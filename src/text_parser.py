#!/usr/bin/env python3
"""
Pipeline:
1) Remove redundant metadata:
   - Page markers: '===== page-xx.png ====='
   - Header lines: 'WHO Drug Information, Vol. xx, No. x, 20xx Proposed INN: List xxx'
                  or 'Proposed INN: List xxx WHO Drug Information, Vol. xx, No. x, 20xx'
   - Page numbers at the bottom: lines that are just digits (e.g. '535')

2) Mark INN entries:
   - Insert '#=========INN Entry========#' above any line that contains
     at least one word ending in 'um' (e.g. 'gaspantatugum #',
     'grebenmotidum simoleninum alfa #').

3) Strip everything before the first INN entry marker.

4) Keep only antibody entries (based on INN stems) and structure them:
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

    Heuristic:
      - Line is considered an INN header if it contains at least one token
        ending in 'um' that is NOT 'actinium' (case-insensitive).
      - This prevents splitting radiolabelled entries like:

          actinium (?Ac) pelgifatamabum mopaxetanum      <-- header (has pelgifatamabum)
          actinium (725Ac) pelgifatamab mopaxetan        <-- synonym line (only 'actinium')

      from being turned into two separate entries.
    """
    lines = text.splitlines()
    marked_lines = []

    um_word_re = re.compile(r"\b([A-Za-z][A-Za-z0-9-]*um)\b")

    for line in lines:
        plain = strip_accents(line)
        matches = um_word_re.findall(plain)
        # Filter out 'actinium' (can extend this list if needed)
        inn_like = [w for w in matches if w.lower() != "actinium"]

        if inn_like:
            marked_lines.append("#=========INN Entry========#")

        marked_lines.append(line)

    return "\n".join(marked_lines)


def strip_before_first_entry(text: str) -> str:
    """
    Remove any content before the first INN entry marker.

    Keeps everything from the first line equal to
    '#=========INN Entry========#' onwards.
    If no marker is found, returns an empty string.
    """
    marker = "#=========INN Entry========#"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == marker:
            # Rebuild text starting from the first marker
            return "\n".join(lines[i:]).lstrip("\n") + "\n"
    # No entry detected
    return ""


def looks_like_sequence_block_start(lines, idx: int) -> bool:
    """
    Heuristic for detecting the start of the sequence block.

    Requires at least 4 lines starting at `idx`:

      0) CAS-like line: ignoring spaces/other chars, must contain
         exactly 10 digits and 2 ASCII dashes (e.g. '3034630-52-6').
      1) Starts with 'Heavy' or 'Light'.
      2) Ends with residue number 50.
      3) Ends with residue number 100.
    """
    if idx + 3 >= len(lines):
        return False

    top = lines[idx]
    second = lines[idx + 1]
    third = lines[idx + 2]
    fourth = lines[idx + 3]

    # Line 0: CAS-like (10 digits, 2 dashes), ignoring spaces/other chars
    filtered = re.sub(r"[^\d-]", "", top)
    digits = re.findall(r"\d", filtered)
    if len(digits) != 10 or filtered.count("-") != 2:
        return False

    # Line 1: starts with 'Heavy' or 'Light'
    second_plain = strip_accents(second)
    if not re.match(r"^\s*(Heavy|Light)\b", second_plain, flags=re.IGNORECASE):
        return False

    # Line 2: ends with ' 50'
    if not re.search(r"\b50\s*$", third):
        return False

    # Line 3: ends with ' 100'
    if not re.search(r"\b100\s*$", fourth):
        return False

    return True


def get_canonical_antibody_from_line(name_line: str) -> str | None:
    """
    From a name line, return the antibody-like INN token (e.g. 'pelgifatamabum'),
    based on the usual stems. Returns None if none found.
    """
    stems = ["mab", "bart", "rac", "ment", "mig", "umab", "zumab", "ximab", "tug", "fusp"]

    plain = strip_accents(name_line)
    tokens = re.split(r"\s+", plain)

    for tok in tokens:
        cleaned = tok.strip(",;()")
        if cleaned.lower().endswith("um"):
            base = cleaned[:-2].lower()
            for stem in stems:
                if base.endswith(stem):
                    return cleaned  # full token (e.g. 'pelgifatamabum')
    return None


