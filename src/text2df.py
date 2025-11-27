#!/usr/bin/env python3
"""
Pipeline:
1) Remove redundant metadata:
   - Page markers: '===== page-xx.png ====='
   - Header lines: 'WHO Drug Information, Vol. xx, No. x, 20xx Proposed INN: List xxx'
                  or 'Proposed INN: List xxx WHO Drug Information, Vol. xx, No. x, 20xx'
   - Page numbers at the bottom: lines that are just digits (e.g. '535')

2) Mark INN entries:
   - Insert '#=========INN Entry Found========#' above any line that contains
     at least one word ending in 'um' (e.g. 'gaspantatugum #',
     'grebenmotidum simoleninum alfa #').

3) Keep only antibody entries (based on INN stems) and structure them:
   - For each entry:
     * Keep only those whose INN name (without 'um') ends with one of:
         -mab, -bart, -rac, -ment, -mig, -umab, -zumab, -ximab, -tug, -fusp
     * Within kept entries, split into:
         INN name line
         #=======Description=======#   (first language block only – assumed English)
         #=======Sequence=======#      (from CAS number line)
         #=======Modifications=======# (from 'Post-translational modifications' line)
   - At the end, append a list of removed INNs.
"""

import argparse
import sys
from pathlib import Path
import re
import unicodedata


def read_text(input_path: str) -> str:
    """Read text from a file."""
    if input_path == "-":
        return sys.stdin.read()
    return Path(input_path).read_text(encoding="utf-8")


def strip_accents(s: str) -> str:
    """Remove all accent marks from a Unicode string."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def remove_metadata(text: str) -> str:
    """
    Remove page markers, header lines, and standalone numeric page numbers.
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # 1) Page markers like "===== page-85.png ====="
        if re.match(r"^=+\s*page-.*\.png\s*=+$", stripped, flags=re.IGNORECASE):
            continue

        # 2) Header lines that contain both WHO header and Proposed INN
        if ("WHO Drug Information" in stripped
                and "Proposed INN: List" in stripped):
            continue

        # 3) Standalone page numbers: "535", "536", ...
        if stripped.isdigit():
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def mark_inn_entries(text: str) -> str:
    """
    Insert a marker line above each INN entry name line.

    Current heuristic for an INN entry name line:
    - The line contains at least one word ending in 'um'.
      Examples matched:
        'gaspantatugum #'
        'gimvekibartum '
        'grebenmotidum simoleninum alfa #'
    """
    lines = text.splitlines()
    marked_lines = []

    pattern = re.compile(r"\b[a-zA-Z]+um\b")

    for line in lines:
        if pattern.search(line):
            marked_lines.append("#=========INN Entry Found========#")
        marked_lines.append(line)

    return "\n".join(marked_lines)


def segment_entry(entry_lines):
    """
    For a single INN entry (list of lines, including the marker as [0]),
    structure it as:

      #=========INN Entry Found========#
      <INN name line>
      #=======Description=======#
      <first language block (assumed English)>

      #=======Sequence=======#
      <CAS + heavy/light chain section>

      #=======Modifications=======#
      <post-translational modifications till end>

    Description isolation uses the INN name as anchor:
    - Each language block in the description starts with the INN name
      (or its accented variant).
    - We:
        * strip accents and lowercase,
        * derive a root stem from the INN name,
        * in the description region, find all lines whose
          accent-stripped, lowercased text starts with that stem,
        * treat these as language-block starts,
        * keep only the first block, drop the rest.
    """
    if not entry_lines:
        return entry_lines

    marker_line = entry_lines[0]
    body = entry_lines[1:]

    # --- Find INN name line: first non-empty, non-marker line ---
    name_idx = None
    name_line = None
    for idx, line in enumerate(body):
        candidate = line.strip()
        if not candidate:
            continue
        if candidate == marker_line.strip():
            continue
        name_idx = idx
        name_line = line  # keep original formatting
        break

    if name_idx is None:
        name_idx = 0
        name_line = None

    # --- Derive stem from INN name ---
    inn_root_stem = None
    if name_line is not None:
        plain = strip_accents(name_line).lower()
        # remove trailing comment after '#'
        plain = plain.split("#", 1)[0]
        plain = re.sub(r"\s+", " ", plain).strip()
        tokens = plain.split(" ")
        # take first token that has letters
        first_token = None
        for t in tokens:
            if any(c.isalpha() for c in t):
                first_token = t
                break
        if first_token:
            # remove trailing 'um' if present (e.g. gimvekibartum -> gimvekibart)
            if first_token.endswith("um"):
                inn_root_stem = first_token[:-2]
            else:
                inn_root_stem = first_token
            inn_root_stem = inn_root_stem.strip()

    # --- Find CAS-like identifier line (xxxxx-xx-x style anywhere in line) ---
    cas_pattern = re.compile(r"\d{5,8}-\d{2}-\d")
    cas_idx = None
    for idx, line in enumerate(body):
        if cas_pattern.search(line):
            cas_idx = idx
            break

    # --- Find 'Post-translational modifications' header ---
    ptm_idx = None
    if cas_idx is not None:
        for idx in range(cas_idx + 1, len(body)):
            if "Post-translational modifications" in body[idx]:
                ptm_idx = idx
                break

    # --- Define sections in terms of 'body' indices ---
    desc_start = name_idx + 1
    desc_end = cas_idx if cas_idx is not None else len(body)
    description_lines = body[desc_start:desc_end]

    sequence_lines = []
    modifications_lines = []

    if cas_idx is not None:
        seq_end = ptm_idx if ptm_idx is not None else len(body)
        sequence_lines = body[cas_idx:seq_end]

        if ptm_idx is not None:
            modifications_lines = body[ptm_idx:]
        else:
            modifications_lines = []

    # --- Use INN-based block boundaries in description ---
    filtered_desc = []

    if inn_root_stem and description_lines:
        # Find all indices in description_lines where a line starts a language block
        block_starts = []
        for idx, ln in enumerate(description_lines):
            plain_ln = strip_accents(ln).lower().lstrip()
            if plain_ln.startswith(inn_root_stem):
                block_starts.append(idx)

        if block_starts:
            start0 = block_starts[0]
            if len(block_starts) > 1:
                end0 = block_starts[1]
            else:
                end0 = len(description_lines)
            filtered_desc = description_lines[start0:end0]

    # Fallback if we didn't detect any block using INN name
    if not filtered_desc and description_lines:
        # simple fallback: first contiguous non-empty block
        started = False
        for ln in description_lines:
            if not started:
                if ln.strip() == "":
                    continue
                started = True
                filtered_desc.append(ln)
            else:
                if ln.strip() == "":
                    break
                filtered_desc.append(ln)

        if not filtered_desc:
            filtered_desc = description_lines

    # --- Rebuild structured entry ---
    new_entry = [marker_line]

    if name_line is not None:
        new_entry.append(name_line)

    if filtered_desc:
        new_entry.append("#=======Description=======#")
        new_entry.extend(filtered_desc)
        new_entry.append("")

    if sequence_lines:
        new_entry.append("#=======Sequence=======#")
        new_entry.extend(sequence_lines)
        new_entry.append("")

    if modifications_lines:
        new_entry.append("#=======Modifications=======#")
        new_entry.extend(modifications_lines)

    return new_entry


