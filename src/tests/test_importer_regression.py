import json, shutil
from thera_curator.utils import fasta_lengths

def test_pl135_candidate_set_matches_gold(pl135_importer,root):
    names=[e.drug_name for e,d in pl135_importer.antibody_entries()]; gold=[x['drug_name'] for x in json.loads((root/'resources'/'golden'/'pl135_reference.json').read_text())]; assert len(names)==70; assert set(names)==set(gold)

def test_pl129_generalises_and_controls(pl129_importer):
    names=[e.drug_name for e,d in pl129_importer.antibody_entries()]; assert 'abiprubart' in names; assert 'verekitug' in names; assert len(names)>40

def test_avrukibart_native_residue_qc(pl135_importer):
    for e,d in pl135_importer.antibody_entries():
        if e.drug_name=='avrukibart': r=pl135_importer.parse_candidate(e,d); break
    else: raise AssertionError('avrukibart not found')
    assert r['cas_registry_number']=='3083662-10-3'; assert r['pdf_pages']=='15-17'; assert r['heavy_chain_count']==2 and fasta_lengths(r['heavy_chain_fasta'])==[450,450]; assert r['light_chain_count']==2 and fasta_lengths(r['light_chain_fasta'])==[214,214]; assert r['parse_status']=='PASS'

def test_car_cell_therapy_excluded(pl135_importer):
    names=[e.drug_name for e,d in pl135_importer.antibody_entries()]; assert not any('abroxcabrene' in n for n in names)

def test_actual_local_ocr_path(pl135_importer):
    if not shutil.which('tesseract') or not shutil.which('pdftoppm'): return
    text=pl135_importer.ocr_pages([16],dpi=120); low=text.lower(); assert len(text)>100; assert 'chain' in low or 'sequence' in low

def test_golden_fixture_reconciliation_is_exact(pl135_importer,root):
    got={x['drug_name']:x for x in pl135_importer.parse(use_golden_fixture=True)}; exp={x['drug_name']:x for x in json.loads((root/'resources'/'golden'/'pl135_reference.json').read_text())}; assert set(got)==set(exp)
    fields=['english_description','cas_registry_number','pdf_pages','heavy_chain_count','light_chain_count','heavy_chain_fasta','light_chain_fasta','non_variable_fasta','ptms','structure_summary','sequence_qc_status']
    for name in exp:
        for f in fields: assert got[name][f]==exp[name][f],(name,f)
