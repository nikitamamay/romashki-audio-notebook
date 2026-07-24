import typing
import traceback

from PyQt5 import QtCore, QtWidgets, QtGui

import os
import sys


from . import audio
from . import tts_whisper
from . import config
from . import gui

try:
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(gui.ICON_APP))

    window = gui.MainWindow()
    window.show()
    # window.restore_geometry_from_config()

    app.exec()

except Exception as e:
    print(traceback.format_exc())
    print(f"{e.__class__.__name__}: {e}")
    sys.exit(1)
