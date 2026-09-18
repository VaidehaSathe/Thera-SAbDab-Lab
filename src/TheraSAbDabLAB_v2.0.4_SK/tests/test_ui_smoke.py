import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from thera_curator.qt_compat import QtWidgets
from thera_curator.db import Database
from thera_curator.ui import MainWindow

def test_ui_launch_and_search(tmp_path):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([]); db=Database(tmp_path/'db.sqlite'); w=MainWindow(db); w.search_edit.setText('avrukibart'); w.run_search(); assert w.search_results.rowCount()>=1; assert w.nav[6].text()=='Pending Import Review'; w.close(); db.close()
