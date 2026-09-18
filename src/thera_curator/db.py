from __future__ import annotations
import json, os, shutil, sqlite3
from pathlib import Path
from typing import Iterable
from .constants import DB_FIELDS, WHO_AUTHORITY_FIELDS, EVIDENCE_FIELDS, COLUMN_TO_DB
from .paths import database_path, resource_path, backups_dir
from .utils import utcnow, json_dumps

SCHEMA_SQL = r'''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    english_description TEXT DEFAULT '', structure_summary TEXT DEFAULT '',
    heavy_chain_count INTEGER DEFAULT 0, heavy_chain_fasta TEXT DEFAULT '',
    light_chain_count INTEGER DEFAULT 0, light_chain_fasta TEXT DEFAULT '',
    non_variable_fasta TEXT DEFAULT '', ptms TEXT DEFAULT '', pdf_pages TEXT DEFAULT '',
    quality_notes TEXT DEFAULT '', alternative_names TEXT DEFAULT '', literature TEXT DEFAULT '',
    clinical_trials TEXT DEFAULT '', immunogenicity TEXT DEFAULT '', patent_information TEXT DEFAULT '',
    external_evidence_notes TEXT DEFAULT '', cas_registry_number TEXT DEFAULT '', sequence_qc_status TEXT DEFAULT '',
    who_list TEXT DEFAULT '', source_pdf_hash TEXT DEFAULT '', source_pdf_name TEXT DEFAULT '',
    source_provenance_json TEXT DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT, drug_name TEXT, evidence_category TEXT, alias_searched TEXT,
    database_source TEXT, exact_query TEXT, result_summary TEXT, source_title TEXT, source_identifier TEXT,
    url TEXT, url_validation_status TEXT, access_date TEXT, evidence_type TEXT, confidence TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS favorites (drug_name TEXT PRIMARY KEY COLLATE NOCASE, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recent_records (drug_name TEXT PRIMARY KEY COLLATE NOCASE, opened_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS import_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source_pdf TEXT NOT NULL, source_pdf_hash TEXT NOT NULL,
    who_list TEXT DEFAULT '', created_at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pending_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL REFERENCES import_sessions(id) ON DELETE CASCADE,
    drug_name TEXT NOT NULL, parse_status TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'pending',
    is_existing INTEGER NOT NULL DEFAULT 0, record_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(session_id, drug_name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER REFERENCES pending_candidates(id) ON DELETE SET NULL,
    drug_name TEXT NOT NULL, field_name TEXT NOT NULL, original_value TEXT, corrected_value TEXT, reason TEXT NOT NULL,
    source_page TEXT, review_status TEXT NOT NULL, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS merge_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, drug_name TEXT NOT NULL, field_name TEXT NOT NULL,
    existing_value TEXT, incoming_value TEXT, resolution TEXT NOT NULL, timestamp TEXT NOT NULL, source TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS url_validation (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, status TEXT NOT NULL, final_url TEXT,
    checked_at TEXT NOT NULL, detail TEXT
);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT);
'''

