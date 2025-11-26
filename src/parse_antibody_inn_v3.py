#!/usr/bin/env python3
"""
Improved parser for WHO Proposed INN text (antibody biologics).

Input:  text file from your OCR/layout pipeline
Output: TSV file with columns: INN, Description, Sequence, Modifications

USEAGE: python src/parse_antibody_inn_v3.py data/outputs/inputfile.txt --out-tsv data/outputs/outputfile.tsv

"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple, Dict

import pandas as pd

# INN stems indicating antibody biologics
# (legacy + new WHO stems)
ANTIBODY_STEMS = ("mab", "tug", "bart", "mig", "ment")


# -------------------------------------------------------------------
# 1. Load & clean
# -------------------------------------------------------------------
def load_and_clean(path: str | Path) -> List[str]:
    """
    Load text and remove:
      - OCR image markers ('===== IMAGE page-xx.png =====')
      - WHO headers with 'WHO Drug Information' and 'Proposed INN: List'
      - bare page numbers (e.g. '535', '536', '538')
    Keep non-empty lines only.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    cleaned: List[str] = []

    for ln in raw:
        s = ln.rstrip("\n")
        stripped = s.strip()

        if not stripped:
            cleaned.append("")  # keep blank lines as separators
            continue

        # layout/image markers
        if stripped.startswith("===== IMAGE") and stripped.endswith("====="):
            continue

        # WHO header lines (either order of the two phrases)
        if "WHO Drug Information" in stripped and "Proposed INN: List" in stripped:
            continue
        if stripped.startswith("Proposed INN: List") and "WHO Drug Information" in stripped:
            continue

        # bare page numbers
        if re.fullmatch(r"\d{1,4}", stripped):
            continue

        cleaned.append(s)

    return cleaned


# -------------------------------------------------------------------
# 2. Split into INN entries
# -------------------------------------------------------------------
def find_entry_starts(lines: List[str]) -> List[int]:
    """
    An entry header looks like: 'gaspantatugum #' etc.
    """
    starts: List[int] = []
    header_re = re.compile(r"^\s*\S+um\s*#$", re.IGNORECASE)
    for i, line in enumerate(lines):
        if header_re.match(line.strip()):
            starts.append(i)
    return starts


