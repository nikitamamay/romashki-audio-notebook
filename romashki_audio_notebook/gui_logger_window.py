import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import io
import sys

from .gui_def import *
from .gui_elided_label import ElidableLabel


class LoggerStringIO(io.StringIO):
    def __init__(
            self,
            oldfile: typing.TextIO|None,
            callback: typing.Callable[[str], typing.Any],
            do_duplicate: bool = True,
            ) -> None:
        super().__init__()
        self._callback: typing.Callable[[str], typing.Any] = callback
        self._oldfile: typing.TextIO|None = oldfile
        self._do_duplicate: bool = do_duplicate and self._oldfile is not None

    def write(self, s: str) -> int:
        self._callback(s)
        if self._do_duplicate and self._oldfile is not None:
            self._oldfile.write(s)
        return super().write(s)


class LoggerWidget(QtWidgets.QWidget):
    append_text_request = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super().__init__(parent)

        self._corner_btn = QtWidgets.QToolButton()
        self._corner_btn.setToolTip("Open/close output log")
        self._corner_btn.setIcon(QtGui.QIcon(ICON_TERMINAL))
        self._corner_btn.clicked.connect(self.toggle)

        self._te = QtWidgets.QPlainTextEdit()
        set_monospace_font(self._te.font, self._te.setFont, 10)
        self._te.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)

        self._label_last_line = ElidableLabel()
        set_monospace_font(self._label_last_line.font, self._label_last_line.setFont, 10)

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0,0,0,0)
        self._layout.setSpacing(3)
        self._layout.addWidget(self._te, 0, 0)
        self._layout.addWidget(self._label_last_line, 0, 0)
        self._layout.addWidget(self._corner_btn, 0, 1, QtCore.Qt.AlignmentFlag.AlignBottom)
        self.setLayout(self._layout)

        self.setMinimumHeight(16)

        self._stdout_old = None
        self._stderr_old = None

        self._collapsed: bool = False
        self._last_line: str = ""

        self.append_text_request.connect(self.append_text)

        self.set_collapsed_state(True)

    def __del__(self):
        if sys.stdout != self._stdout_old:
            sys.stdout = self._stdout_old
        if sys.stderr != self._stderr_old:
            sys.stderr = self._stderr_old

    def redirect_stdout(self):
        self._stdout_old = sys.stdout
        sys.stdout = LoggerStringIO(sys.stdout, self.append_text_request.emit, True)
        self._stderr_old = sys.stderr
        sys.stderr = LoggerStringIO(sys.stderr, self.append_text_request.emit, True)

    def append_text(self, text: str | None) -> None:
        if text is not None:
            self._last_line = self._last_line + text
            for line in reversed(self._last_line.splitlines(True)):
                if line.strip() != "":
                    self._last_line = line.lstrip()
                    break
            # self._stdout_old.write(f"last_line={repr(self._last_line)}\n")

            self._label_last_line.setText(self._last_line)

            self._te.moveCursor(QtGui.QTextCursor.MoveOperation.End);
            self._te.insertPlainText(text);
            self._te.moveCursor(QtGui.QTextCursor.MoveOperation.End);

    def set_collapsed_state(self, state: bool):
        self._collapsed = state
        self.setMaximumHeight(16 if self._collapsed else 10000)
        self._te.setVisible(not self._collapsed)
        self._label_last_line.setVisible(self._collapsed)

    def toggle(self):
        self.set_collapsed_state(not self._collapsed)

