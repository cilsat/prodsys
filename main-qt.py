#!/usr/bin/python

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import pparser as pp

class Example(QMainWindow):

    def __init__(self):
        super(Example, self).__init__()
        self.initUI()

    def initUI(self):

        """
        Main Window global parameters
        """
        self.mainWidth = 1280
        self.mainHeight = 640
        self.main = QLabel()
        grid = QGridLayout()
        self.main.setLayout(grid)

        self.fileFacts = '/home/cilsat/dev/rpp/prodsys/brick-memory'
        self.fileRules = '/home/cilsat/dev/rpp/prodsys/brick-rules'

        self.mainRules = QTextEdit()
        self.mainRules.setGeometry(5, 5, 500, 300)
        self.mainRules.setFont(QFont('Monospace', 12))

        self.mainFacts = QTextEdit()
        self.mainFacts.setGeometry(5, 5, 500, 300)
        self.mainFacts.setFont(QFont('Monospace', 12))

        self.mainConsole = QTextEdit()
        self.mainConsole.setGeometry(5, 5, 500, 300)
        self.mainConsole.setFont(QFont('Monospace', 12))
        self.mainConsole.setReadOnly(True)

        self.buttonRun = QPushButton('Run', self)
        self.label = QLabel(self)
        grid.addWidget(self.buttonRun, 1, 0)
        grid.addWidget(self.label)

        grid.addWidget(self.mainRules, 1, 0)
        grid.addWidget(self.mainFacts, 2, 0)
        grid.addWidget(self.mainConsole, 0, 1, 3, 1)
        """
        Menu Bar
        """

        # FILE MENU
        openRules = QAction('Rules', self)
        openRules.setShortcut('Ctrl+R')
        openRules.setStatusTip('Open Rules')
        openRules.triggered.connect(self.showRulesDialog)

        openFacts = QAction('Facts', self)
        openFacts.setShortcut('Ctrl+F')
        openFacts.setStatusTip('Open Facts')
        openFacts.triggered.connect(self.showFactsDialog)

        saveRules = QAction('Save Rules', self)
        saveRules.triggered.connect(self.saveRules)

        saveFacts = QAction('Save Facts', self)
        saveRules.triggered.connect(self.saveFacts)

        exitAction = QAction('Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        runMatcher = QAction('Run', self)
        runMatcher.triggered.connect(lambda:self.runMatcher())

        # MENU BAR
        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(openRules)
        fileMenu.addAction(openFacts)
        fileMenu.addAction(saveRules)
        fileMenu.addAction(saveFacts)
        fileMenu.addAction(exitAction)

        processMenu = menubar.addMenu('&Process')
        processMenu.addAction(runMatcher)

        """
        Toolbar, Status Bar, Tooltip
        """
        self.statusBar().showMessage('Ready')

        QToolTip.setFont(QFont('SansSerif', 10))
        #self.setToolTip('This is a <b>QWidget</b> widget')

        """
        Displaying
        """

        self.setGeometry(12, 30, self.mainWidth, self.mainHeight+80)
        self.setWindowTitle('Prodsys')
        self.setWindowIcon(QIcon('res/web.png'))

        self.setCentralWidget(self.main)

        self.main.setGeometry(QRect(0, 80, self.mainWidth, self.mainHeight))
        #self.mainAfter.setGeometry(QRect(self.mainWidth/2, 80, self.mainWidth/2, self.mainHeight))

        self.show()

    def saveFacts(self):
        txt = str(self.mainFacts.toPlainText())
        with open(self.fileFacts, 'w') as f:
            f.write(txt)

    def saveRules(self):
        txt = str(self.mainRules.toPlainText())
        with open(self.fileRules, 'w') as f:
            f.write(txt)

    def showRulesDialog(self):
        fname = QFileDialog.getOpenFileName(self, 'Open rules', '/home/cilsat/dev/rpp/prodsys')

        if fname[0]:
            self.fileRules = fname[0]
            rules = open(fname[0]).read()
            print(rules)
            self.mainRules.setText(rules)
            self.rules = rules

    def showFactsDialog(self):
        fname = QFileDialog.getOpenFileName(self, 'Open facts', '/home/cilsat/dev/rpp/prodsys')

        if fname[0]:
            self.fileFacts = fname[0]
            facts = open(fname[0]).read()
            print(facts)
            self.mainFacts.setText(facts)
            self.facts = facts

    def runMatcher(self):
        rules = str(self.mainRules.toPlainText())
        facts = str(self.mainFacts.toPlainText())

        out = str(pp.test_loop(rules, facts))
        self.mainConsole.setText(out)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())
