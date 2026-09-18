from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from thera_curator.importer import WHOImporter
from thera_curator.utils import fasta_lengths

FIELDS=['drug_name','english_description','cas_registry_number','pdf_pages','heavy_chain_count','light_chain_count','heavy_chain_fasta','light_chain_fasta','non_variable_fasta','ptms','structure_summary','sequence_qc_status']

def compare(pdf:Path,golden:Path,use_fixture=False):
    expected=json.loads(golden.read_text(encoding='utf-8')); exp={x['drug_name']:x for x in expected}
    imp=WHOImporter(pdf); got=imp.parse(enable_ocr=False,use_golden_fixture=use_fixture); gd={x['drug_name']:x for x in got}
    result={'pdf':str(pdf),'who_list':imp.who_list,'expected_records':len(exp),'detected_records':len(gd),'missing':sorted(set(exp)-set(gd)),'extra':sorted(set(gd)-set(exp)),'field_matches':{},'discrepancies':[]}
    for f in FIELDS:
        n=0; total=0
        for name in sorted(set(exp)&set(gd)):
            total+=1
            a=exp[name].get(f,'');b=gd[name].get(f,'')
            if a==b:n+=1
            elif len(result['discrepancies'])<250: result['discrepancies'].append({'drug':name,'field':f,'expected':str(a)[:220],'actual':str(b)[:220]})
        result['field_matches'][f]={'matched':n,'total':total}
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('pdf',type=Path);ap.add_argument('--golden',type=Path,default=ROOT/'resources'/'golden'/'pl135_reference.json');ap.add_argument('--fixture',action='store_true');ap.add_argument('--out',type=Path);a=ap.parse_args();r=compare(a.pdf,a.golden,a.fixture);txt=json.dumps(r,ensure_ascii=False,indent=2);print(txt);a.out and a.out.write_text(txt,encoding='utf-8')
