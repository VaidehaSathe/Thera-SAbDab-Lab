from thera_curator.db import Database
from thera_curator.exporter import export_record
from thera_curator.workbook import export_database_workbook,inspect_workbook

def test_record_and_workbook_exports(tmp_path):
    db=Database(tmp_path/'db.sqlite'); rec=db.get_record('avrukibart',False); h=export_record(rec,tmp_path/'a.html'); j=export_record(rec,tmp_path/'a.json'); x=export_database_workbook(db,tmp_path/'out.xlsx'); assert h.exists() and j.exists() and x.exists(); assert inspect_workbook(x)['schema_ok']; db.close()
