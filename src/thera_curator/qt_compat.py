"""Small compatibility layer for the Qt binding used by the desktop UI.

Windows portable builds deliberately use PyQt5 because its wheel layout is
substantially shallower than current PySide6 wheels and therefore works on
Windows systems where long-path support is disabled.  PySide6 remains a
fallback for development environments that already provide it.
"""
try:
    from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport
    Signal = QtCore.pyqtSignal
    if not hasattr(QtCore, 'Slot'):
        QtCore.Slot = QtCore.pyqtSlot
    BINDING = 'PyQt5'
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets, QtPrintSupport
    Signal = QtCore.Signal
    BINDING = 'PySide6'
