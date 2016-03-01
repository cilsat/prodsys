#!/usr/bin/python

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import *

import pparser as pp

class Example(QMainWindow):

    def __init__(self):
        super(Example, self).__init__()
        self.initUI()
        self.facts = ''
        self.rules = ''

    def initUI(self):

        """
        Main Window global parameters
        """
        self.mainWidth = 1280
        self.mainHeight = 640
        self.main = QLabel()
        grid = QGridLayout()
        self.main.setLayout(grid)

        self.mainRules = QLabel('Rules')
        self.mainRules.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.mainRules.setWordWrap(True)
        self.mainRules.setFont(QFont('Monospace', 10))

        self.mainFacts = QLabel('Facts')
        self.mainFacts.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.mainFacts.setWordWrap(True)
        self.mainFacts.setFont(QFont('Monospace', 10))

        self.mainConsole = QLabel('Console')
        self.mainConsole.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.mainConsole.setWordWrap(True)
        self.mainConsole.setFont(QFont('Monospace', 10))

        grid.addWidget(self.mainRules, 0, 0)
        grid.addWidget(self.mainFacts, 0, 1)
        grid.addWidget(self.mainConsole, 0, 2)

        """
        Menu Bar
        """

        # FILE MENU
        openRules = QAction('Open', self)
        openRules.setShortcut('Ctrl+R')
        openRules.setStatusTip('Open Rules')
        openRules.triggered.connect(self.showRulesDialog)

        openFacts = QAction('Open', self)
        openFacts.setShortcut('Ctrl+F')
        openFacts.setStatusTip('Open Facts')
        openFacts.triggered.connect(self.showFactsDialog)

        exitAction = QAction('Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        runMatcher = QAction('Run', self)
        runMatcher.triggered.connect

        # MENU BAR
        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(openRules)
        fileMenu.addAction(openFacts)
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

    def showRulesDialog(self):
        fname = QFileDialog.getOpenFileName(self, 'Open rules', '/home/cilsat/dev/rpp/prodsys')

        if fname[0]:
            rules = open(fname[0]).read()
            self.mainRules.setText(rules)
            self.rules = rules

    def showFactsDialog(self):
        fname = QFileDialog.getOpenFileName(self, 'Open facts', '/home/cilsat/dev/rpp/prodsys')

        if fname[0]:
            facts = open(fname[0]).read()
            self.mainFacts.setText(facts)
            self.facts = facts

    def patternMatch(self, rules, facts):
        a, t = pp.parse_rules(rules)
        t = pp.parse_mem(facts, t)
        self.mainConsole.setText(pp.match_antecedents(a, t))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())
