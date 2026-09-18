# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
root=Path(SPECPATH)

datas=[
    (str(root/'resources'/'seed.sqlite'),'resources'),
    (str(root/'resources'/'app_icon.ico'),'resources'),
    (str(root/'resources'/'golden'/'pl135_reference.json'),'resources/golden'),
    (str(root/'resources'/'golden'/'pl135_pdf_sha256.txt'),'resources/golden'),
]
binaries=[]

tess=root/'vendor'/'tesseract'
if (tess/'tesseract.exe').exists():
    for f in tess.rglob('*'):
        if f.is_file(): datas.append((str(f),str(Path('tesseract')/f.relative_to(tess).parent)))
pop=root/'vendor'/'poppler'
if pop.exists() and any(f.name.lower()=='pdftoppm.exe' for f in pop.rglob('*')):
    for f in pop.rglob('*'):
        if f.is_file(): datas.append((str(f),str(Path('poppler')/f.relative_to(pop).parent)))

a=Analysis(
    ['run_curator.py'], pathex=[str(root)], binaries=binaries, datas=datas,
    hiddenimports=['PyQt5','PyQt5.QtCore','PyQt5.QtGui','PyQt5.QtWidgets','PyQt5.QtPrintSupport','pypdf','openpyxl','rapidfuzz','requests','PIL'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['PySide6'], noarchive=False,
)
pyz=PYZ(a.pure)
exe=EXE(
    pyz,a.scripts,[],exclude_binaries=True,name='Thera-SAbDab_WHO_INN_Curator',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    icon=str(root/'resources'/'app_icon.ico'),
)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,upx_exclude=[],name='Thera-SAbDab_WHO_INN_Curator')
