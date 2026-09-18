from __future__ import annotations
import sys
from .qt_compat import QtWidgets,QtGui
from .db import Database
from .constants import APP_NAME
from .paths import resource_path
from .ui import MainWindow

def main():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setOrganizationName('Thera-SAbDab')
    icon=resource_path('app_icon.ico')
    if icon.exists(): app.setWindowIcon(QtGui.QIcon(str(icon)))
    db=Database(); win=MainWindow(db); win.show(); code=app.exec() if hasattr(app,'exec') else app.exec_(); db.close(); return code