class Database:
    def __init__(self, path: str|Path|None=None, initialize: bool=True):
        self.path=Path(path) if path else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if initialize and not self.path.exists():
            seed=resource_path('seed.sqlite')
            if seed.exists(): shutil.copy2(seed, self.path)
        self.con=sqlite3.connect(self.path)
        self.con.row_factory=sqlite3.Row
        self.con.executescript(SCHEMA_SQL)
        self.con.commit()

    def close(self):
        self.con.close()

    def count_records(self) -> int:
        return self.con.execute('select count(*) from records').fetchone()[0]

    def get_record(self, drug_name: str, mark_recent: bool=True):
        row=self.con.execute('select * from records where drug_name=? collate nocase',(drug_name,)).fetchone()
        if row and mark_recent:
            self.con.execute('insert into recent_records(drug_name,opened_at) values(?,?) on conflict(drug_name) do update set opened_at=excluded.opened_at',(row['drug_name'],utcnow()))
            self.con.commit()
        return dict(row) if row else None

    def list_records(self, letter: str|None=None, limit: int=1000):
        if letter:
            rows=self.con.execute('select * from records where drug_name like ? order by drug_name limit ?', (letter+'%',limit)).fetchall()
        else:
            rows=self.con.execute('select * from records order by drug_name limit ?', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str='', qc: str='', favorites_only: bool=False, limit: int=200):
        q=(query or '').strip()
        params=[]
        sql='select distinct r.* from records r '
        if favorites_only: sql+=' join favorites f on lower(f.drug_name)=lower(r.drug_name) '
        wh=[]
        if q:
            pat=f'%{q}%'; params.extend([pat]*10)
            wh.append('('+' or '.join([
                'r.drug_name like ?','r.alternative_names like ?','r.cas_registry_number like ?',
                'r.english_description like ?','r.structure_summary like ?','r.clinical_trials like ?',
                'r.patent_information like ?','r.literature like ?','r.immunogenicity like ?',
                'r.external_evidence_notes like ?'])+')')
        if qc:
            wh.append('r.sequence_qc_status like ?'); params.append('%'+qc+'%')
        if wh: sql+=' where '+' and '.join(wh)
        sql+=' order by case when lower(r.drug_name)=lower(?) then 0 when lower(r.drug_name) like lower(?) then 1 else 2 end, r.drug_name limit ?'
        params.extend([q,q+'%',limit])
        rows=[dict(r) for r in self.con.execute(sql,params).fetchall()]
        if q and len(rows)<limit:
            try:
                from rapidfuzz import fuzz
                seen={r['drug_name'].lower() for r in rows}
                pool=[dict(r) for r in self.con.execute('select * from records order by drug_name').fetchall()]
                scored=[]
                for r in pool:
                    if r['drug_name'].lower() in seen: continue
                    hay=' | '.join([r.get('drug_name',''),r.get('alternative_names',''),r.get('cas_registry_number','')])
                    score=fuzz.WRatio(q.lower(),hay.lower())
                    if score>=72: scored.append((score,r))
                scored.sort(key=lambda x:(-x[0],x[1]['drug_name']))
                rows.extend(r for _,r in scored[:max(0,limit-len(rows))])
            except Exception:
                pass
        return rows

    def set_favorite(self, drug_name: str, enabled: bool):
        if enabled:
            self.con.execute('insert or replace into favorites(drug_name,added_at) values(?,?)',(drug_name,utcnow()))
        else: self.con.execute('delete from favorites where drug_name=? collate nocase',(drug_name,))
        self.con.commit()

    def is_favorite(self, drug_name: str) -> bool:
        return bool(self.con.execute('select 1 from favorites where drug_name=? collate nocase',(drug_name,)).fetchone())

    def favorites(self):
        return [r[0] for r in self.con.execute('select drug_name from favorites order by drug_name')]

    def recent(self, limit=12):
        return [dict(r) for r in self.con.execute('select r.* from recent_records x join records r on lower(r.drug_name)=lower(x.drug_name) order by x.opened_at desc limit ?',(limit,)).fetchall()]

    def dashboard(self):
        d={'records':self.count_records()}
        d['favorites']=self.con.execute('select count(*) from favorites').fetchone()[0]
        d['pending']=self.con.execute("select count(*) from pending_candidates where review_status='pending'").fetchone()[0]
        d['review']=self.con.execute("select count(*) from pending_candidates where parse_status='REVIEW' and review_status='pending'").fetchone()[0]
        d['qc_review']=self.con.execute("select count(*) from records where upper(sequence_qc_status) like '%REVIEW%'").fetchone()[0]
        return d

    def backup(self, label: str='manual') -> Path:
        stamp=utcnow().replace(':','').replace('+00:00','Z').replace('-','')
        dest=backups_dir()/f'curator_{label}_{stamp}.sqlite'
        self.con.commit()
        dest.parent.mkdir(parents=True,exist_ok=True)
        out=sqlite3.connect(dest)
        with out: self.con.backup(out)
        out.close(); return dest

    def restore(self, backup_path: str|Path):
        backup_path=Path(backup_path)
        if not backup_path.exists(): raise FileNotFoundError(backup_path)
        self.close(); shutil.copy2(backup_path,self.path)
        self.con=sqlite3.connect(self.path); self.con.row_factory=sqlite3.Row; self.con.executescript(SCHEMA_SQL); self.con.commit()

    def create_import_session(self, source_pdf: str, source_hash: str, who_list: str, notes: str='') -> int:
        cur=self.con.execute('insert into import_sessions(source_pdf,source_pdf_hash,who_list,created_at,state,notes) values(?,?,?,?,?,?)',(source_pdf,source_hash,who_list,utcnow(),'pending',notes))
        self.con.commit(); return int(cur.lastrowid)

    def add_pending_candidates(self, session_id: int, candidates: Iterable[dict]):
        now=utcnow()
        for rec in candidates:
            name=rec.get('drug_name','').strip()
            existing=bool(self.con.execute('select 1 from records where drug_name=? collate nocase',(name,)).fetchone())
            status=rec.get('parse_status') or ('PASS' if 'validated' in rec.get('sequence_qc_status','').lower() and 'review' not in rec.get('sequence_qc_status','').lower() else 'REVIEW')
            self.con.execute('''insert into pending_candidates(session_id,drug_name,parse_status,review_status,is_existing,record_json,created_at,updated_at)
                values(?,?,?,?,?,?,?,?) on conflict(session_id,drug_name) do update set parse_status=excluded.parse_status,is_existing=excluded.is_existing,record_json=excluded.record_json,updated_at=excluded.updated_at''',
                (session_id,name,status,'pending',int(existing),json_dumps(rec),now,now))
        self.con.commit()

    def pending(self, session_id: int|None=None):
        if session_id:
            rows=self.con.execute('select * from pending_candidates where session_id=? order by drug_name',(session_id,)).fetchall()
        else:
            rows=self.con.execute("select p.* from pending_candidates p join import_sessions s on s.id=p.session_id where s.state='pending' order by p.session_id desc,p.drug_name").fetchall()
        out=[]
        for r in rows:
            d=dict(r); d['record']=json.loads(d['record_json']); out.append(d)
        return out

    def sessions(self, pending_only=False):
        sql='select * from import_sessions'
        if pending_only: sql+=" where state='pending'"
        sql+=' order by id desc'
        return [dict(r) for r in self.con.execute(sql).fetchall()]

    def set_candidate_review(self, candidate_id: int, status: str):
        if status not in {'pending','approved','rejected','manual_review'}: raise ValueError(status)
        self.con.execute('update pending_candidates set review_status=?,updated_at=? where id=?',(status,utcnow(),candidate_id)); self.con.commit()

    def approve_all_pass(self, session_id: int):
        self.con.execute("update pending_candidates set review_status='approved',updated_at=? where session_id=? and parse_status='PASS' and review_status='pending'",(utcnow(),session_id)); self.con.commit()

    def clear_approved(self, session_id: int):
        self.con.execute("update pending_candidates set review_status='pending',updated_at=? where session_id=? and review_status='approved'",(utcnow(),session_id)); self.con.commit()

    def correct_candidate_field(self, candidate_id: int, field_name: str, value, reason: str, source_page: str=''):
        row=self.con.execute('select * from pending_candidates where id=?',(candidate_id,)).fetchone()
        if not row: raise KeyError(candidate_id)
        rec=json.loads(row['record_json']); old=rec.get(field_name); rec[field_name]=value
        self.con.execute('update pending_candidates set record_json=?,updated_at=? where id=?',(json_dumps(rec),utcnow(),candidate_id))
        self.con.execute('insert into corrections(candidate_id,drug_name,field_name,original_value,corrected_value,reason,source_page,review_status,timestamp) values(?,?,?,?,?,?,?,?,?)',
                         (candidate_id,row['drug_name'],field_name,'' if old is None else str(old),'' if value is None else str(value),reason,source_page,row['review_status'],utcnow()))
        self.con.commit()

    def _merge_record(self, rec: dict, source='WHO PDF') -> str:
        name=rec['drug_name'].strip()
        existing=self.get_record(name, mark_recent=False)
        now=utcnow()
        if not existing:
            fields=DB_FIELDS + ['who_list','source_pdf_hash','source_pdf_name','source_provenance_json']
            vals=[rec.get(f,'') for f in fields]
            self.con.execute(f"insert into records({','.join(fields)},created_at,updated_at) values({','.join('?' for _ in fields)},?,?)", vals+[now,now])
            return 'added'
        changed=False
        updates={}
        for f in DB_FIELDS[1:]:
            incoming=rec.get(f,'')
            current=existing.get(f,'')
            if incoming in ('',None,0): continue
            if current in ('',None,0): updates[f]=incoming; changed=True; continue
            if str(current)==str(incoming): continue
            resolution='preserved-existing'
            # WHO source may refresh official WHO fields only when source is a WHO import and current record has no stronger manually curated marker.
            if source.startswith('WHO') and f in WHO_AUTHORITY_FIELDS and 'manual correction' not in (existing.get('quality_notes') or '').lower():
                # Preserve stronger existing curation by default; conflict is auditable and reviewer can edit.
                resolution='conflict-preserved-existing'
            self.con.execute('insert into merge_conflicts(drug_name,field_name,existing_value,incoming_value,resolution,timestamp,source) values(?,?,?,?,?,?,?)',
                             (name,f,str(current),str(incoming),resolution,now,source))
        for f in ['who_list','source_pdf_hash','source_pdf_name','source_provenance_json']:
            if rec.get(f) and not existing.get(f): updates[f]=rec[f]; changed=True
        if updates:
            sets=','.join(f'{k}=?' for k in updates)
            self.con.execute(f'update records set {sets},updated_at=? where drug_name=? collate nocase', list(updates.values())+[now,name])
        return 'updated' if changed else 'unchanged'

    def merge_approved(self, session_id: int):
        self.backup('pre_merge')
        rows=self.con.execute("select * from pending_candidates where session_id=? and review_status='approved' order by id",(session_id,)).fetchall()
        stats={'added':0,'updated':0,'unchanged':0}
        for row in rows:
            rec=json.loads(row['record_json']); result=self._merge_record(rec,'WHO PDF'); stats[result]+=1
        self.con.execute("update import_sessions set state='merged' where id=?",(session_id,))
        self.con.commit(); return stats

    def merge_workbook_records(self, records: list[dict], source='Workbook'):
        self.backup('pre_workbook_merge')
        stats={'added':0,'updated':0,'unchanged':0}
        for rec in records:
            result=self._merge_record(rec,source); stats[result]+=1
        self.con.commit(); return stats

    def correction_history(self, drug_name: str):
        return [dict(r) for r in self.con.execute('select * from corrections where drug_name=? collate nocase order by id desc',(drug_name,)).fetchall()]

    def evidence_for(self, drug_name: str):
        return [dict(r) for r in self.con.execute('select * from evidence_ledger where drug_name=? collate nocase order by id',(drug_name,)).fetchall()]

    def record_url_validation(self, url: str, status: str, final_url: str='', detail: str=''):
        self.con.execute('insert into url_validation(url,status,final_url,checked_at,detail) values(?,?,?,?,?) on conflict(url) do update set status=excluded.status,final_url=excluded.final_url,checked_at=excluded.checked_at,detail=excluded.detail',
                         (url,status,final_url,utcnow(),detail))
        self.con.execute('update evidence_ledger set url_validation_status=? where url=?',(status,url))
        self.con.commit()

    def urls_to_validate(self):
        return [r[0] for r in self.con.execute("select distinct url from evidence_ledger where trim(coalesce(url,''))<>'' order by url").fetchall()]
