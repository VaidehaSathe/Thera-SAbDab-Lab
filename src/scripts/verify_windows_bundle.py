from __future__ import annotations
import argparse,sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('bundle',type=Path);ap.add_argument('--allow-external-ocr',action='store_true');a=ap.parse_args();b=a.bundle
    exe=b/'Thera-SAbDab_WHO_INN_Curator.exe'; missing=[]
    if not exe.exists():missing.append(str(exe))
    if not (b/'resources'/'seed.sqlite').exists():missing.append('resources/seed.sqlite')
    if not (b/'resources'/'golden'/'pl135_reference.json').exists():missing.append('resources/golden/pl135_reference.json')
    if not a.allow_external_ocr:
        if not (b/'tesseract'/'tesseract.exe').exists():missing.append('tesseract/tesseract.exe')
        if not ((b/'poppler'/'Library'/'bin'/'pdftoppm.exe').exists() or (b/'poppler'/'bin'/'pdftoppm.exe').exists()):missing.append('poppler pdftoppm.exe')
    if missing:
        print('Bundle verification FAILED:',*missing,sep='\n - ');return 2
    print('Bundle verification PASSED');return 0
if __name__=='__main__':raise SystemExit(main())
