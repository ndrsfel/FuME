#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
import shutil
import sys

import appdirs
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtSql
from PyQt5 import QtWidgets

from fume.gui.FilterDialog import FilterDialog
from fume.gui.LogDialog import LogDialog
from fume.gui.SettingsDialog import SettingsDialog
from fume.threads.DownloadProcessor import DownloadProcessor
from fume.threads.ReserveProcessor import ReserveProcessor
from fume.ui.mainwindow import Ui_MainWindow


class CustomSqlModel(QtSql.QSqlQueryModel):
    # adapted: https://stackoverflow.com/a/44104745
    def __init__(self, parent=None):
        QtSql.QSqlQueryModel.__init__(self, parent=parent)
        self.defaultFilter = 'select * from calendar'
        self.setQuery(self.defaultFilter)

    def data(self, item, role):
        # Changing color if "reserved" is True
        if role == QtCore.Qt.BackgroundRole:
            if QtSql.QSqlQueryModel.data(self, self.index(item.row(), 7), QtCore.Qt.DisplayRole) == 1:
                return QtGui.QBrush(QtGui.QColor.fromRgb(176, 234, 153))
            if QtSql.QSqlQueryModel.data(self, self.index(item.row(), 7), QtCore.Qt.DisplayRole) == 2:
                return QtGui.QBrush(QtGui.QColor.fromRgb(234, 189, 190))

        # Changing value 0=False, 1=True - deprecated
        # if role == QtCore.Qt.DisplayRole:
        #     if item.column() == 7:
        #         if QtSql.QSqlQueryModel.data(self, item, QtCore.Qt.DisplayRole) == 1:
        #             return True
        #         else:
        #             return False

        return QtSql.QSqlQueryModel.data(self, item, role)

    def setFilter(self, text):
        self.setQuery(self.defaultFilter + ' WHERE ' + text + ' order by match_date asc')

    def select(self):
        queryStr = self.query().executedQuery()
        self.query().clear()
        self.setQuery(queryStr)


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.label.setPixmap(QtGui.QPixmap(self.get_pathToTemp("bin/header_klein.png")))
        self.statusBar.showMessage("Willkommen!")

        self.read_settings()

        self.logDialog = LogDialog(self)
        self.settingsDialog = SettingsDialog(self)

        if not self.set_database():
            sys.exit(1)

        self.set_connections()
        self.set_tableStyleSheet()
        self.set_tableView()

        self.matchFilterString = ''
        self.regionFilterString = ''
        self.dateFilterString = ''

        self.set_comboBoxItems()
        self.date_changed()  # set date-range
        self.set_listWidget()
        self.comboBox_changed()  # set region

        # last tweaks on tableView before show()
        self.tableView.hideColumn(7)
        self.tableView.hideColumn(8)

        widths = [72, 220, 125, 220, 220, 60, 140]
        for i, d in enumerate(widths):
            self.tableView.setColumnWidth(i, d)

        self.show()

    def set_connections(self):
        self.pushButton.clicked.connect(self.showFilterDialog)
        self.pushButton_2.clicked.connect(self.invertSelection)
        self.pushButton_3.clicked.connect(self.logDialog.show)
        self.pushButton_4.clicked.connect(self.settingsDialog.show)
        self.pushButton_5.clicked.connect(self.download_match)
        self.pushButton_9.clicked.connect(self.listWidget.selectionModel().clearSelection)
        self.pushButton_10.clicked.connect(self.restoreSelection)
        self.pushButton_11.clicked.connect(self.reserve_match)

        self.dateEdit_3.dateChanged.connect(self.date_changed)
        self.dateEdit_4.dateChanged.connect(self.date_changed)
        self.lineEdit.textChanged.connect(self.lineEdit_changed)
        self.listWidget.itemSelectionChanged.connect(self.itemSelection_changed)
        self.checkBox_2.stateChanged.connect(self.checkBox_changed)
        self.comboBox.currentTextChanged.connect(self.comboBox_changed)

    def set_database(self):
        self.db = QtSql.QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName(self.dbPath)

        if not self.db.open():
            QtWidgets.QMessageBox.critical(None, QtWidgets.qApp.tr("Datenbank nicht verfügbar"),
                                           QtWidgets.qApp.tr(
                                               "Es konnte keine Verbindung zur Datenbank hergestellt werden.\n"
                                               "Dieses Programm benötigt SQLite support. Bitte lesen Sie "
                                               "die Qt SQL Treiber Dokumentation für mehr Informationen\n\n"
                                               "Klicke Abbrechen zum beenden."),
                                           QtWidgets.QMessageBox.Cancel)
            return False
        else:
            return True

    def set_tableStyleSheet(self):
        self.tableViewStyle = """
                                QTableView
                                {
                                    background-color: white;
                                    gridline-color: #545454;
                                    color: black;
                                    alternate-background-color: #eeeeee;
                                }
                                """
        self.setStyleSheet(self.tableViewStyle)

    def set_tableView(self):
        self.sqlmodel_calendar = CustomSqlModel()
        labels = ['ID', 'Liga', 'Datum/Uhrzeit', 'Heim', 'Gast', 'Tore', 'Region']
        for i in range(len(labels)):
            self.sqlmodel_calendar.setHeaderData(i, QtCore.Qt.Horizontal, labels[i])

        self.tableView.setModel(self.sqlmodel_calendar)
        # self.tableView_2.resizeColumnsToContents()
        self.tableView.setAlternatingRowColors(True)

    def set_comboBoxItems(self):
        # 18.05.2017
        items = ['Alle', 'Baden', 'Bayliga', 'Berlin', 'Brandenburg', 'Darmstadt', 'Hamburg', 'Lueneburg', 'Luxemburg',
                 'Mecklenburg-Vorpommern', 'Mittelbaden', 'Mittelfranken', 'Mittelhessen', 'Mittelrhein', 'Nahe',
                 'Niederbayern', 'Niederrhein', 'Nordhessen', 'Nordwest', 'Oberbayern', 'Oberfranken', 'Oberpfalz',
                 'Oberschwaben', 'Ostwestfalen', 'Rheinhessen', 'Rheinland', 'Ruhrgebiet', 'Saarland', 'Sachsen',
                 'Sachsen-Anhalt', 'Schleswig-Holstein', 'Schwaben', 'Stuttgart', 'Suedbaden', 'Suedwest',
                 'Suedwestfalen', 'Thueringen', 'Weser-Ems', 'Westpfalz', 'Westrhein', 'Wiesbaden']
        self.comboBox.addItems(items)
        self.comboBox.setCurrentText(self.settings.value('region', 'Alle'))

    def set_listWidget(self):
        # Sets the default values if the fume is closed without any elements in listWidget
        # Important: These values are preset and defined in .ui file
        defaults = ['Noch keine Mannschaften hinzugefügt...', 'Region wählen und unten links auf konfigurieren klicken']
        elements = self.settings.value('filter', defaults)
        if elements != defaults and len(elements) != 0:
            self.listWidget.clear()
            for i in elements:
                item = QtWidgets.QListWidgetItem()
                item.setText(i[0])
                item.setData(QtCore.Qt.UserRole, i[1])
                self.listWidget.addItem(item)

        # Loading selected items
        for i in self.settings.value('filter_calendar', []):
            for j in self.listWidget.findItems(i, QtCore.Qt.MatchExactly):
                j.setSelected(True)

        self.itemSelection_changed()
        self.current_selection = [x for x in self.listWidget.selectedItems()]  # for restoring selection

    def get_filterString(self):
        # Only join not empty filter strings
        str = ' AND '.join(filter(None, [self.dateFilterString, self.matchFilterString, self.regionFilterString]))
        # print(str)
        return str

    def get_pathToTemp(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def hideAll(self):
        for i in range(0, self.listWidget.count()):
            self.listWidget.item(i).setHidden(True)

    def showAll(self):
        for i in range(0, self.listWidget.count()):
            self.listWidget.item(i).setHidden(False)

    def write_settings(self):
        self.settings.setValue('date_from_calendar', self.dateEdit_3.date())
        self.settings.setValue('date_to_calendar', self.dateEdit_4.date())
        self.settings.setValue('filter_calendar', [x.text() for x in self.listWidget.selectedItems()])
        self.settings.setValue('region', self.comboBox.currentText())
        self.settings.setValue('filter', [[self.listWidget.item(i).text(),
                                           self.listWidget.item(i).data(QtCore.Qt.UserRole)]
                                          for i in range(self.listWidget.count())])

    def read_settings(self):
        self.settings = QtCore.QSettings('fume', 'Match-Explorer')
        now = datetime.datetime.now()
        self.dateEdit_3.setDate(self.settings.value('date_from_calendar', QtCore.QDate(now.year, now.month, now.day)))
        self.dateEdit_4.setDate(self.settings.value('date_to_calendar', QtCore.QDate(now.year, now.month, now.day)))

        # dbPaths
        # Windows: C:\Documents and Settings\<User>\Application Data\Local Settings\FuME\FuME
        # macOS: /Users/<User>/Library/Application Support/FuME
        userDataDir = appdirs.user_data_dir('FuME', 'FuME')
        src = self.get_pathToTemp(os.path.join('db', 'sql_default.db'))
        dst = os.path.join(userDataDir, 'sql.db')
        if not os.path.exists(userDataDir):
            os.makedirs(userDataDir)
            shutil.copy(src, dst)
        self.dbPath = dst

        # TODO: Include Chrome to freezed apps and add headless support

    def closeEvent(self, QCloseEvent):
        self.write_settings()
        self.db.close()

    @QtCore.pyqtSlot()
    def showFilterDialog(self):
        if self.comboBox.currentText() == 'Alle':
            QtWidgets.QMessageBox.warning(self, QtWidgets.qApp.tr("Region wählen"),
                                          QtWidgets.qApp.tr("Bitte zuerst eine Region wählen.\n\n"
                                                            "Ok drücken um fortzufahren."),
                                          QtWidgets.QMessageBox.Ok)
        else:
            self.filterWindow = FilterDialog(self)
            self.filterWindow.show()

    @QtCore.pyqtSlot()
    def date_changed(self):
        date_from = self.dateEdit_3.date()
        date_to = self.dateEdit_4.date()

        if date_from > date_to:
            date_to = date_from
            self.dateEdit_4.setDate(date_to)
        elif date_to < date_from:
            date_from = date_to
            self.dateEdit_3.setDate(date_from)

        date_from_str = date_from.toString("yyyy-MM-dd")
        date_to_str = date_to.addDays(1).toString("yyyy-MM-dd")  # Upper limit exclusive in BETWEEN statement

        self.dateFilterString = 'match_date BETWEEN "%s" AND "%s"' % (date_from_str, date_to_str)
        self.sqlmodel_calendar.setFilter(self.get_filterString())
        self.sqlmodel_calendar.select()
        # self.tableView_2.resizeColumnsToContents()

    @QtCore.pyqtSlot(str)
    def lineEdit_changed(self, text):
        # adapted: http://stackoverflow.com/a/32336368/6304901
        self.hideAll()

        for i in self.listWidget.findItems(text, QtCore.Qt.MatchContains):
            if self.comboBox.currentText() == i.data(QtCore.Qt.UserRole):
                if self.checkBox_2.isChecked():
                    if i in self.listWidget.selectedItems():
                        i.setHidden(False)
                else:
                    i.setHidden(False)

    @QtCore.pyqtSlot(int)
    def checkBox_changed(self, int):
        if int:  # 1: checkBox checked
            self.hideAll()
            for i in self.listWidget.selectedItems():
                i.setHidden(False)
        else:
            self.showAll()

        self.lineEdit_changed(self.lineEdit.text())

    @QtCore.pyqtSlot()
    def comboBox_changed(self):
        region = self.comboBox.currentText()
        if region == 'Alle':
            self.regionFilterString = ''
        else:
            self.regionFilterString = 'region = "%s"' % region

        self.sqlmodel_calendar.setFilter(self.get_filterString())
        self.sqlmodel_calendar.select()
        # self.tableView_2.resizeColumnsToContents()

        self.showAll()
        if region != 'Alle':  # else do nothing (show all)
            for i in range(self.listWidget.count()):
                itemData = self.listWidget.item(i).data(QtCore.Qt.UserRole)
                if itemData != region and itemData != None:
                    self.listWidget.item(i).setHidden(True)

    @QtCore.pyqtSlot()
    def itemSelection_changed(self):
        self.selection = self.listWidget.selectedItems()
        if self.selection != []:
            self.matchFilterString = '(' + ' OR '.join(['home = "%s"' % i.text() for i in self.selection]) + ')'
        else:  # show all
            self.matchFilterString = ''

        self.sqlmodel_calendar.setFilter(self.get_filterString())
        self.sqlmodel_calendar.select()
        # self.tableView_2.resizeColumnsToContents()
        self.label_6.setText('%s' % len(self.selection))
        self.label_7.setText('%s' % self.sqlmodel_calendar.rowCount())

    @QtCore.pyqtSlot()
    def restoreSelection(self):
        self.listWidget.selectionModel().clearSelection()

        for x in self.current_selection:  # Current selection saved during startup
            self.listWidget.setCurrentItem(x, QtCore.QItemSelectionModel.Select)

    @QtCore.pyqtSlot()
    def invertSelection(self):
        for i in range(self.listWidget.count()):
            if not self.listWidget.item(i).isHidden():
                self.listWidget.setCurrentRow(i, QtCore.QItemSelectionModel.Toggle)

    @QtCore.pyqtSlot()
    def reserve_match(self):
        selected = []
        indexes = self.tableView.selectedIndexes()
        for index in sorted(indexes):
            match_id = self.tableView.model().record(index.row()).value('match_id')
            match_date = self.tableView.model().record(index.row()).value('match_date')
            home = self.tableView.model().record(index.row()).value('home')
            guest = self.tableView.model().record(index.row()).value('guest')
            selected.append({'match_id': match_id, 'match_date': match_date, 'home': home, 'guest': guest})

        cookies = self.settings.value('cookie', '')
        if cookies == '':
            QtWidgets.QMessageBox.information(self, QtWidgets.qApp.tr("Cookies"),
                                              QtWidgets.qApp.tr("Keine Cookies vorhanden.\n\n"
                                                                "Erstelle jetzt deine Cookies in den Einstellungen"),
                                              QtWidgets.QMessageBox.Ok)
            return

        options = {
            'cookie': cookies,
            'selected': selected,
            'database-path': self.dbPath,
            'parent': self
        }
        self.reserveProcess = ReserveProcessor(options)

        # Connections
        self.reserveProcess.loggerSignal.connect(self.logDialog.add)
        self.reserveProcess.statusBarSignal.connect(self.statusBar.showMessage)
        self.reserveProcess.alreadyReservedSignal.connect(self.alreadyReservedMessageBox)
        self.reserveProcess.finished.connect(self.sqlmodel_calendar.select)

        self.reserveProcess.start()

    @QtCore.pyqtSlot(str)
    def alreadyReservedMessageBox(self, text):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Information)
        msgBox.setBaseSize(QtCore.QSize(600, 300))
        msgBox.setText("Bereits reservierte Spiele gefunden!")
        msgBox.setInformativeText(text)
        msgBox.exec()

    @QtCore.pyqtSlot()
    def download_match(self):
        options = {
            'region': self.comboBox.currentText(),
            'date-from': self.dateEdit_3.date(),
            'date-to': self.dateEdit_4.date(),
            'database-path': self.dbPath,
            'parent': self
        }

        if self.comboBox.currentText() == 'Alle':
            QtWidgets.QMessageBox.warning(self, QtWidgets.qApp.tr("Region wählen"),
                                          QtWidgets.qApp.tr("Bitte zuerst eine Region wählen.\n\n"
                                                            "Ok drücken um fortzufahren."),
                                          QtWidgets.QMessageBox.Ok)
            return
        else:
            self.downloadProcessor = DownloadProcessor(options)

        # Connections
        self.downloadProcessor.finished.connect(self.sqlmodel_calendar.select)
        # self.downloadProcessor.finished.connect(self.tableView_2.resizeColumnsToContents)
        self.downloadProcessor.loggerSignal.connect(self.logDialog.add)
        self.downloadProcessor.statusBarSignal.connect(self.statusBar.showMessage)

        self.downloadProcessor.start()


def run():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == '__main__':
    run()
