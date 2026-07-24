from PyQt5 import QtGui, QtCore, QtWidgets


class ElidableLabel(QtWidgets.QLabel):
    def __init__(self, text: str = "", parent = None):
        super().__init__(text, parent)
        self._elidable: bool = True
        self._size_hint = QtCore.QSize(100, self.fontMetrics().height())

    def setElidable(self, r: bool) -> None:
        self._elidable = r

    def elidable(self) -> bool:
        return self._elidable

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        fm = self.fontMetrics()

        if self.elidable():
            text = fm.elidedText(self.text(), QtCore.Qt.TextElideMode.ElideRight, self.width())
            i = text.find("\n")
            if i != -1:
                text = text[:i]
        else:
            text = self.text()

        painter.drawText(QtCore.QRect(QtCore.QPoint(0,0), self.size()), self.alignment(), text)  # | (QtCore.Qt.TextFlag.TextWordWrap * int(self.wordWrap()))

    def minimumSizeHint(self) -> QtCore.QSize:
        fm = self.fontMetrics()
        if self.elidable():
            return QtCore.QSize(fm.width("…"), fm.height())
        else:
            return QtCore.QSize(fm.width(self.text()), fm.height())

    def sizeHint(self) -> QtCore.QSize:
        return self._size_hint

    def set_size_hint(self, size: QtCore.QSize) -> None:
        self._size_hint.setWidth(size.width())
        self._size_hint.setHeight(size.height())

    def setWordWrap(self, on: bool) -> None:
        raise NotImplementedError()

