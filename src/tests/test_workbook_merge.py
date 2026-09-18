from openpyxl import load_workbook
from thera_curator.db import Database
from thera_curator.workbook import read_antibody_records

def test_workbook_import_merges_not_replaces(tmp_path,gold_xlsx,monkeypatch):
    monkeypatch.setenv('THERA_CURATOR_DATA_DIR',str(tmp_path))
    mod=tmp_path/'mod.xlsx'; wb=load_workbook(gold_xlsx); ws=wb['Antibody Database']; row=[None]*19; row[0]='zztestug'; row[1]='immunoglobulin G1-kappa test'; row[2]='test'; row[3]=2; row[5]=2; row[17]='999999-99-9'; row[18]='REVIEW'; ws.append(row); wb.save(mod)
    db=Database(tmp_path/'db.sqlite'); before=db.count_records(); stats=db.merge_workbook_records(read_antibody_records(mod)); assert before==70; assert db.count_records()==71; assert stats['added']==1; assert db.get_record('avrukibart',False) is not None; db.close()