def split_entries(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """
    Return list of (header_line, body_lines).
    """
    starts = find_entry_starts(lines)
    entries: List[Tuple[str, List[str]]] = []

    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        header = lines[start]
        body = lines[start + 1:end]
        entries.append((header, body))

    return entries


# -------------------------------------------------------------------
# 3. INN parsing & antibody filter
# -------------------------------------------------------------------
def get_base_inn(header: str) -> str:
    """
    From 'gaspantatugum #' -> 'gaspantatug'
    """
    stripped = header.strip()
    if stripped.endswith("#"):
        stripped = stripped[:-1].strip()

    parts = stripped.split()
    latin = ""
    for token in parts:
        if token.lower().endswith("um"):
            latin = token
            break

    base = re.sub(r"um$", "", latin, flags=re.IGNORECASE)
    return base


def is_antibody_inn(base_inn: str) -> bool:
    inn = base_inn.lower()
    return any(inn.endswith(stem) for stem in ANTIBODY_STEMS)


# -------------------------------------------------------------------
# 4. Description extraction (English only)
# -------------------------------------------------------------------
def extract_description(body: List[str], inn: str) -> str:
    """
    Extract the English description block.

    Pattern in your data:

        <blank>
        inn
        immunoglobulin G...  (English block)
        ...
        antineoplastic / immunomodulator / angiogenesis inhibitor
        <blank>
        inn
        immunoglobuline G... (French block)
        ...

    Strategy:
      - Find all indices where line.strip().lower() == inn.lower()
      - English description starts at index[0] + 1
      - Ends at index[1] (start of French) if present, else end of body
    """
    inn_lower = inn.lower()
    inn_indices: List[int] = []

    # Find all "bare INN" lines
    for i, line in enumerate(body):
        if line.strip().lower() == inn_lower:
            inn_indices.append(i)

    if not inn_indices:
        # Fallback: line starting with INN + space (if OCR merged)
        for i, line in enumerate(body):
            if line.strip().lower().startswith(inn_lower + " "):
                inn_indices.append(i)
                break

    if not inn_indices:
        return ""

    start = inn_indices[0] + 1  # line after 'inn'
    end = inn_indices[1] if len(inn_indices) > 1 else len(body)

    # Slice and trim leading/trailing blanks
    desc_lines = body[start:end]
    # Remove leading/trailing empty lines
    while desc_lines and not desc_lines[0].strip():
        desc_lines.pop(0)
    while desc_lines and not desc_lines[-1].strip():
        desc_lines.pop()

    if not desc_lines:
        return ""

    # Join lines into a single string, normalising whitespace
    desc_text = " ".join(l.strip() for l in desc_lines)
    desc_text = re.sub(r"\s+", " ", desc_text).strip()
    return desc_text



# -------------------------------------------------------------------
# 5. Sequence & modifications
# -------------------------------------------------------------------
def extract_sequence(body: List[str]) -> str:
    """
    Sequence block pattern:

        <CAS number>
        Heavy chain / Chaine lourde / Cadena pesada ...
        ... lines with amino acids ...
        Light chain / ...
        ... lines with amino acids ...
        (then 'Post-translational modifications')

    Strategy:
      - Build full_text = '\n'.join(body)
      - Find first CAS-like pattern: \d{2,8}-\d{2}-\d
      - Sequence starts at that CAS line
      - Ends just before 'Post-translational modifications'
    """
    full_text = "\n".join(body)

    cas_match = re.search(r"\b\d{2,8}-\d{2}-\d\b", full_text)
    ptm_match = re.search(
        r"Post[-\s]*translational\s*modifications?",
        full_text,
        flags=re.IGNORECASE,
    )

    if not cas_match:
        return ""

    seq_start = cas_match.start()
    seq_end = ptm_match.start() if ptm_match else len(full_text)
    seq_block = full_text[seq_start:seq_end]

    # Clean up a bit: collapse whitespace but keep it as text sequence
    seq_block = re.sub(r"[ \t]+", " ", seq_block)
    seq_block = re.sub(r"\s*\n\s*", " ", seq_block)
    return seq_block.strip()


def extract_modifications(body: List[str]) -> str:
    """
    Modifications block pattern:

        Post-translational modifications
        Disulfide bridges ...
        ...
        C-terminal lysine clipping ...

    Strategy:
      - Start from 'Post-translational modifications'
      - Take everything to end of entry
    """
    full_text = "\n".join(body)
    ptm_match = re.search(
        r"Post[-\s]*translational\s*modifications?",
        full_text,
        flags=re.IGNORECASE,
    )

    if not ptm_match:
        return ""

    mods_block = full_text[ptm_match.start():]
    mods_block = re.sub(r"[ \t]+", " ", mods_block)
    mods_block = re.sub(r"\s*\n\s*", " ", mods_block)
    return mods_block.strip()


# -------------------------------------------------------------------
# 6. Main parsing function
# -------------------------------------------------------------------
def parse_antibody_entries(txt_path: str | Path) -> pd.DataFrame:
    lines = load_and_clean(txt_path)
    entries = split_entries(lines)

    rows: List[Dict[str, str]] = []

    for header, body in entries:
        base_inn = get_base_inn(header)
        if not base_inn:
            continue

        if not is_antibody_inn(base_inn):
            continue

        desc = extract_description(body, base_inn)
        seq = extract_sequence(body)
        mods = extract_modifications(body)

        rows.append(
            {
                "INN": base_inn,
                "Description": desc,
                "Sequence": seq,
                "Modifications": mods,
            }
        )

    df = pd.DataFrame(rows, columns=["INN", "Description", "Sequence", "Modifications"])
    return df


# -------------------------------------------------------------------
# 7. CLI
# -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Parse WHO INN antibody entries (txt) → TSV with INN, Description, Sequence, Modifications."
    )
    parser.add_argument("txt_file", help="Path to input .txt file")
    parser.add_argument(
        "--out-tsv",
        default="antibody_inn_entries.tsv",
        help="Output TSV filename (default: antibody_inn_entries.tsv)",
    )
    args = parser.parse_args()

    df = parse_antibody_entries(args.txt_file)
    df.to_csv(args.out_tsv, index=False, sep="\t")  # TSV output

    print(f"Parsed {len(df)} antibody entries → {args.out_tsv}")
    with pd.option_context("display.max_colwidth", 120, "display.width", 160):
        print(df.head(3))


if __name__ == "__main__":
    main()
