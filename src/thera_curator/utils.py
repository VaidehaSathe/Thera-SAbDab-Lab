from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from .constants import AMINO_ACIDS


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact_space(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def normalize_sequence(s: str) -> str:
    seq="".join(re.findall(r"[A-Za-z]+", s)).upper()
    return seq


def validate_sequence(seq: str) -> tuple[bool,str]:
    bad=sorted(set(seq)-AMINO_ACIDS)
    if bad: return False, "invalid residues: " + ",".join(bad)
    if not seq: return False, "empty sequence"
    return True, "OK"


def parse_fasta(text: str) -> list[tuple[str,str]]:
    out=[]; header=None; chunks=[]
    for line in (text or "").splitlines():
        line=line.strip()
        if not line: continue
        if line.startswith('>'):
            if header is not None: out.append((header, ''.join(chunks).upper()))
            header=line[1:]; chunks=[]
        else: chunks.append(re.sub(r"\s+", "", line))
    if header is not None: out.append((header, ''.join(chunks).upper()))
    return out


def fasta_lengths(text: str) -> list[int]:
    return [len(seq) for _,seq in parse_fasta(text)]


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
