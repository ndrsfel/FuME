#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from PyQt5 import QtWidgets

from fume.ui.log import Ui_Log


class LogDialog(QtWidgets.QDialog, Ui_Log):
    def __init__(self, parent=None):
        super(LogDialog, self).__init__(parent)
        self.setupUi(self)
        self.__counter = 1

    def add(self, text):
        if len(text) > 55:
            self.add(text[0:55])
            self.add(text[55:])
        else:
            time = datetime.datetime.now().strftime("%H:%M:%S")
            self.plainTextEdit.appendPlainText("[%s] %s Uhr: %s" % (self.__counter, time, text))
            self.parent().statusBar.showMessage("%s" % text)
            self.__counter += 1
