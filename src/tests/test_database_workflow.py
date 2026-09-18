from thera_curator.db import Database

def candidate(name,status='PASS'):
    return {'drug_name':name,'english_description':'immunoglobulin G1-kappa [VH] heavy chain light chain','structure_summary':'G1-kappa','heavy_chain_count':2,'heavy_chain_fasta':'','light_chain_count':2,'light_chain_fasta':'','non_variable_fasta':'','ptms':'','pdf_pages':'1','quality_notes':'','alternative_names':'','literature':'','clinical_trials':'','immunogenicity':'','patent_information':'','external_evidence_notes':'','cas_registry_number':'12345-67-8','sequence_qc_status':'validated' if status=='PASS' else 'REVIEW','parse_status':status,'who_list':'Test','source_pdf_hash':'abc','source_pdf_name':'x.pdf','source_provenance_json':'{}'}

def test_pending_review_persists_and_review_not_autoapproved(tmp_path,monkeypatch):
    monkeypatch.setenv('THERA_CURATOR_DATA_DIR',str(tmp_path))
    p=tmp_path/'db.sqlite'; db=Database(p); sid=db.create_import_session('x.pdf','abc','Test'); db.add_pending_candidates(sid,[candidate('passdrug','PASS'),candidate('reviewdrug','REVIEW')]); db.close()
    db=Database(p); rows=db.pending(sid); assert len(rows)==2; db.approve_all_pass(sid); rows={r['drug_name']:r for r in db.pending(sid)}; assert rows['passdrug']['review_status']=='approved'; assert rows['reviewdrug']['review_status']=='pending'; db.close()

def test_audited_correction_and_merge(tmp_path,monkeypatch):
    monkeypatch.setenv('THERA_CURATOR_DATA_DIR',str(tmp_path))
    db=Database(tmp_path/'db.sqlite'); sid=db.create_import_session('x.pdf','abc','Test'); db.add_pending_candidates(sid,[candidate('newdrug','PASS')]); c=db.pending(sid)[0]; db.correct_candidate_field(c['id'],'cas_registry_number','99999-99-9','checked against source','1'); hist=db.correction_history('newdrug'); assert hist and hist[0]['original_value']=='12345-67-8'; db.set_candidate_review(c['id'],'approved'); stats=db.merge_approved(sid); assert stats['added']==1; assert db.get_record('newdrug',False)['cas_registry_number']=='99999-99-9'; assert list((tmp_path/'backups').glob('*.sqlite')); db.close()
