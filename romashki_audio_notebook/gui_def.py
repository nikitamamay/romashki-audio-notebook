
import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import os

from . import PACKAGE_DIR


MONOSPACE_FONT_FAMILIES = ['Liberation Mono', 'Consolas', 'Courier New', 'monospace']


ICON_APP = os.path.join(PACKAGE_DIR, "icons/app.svg")
ICON_LOADING = os.path.join(PACKAGE_DIR, "icons/loading.svg")
ICON_READY_FOR_RECORD = os.path.join(PACKAGE_DIR, "icons/ready_for_record.svg")  # for mic button
ICON_STOP = os.path.join(PACKAGE_DIR, "icons/stop.svg")  # for mic button
ICON_RECORDING = os.path.join(PACKAGE_DIR, "icons/recording.svg")
ICON_ANALYZING = os.path.join(PACKAGE_DIR, "icons/analyzing.svg")
ICON_RECORDING_AND_ANALYZING = os.path.join(PACKAGE_DIR, "icons/recording_and_analyzing.svg")
ICON_SETTINGS = os.path.join(PACKAGE_DIR, "icons/settings.svg")
ICON_TERMINAL = os.path.join(PACKAGE_DIR, "icons/terminal.svg")
ICON_INFO = os.path.join(PACKAGE_DIR, "icons/information.svg")
ICON_RECORDS_LIST = os.path.join(PACKAGE_DIR, "icons/records_list.svg")

ICON_RECORD_SYMBOL = os.path.join(PACKAGE_DIR, "icons/record_symbol.png")



def set_monospace_font(
        func_get_font: typing.Callable[[], QtGui.QFont],
        func_set_font: typing.Callable[[QtGui.QFont], typing.Any],
        pixel_size: int|None = None,
    ) -> None:
    font = func_get_font()
    font.setFamilies(MONOSPACE_FONT_FAMILIES)
    if pixel_size is not None:
        font.setPixelSize(pixel_size)
    func_set_font(font)

