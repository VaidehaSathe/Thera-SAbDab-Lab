from thera_curator.db import Database
from thera_curator.constants import CANONICAL_COLUMNS
from thera_curator.workbook import inspect_workbook

def test_seed_has_70_records(tmp_path):
    db=Database(tmp_path/'db.sqlite'); assert db.count_records()==70
    r=db.get_record('avrukibart',False); assert r and r['heavy_chain_count']==2 and r['light_chain_count']==2
    db.close()

def test_workbook_schema_exact(gold_xlsx):
    info=inspect_workbook(gold_xlsx); assert info['schema_ok']; assert info['headers']==CANONICAL_COLUMNS; assert info['row_count']==70