def filter_antibody_entries(text: str) -> str:
    """
    Keep only INN entries whose name matches antibody-related stems and
    structure each kept entry into Description / Sequence / Modifications.

    Entry definition:
    - Starts at a line equal to '#=========INN Entry Found========#'
      and continues up to (but not including) the next such marker.

    Classification:
    - INN name line = first non-empty, non-marker line after the marker.
    - From that line, gather tokens ending in 'um'.
    - For each such token, strip trailing 'um' and check if the base ends with
      any of the stems:
        -mab, -bart, -rac, -ment, -mig, -umab, -zumab, -ximab, -tug, -fusp
    - If any token matches, keep & segment the entry.
    - Otherwise, drop the entry and record the *first* INN token found.
    """
    marker = "#=========INN Entry Found========#"
    stems = ["mab", "bart", "rac", "ment", "mig", "umab", "zumab", "ximab", "tug", "fusp"]

    lines = text.splitlines()

    # Split into preamble and entries
    preamble = []
    entries = []

    i = 0
    while i < len(lines) and lines[i].strip() != marker:
        preamble.append(lines[i])
        i += 1

    while i < len(lines):
        if lines[i].strip() == marker:
            entry = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip() != marker:
                entry.append(lines[i])
                i += 1
            entries.append(entry)
        else:
            preamble.append(lines[i])
            i += 1

    kept_entries = []
    removed_inns = []

    for entry in entries:
        # Find INN name line
        name_line = None
        for line in entry[1:]:
            candidate = line.strip()
            if not candidate:
                continue
            if candidate == marker:
                continue
            name_line = candidate
            break

        if not name_line:
            continue

        # Extract tokens ending in 'um'
        tokens = re.split(r"\s+", name_line)
        inn_tokens = []
        for tok in tokens:
            cleaned = tok.strip(",;()")
            if cleaned.lower().endswith("um"):
                inn_tokens.append(cleaned)

        if not inn_tokens:
            continue

        # Check stems
        is_antibody = False
        for inn in inn_tokens:
            base = inn[:-2]  # remove trailing 'um'
            base_lower = base.lower()
            for stem in stems:
                if base_lower.endswith(stem):
                    is_antibody = True
                    break
            if is_antibody:
                break

        if is_antibody:
            processed_entry = segment_entry(entry)
            kept_entries.append(processed_entry)
        else:
            removed_inns.append(inn_tokens[0])

    # Rebuild output
    out_lines = []

    # Preamble
    out_lines.extend(preamble)
    if preamble and preamble[-1].strip() != "":
        out_lines.append("")

    # Kept entries
    for entry in kept_entries:
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        out_lines.extend(entry)

    # Removed INNs section
    out_lines.append("")
    out_lines.append("#=========REMOVED INN ENTRIES========#")
    if removed_inns:
        for inn in removed_inns:
            out_lines.append(inn)
    else:
        out_lines.append("(none)")

    return "\n".join(out_lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Process OCR'd INN text: remove metadata, mark entries, "
            "keep only antibody entries, structure them, and list removed INNs."
        )
    )

    parser.add_argument(
        "input",
        help="Input text file (use '-' for stdin).",
    )
    parser.add_argument(
        "output",
        help="Output text file (use '-' for stdout).",
    )

    args = parser.parse_args()

    raw_text = read_text(args.input)
    no_meta = remove_metadata(raw_text)
    marked = mark_inn_entries(no_meta)
    processed = filter_antibody_entries(marked)

    if args.output == "-":
        sys.stdout.write(processed)
    else:
        Path(args.output).write_text(processed, encoding="utf-8")


if __name__ == "__main__":
    main()




