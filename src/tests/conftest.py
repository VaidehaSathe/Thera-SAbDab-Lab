import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from thera_curator.importer import WHOImporter

@pytest.fixture(scope='session')
def root(): return ROOT
@pytest.fixture(scope='session')
def pl135(root): return root/'resources'/'golden'/'pl135.pdf'
@pytest.fixture(scope='session')
def pl129(root): return root/'resources'/'golden'/'pl129.pdf'
@pytest.fixture(scope='session')
def gold_xlsx(root): return root/'resources'/'golden'/'pl135_gold.xlsx'
@pytest.fixture(scope='session')
def pl135_importer(pl135):
    imp=WHOImporter(pl135); imp.antibody_entries(); return imp
@pytest.fixture(scope='session')
def pl129_importer(pl129):
    imp=WHOImporter(pl129); imp.antibody_entries(); return imp
