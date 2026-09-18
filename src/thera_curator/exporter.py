from __future__ import annotations
import html, json
from pathlib import Path
from .constants import DB_FIELDS, DB_TO_COLUMN
from .utils import parse_fasta


def record_text(rec: dict) -> str:
    parts=[]
    for f in DB_FIELDS:
        parts.append(f"{DB_TO_COLUMN[f]}:\n{rec.get(f,'')}\n")
    return '\n'.join(parts)


def record_json(rec: dict) -> str:
    return json.dumps({DB_TO_COLUMN[f]:rec.get(f,'') for f in DB_FIELDS},ensure_ascii=False,indent=2)


def record_html(rec: dict) -> str:
    rows=''.join(f"<tr><th>{html.escape(DB_TO_COLUMN[f])}</th><td><pre>{html.escape(str(rec.get(f,'')))}</pre></td></tr>" for f in DB_FIELDS)
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(rec.get('drug_name',''))}</title><style>
    body{{font-family:Segoe UI,Arial,sans-serif;margin:2rem;color:#1d2730}} h1{{color:#174f6b}} table{{border-collapse:collapse;width:100%}} th{{width:24%;text-align:left;vertical-align:top;background:#eef4f7}} td,th{{padding:.6rem;border-bottom:1px solid #d8e0e5}} pre{{white-space:pre-wrap;word-break:break-word;font-family:Consolas,monospace}}</style></head><body><h1>{html.escape(rec.get('drug_name',''))}</h1><table>{rows}</table></body></html>'''


def export_record(rec: dict, path: str|Path):
    path=Path(path); ext=path.suffix.lower()
    if ext=='.json': text=record_json(rec)
    elif ext in {'.html','.htm'}: text=record_html(rec)
    else: text=record_text(rec)
    path.write_text(text,encoding='utf-8')
    return path