def segment_entry(entry_lines, ab_sequence_db=None, canonical_ab=None):
    """
    For a single INN entry (list of lines, including the marker as [0]),
    structure it as:

      #=========INN Entry========#
      <INN name line>
      #=======Description=======#
      <first language block (assumed English) OR 'No information extractable'>

      #=======Sequence=======#
      <sequence block or base antibody fallback
       OR 'No information extractable'>

      #=======Modifications=======#
      <post-translational modifications or base antibody fallback
       OR 'No information extractable'>
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

    # --- Derive stem from INN name for description segmentation ---
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
            if first_token.endswith("um"):
                inn_root_stem = first_token[:-2]
            else:
                inn_root_stem = first_token
            inn_root_stem = inn_root_stem.strip()

    # --- Determine canonical antibody token if not provided ---
    if canonical_ab is None and name_line is not None:
        canonical_ab = get_canonical_antibody_from_line(name_line)

    # --- Find CAS / sequence header using the 4-line pattern, then fallback ---
    cas_idx = None

    # 1) Prefer robust 4-line pattern (CAS + Heavy/Light + 50 + 100)
    for idx in range(len(body) - 3):
        if looks_like_sequence_block_start(body, idx):
            cas_idx = idx
            break

    # 2) Fallback to any CAS-style line if the pattern isn't found
    if cas_idx is None:
        cas_pattern = re.compile(r"\d{5,8}-\d{2}-\d")
        for idx, line in enumerate(body):
            if cas_pattern.search(line):
                cas_idx = idx
                break

    # --- Find 'Post-translational modifications' header ---
    ptm_idx = None
    if cas_idx is not None:
        ptm_pattern = re.compile(
            r"post\s*[-]?\s*translational\s+modifications?",
            re.IGNORECASE,
        )
        for idx in range(cas_idx + 1, len(body)):
            plain_ln = strip_accents(body[idx])
            if ptm_pattern.search(plain_ln):
                ptm_idx = idx
                break

    # --- Define raw regions in terms of 'body' indices ---
    desc_start = name_idx + 1
    desc_end = cas_idx if cas_idx is not None else len(body)
    description_lines = body[desc_start:desc_end]

    sequence_lines = []
    modifications_lines = []

    if cas_idx is not None:
        # sequence starts BELOW the CAS line
        seq_start = cas_idx + 1
        seq_end = ptm_idx if ptm_idx is not None else len(body)
        sequence_lines = body[seq_start:seq_end]

        if ptm_idx is not None:
            modifications_lines = body[ptm_idx:]
        else:
            modifications_lines = []

    # --- Use INN-based block boundaries in description ---
    filtered_desc = []

    if inn_root_stem and description_lines:
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

    # --- Radiolabel / base-antibody fallback via ab_sequence_db ---
    if ab_sequence_db is not None and canonical_ab:
        key = strip_accents(canonical_ab).lower()
        if sequence_lines:
            # We have a sequence for this antibody: record it if not already present
            if key not in ab_sequence_db:
                ab_sequence_db[key] = {
                    "sequence_lines": sequence_lines[:],
                    "modifications_lines": modifications_lines[:],
                }
        else:
            # No sequence in this entry: try to reuse from base antibody
            stored = ab_sequence_db.get(key)
            if stored:
                sequence_lines = stored.get("sequence_lines", [])
                if not modifications_lines:
                    modifications_lines = stored.get("modifications_lines", [])

    # --- Rebuild structured entry with *always-present* sections ---
    new_entry = [marker_line]

    if name_line is not None:
        new_entry.append(name_line)

    # Description
    new_entry.append("#=======Description=======#")
    if filtered_desc:
        new_entry.extend(filtered_desc)
    else:
        new_entry.append("No information extractable")
    new_entry.append("")

    # Sequence
    new_entry.append("#=======Sequence=======#")
    if sequence_lines:
        new_entry.extend(sequence_lines)
    else:
        new_entry.append("No information extractable")
    new_entry.append("")

    # Modifications
    new_entry.append("#=======Modifications=======#")
    if modifications_lines:
        new_entry.extend(modifications_lines)
    else:
        new_entry.append("No information extractable")

    return new_entry


def filter_antibody_entries(text: str) -> str:
    """
    Keep only INN entries whose name matches antibody-related stems and
    structure each kept entry into Description / Sequence / Modifications.

    Additionally:
      - For entries that lack sequence/modification info, reuse the base
        antibody's data if available (e.g. radiolabelled mAbs).
      - Even if no data can be extracted, each entry will still contain
        Description / Sequence / Modifications sections with
        'No information extractable'.
    """
    marker = "#=========INN Entry========#"
    stems = ["mab", "bart", "rac", "ment", "mig", "umab", "zumab", "ximab", "tug", "fusp"]

    lines = text.splitlines()

    # Split into (potentially empty) preamble and entries
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

    # Shared DB of sequences by canonical antibody name
    ab_sequence_db = {}

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

        # Check stems and pick canonical antibody token
        is_antibody = False
        canonical_ab = None
        for inn in inn_tokens:
            base = inn[:-2]  # remove trailing 'um'
            base_lower = base.lower()
            for stem in stems:
                if base_lower.endswith(stem):
                    is_antibody = True
                    canonical_ab = inn
                    break
            if is_antibody:
                break

        if is_antibody:
            processed_entry = segment_entry(
                entry,
                ab_sequence_db=ab_sequence_db,
                canonical_ab=canonical_ab,
            )
            kept_entries.append(processed_entry)
        else:
            removed_inns.append(inn_tokens[0])

    # Rebuild output (preamble is now expected to be empty if strip_before_first_entry used)
    out_lines = []

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
            "strip preamble, keep only antibody entries, structure them, "
            "and list removed INNs."
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
    entries_only = strip_before_first_entry(marked)
    processed = filter_antibody_entries(entries_only)

    if args.output == "-":
        sys.stdout.write(processed)
    else:
        Path(args.output).write_text(processed, encoding="utf-8")


if __name__ == "__main__":
    main()





