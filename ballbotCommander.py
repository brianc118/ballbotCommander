#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import serial
from serial import Serial
import serial.tools.list_ports
import pyqtgraph as pg
#from pyqtgraph.Qt import QtCore, QtGui
import PyQt4.QtCore as QtCore
from PyQt4.QtCore import Qt, QThread, SIGNAL, QTimer, QDateTime
import PyQt4.QtGui as QtGui
import os
import time

about = "ballbotCommander by Brian Chen"
version = "0.1"

pg.mkQApp()
path = os.path.dirname(os.path.abspath(__file__))
uiFile = os.path.join(path, 'ballbotCommander.ui')
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(uiFile)

class AboutDialog(QtGui.QDialog):
	def __init__(self, parent = None):
		super(AboutDialog, self).__init__(parent)
		self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
		layout = QtGui.QVBoxLayout(self)

		self.setFixedSize(300,80)
		self.label = QtGui.QLabel(self)
		self.label.setText(about)

		self.label2 = QtGui.QLabel(self)
		self.label2.setText("Version %s" % version)
		layout.addWidget(self.label)
		layout.addWidget(self.label2)
		

class MainWindow(TemplateBaseClass):  
	procEnd = QtCore.pyqtSignal()
	procSend = QtCore.pyqtSignal(str)

	def __init__(self):
		TemplateBaseClass.__init__(self)
		self.setWindowTitle('ballbotCommander')

		# Create variables
		self.data = []
		self.dataInitialised = False
		self.dataColumns = 0
		self.names = []
		self.nameCheckItems = []
		self.receiveNewDataCnt = 0

		# Remote control
		self.speed = '$'

		# Serial Thread
		self.serThread = None

		# Graph
		self.curves = []
		self.curveStates = []
		self.curveColors = []

		# Creater timer for plotting
		self.plotTimer = QTimer()
		self.plotTimer.timeout.connect(self.plot)

		# Create timer for remote control
		self.remoteTimer = QTimer()
		self.remoteTimer.timeout.connect(self.sendSpeed)

		# Create the main window
		self.ui = WindowTemplate()
		self.ui.setupUi(self)
		self.ui.sendButton.clicked.connect(self.sendMsg)
		self.ui.sendTextBox.returnPressed.connect(self.sendMsg)
		self.actionRefresh = QtGui.QAction('&Refresh', self) 
		self.actionRefresh.triggered.connect(self.listPorts)
		self.ui.menuPorts.triggered.connect(self.listPorts)
		self.ui.menuPorts.addAction(self.actionRefresh)
		self.ui.clearGraphButton.clicked.connect(self.clearPlot)
		self.ui.enableRCCheckBox.toggled.connect(self.toggleRC)
		self.ui.actionAbout.triggered.connect(self.about)
		self.ui.MyPlotWidget.addLegend()

		# Graph listview
		self.listViewModel = QtGui.QStandardItemModel()
		self.ui.listView.setModel(self.listViewModel)

		# Read arrow keys
		self.connect(QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self), QtCore.SIGNAL('activated()'), self.keyUp)
		self.connect(QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self), QtCore.SIGNAL('activated()'), self.keyDown)
		self.connect(QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self), QtCore.SIGNAL('activated()'), self.keyLeft)
		self.connect(QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self), QtCore.SIGNAL('activated()'), self.keyRight)

		self.show()

		self.listPorts()

	def about(self):
		my_dialog = AboutDialog()
		my_dialog.exec_()  # blocks all other windows until this window is closed.		

	def toggleRC(self):
		if self.remoteTimer.isActive():
			self.remoteTimer.stop()
		else:
			self.remoteTimer.start(100)

	def keyUp(self):
		self.speed = '^'

	def keyDown(self):
		self.speed = '|'

	def keyLeft(self):
		self.speed = '<'

	def keyRight(self):
		self.speed = '>'

	def sendSpeed(self):
		if self.ui.upButton.isDown():
			self.speed = '^'
		elif self.ui.downButton.isDown():
			self.speed = '|'
		elif self.ui.leftButton.isDown():
			self.speed = '<'
		elif self.ui.rightButton.isDown():
			self.speed = '>'

		if self.sendText(self.speed + "\n") == False:
			# error sending text
			self.toggleRC()
			self.ui.enableRCCheckBox.setCheckState(0)
		self.speed = '$'

	def enableRCCheckBoxEvent(self):
		if self.ui.enableRCCheckBox.checkState() == Qt.Unchecked:
			self.remoteTimer.stop()
		elif self.ui.enableRCCheckBox.checkState() == Qt.Checked:
			self.remoteTimer.start(100)

	def clearPlot(self):
		#self.ui.MyPlotWidget.clear()
		self.data = []
		self.dataInitialised = False
		# self.names = []
		self.receiveNewDataCnt = 0

	def listPorts(self):
		print(self.ui.menuPorts)
		self.ui.menuPorts.clear()
		self.ui.menuPorts.addAction(self.actionRefresh)

		ports = list(serial.tools.list_ports.comports())
		ports.sort()

		for port in ports:
			portName = port[0]
			self.addPortMenu(portName)

	def addPortMenu(self, name):
		menu = self.ui.menuPorts.addMenu(name)
		connectAction = QtGui.QAction('&Connect', self) 
		connectAction.triggered.connect(lambda: self.connectToPort(name))
		menu.addAction(connectAction)

	def connectToPort(self, portName):
		self.plotTimer.stop()

		# clear listView items
		self.listViewModel.clear() 
		self.nameCheckItems = []

		if self.serThread is not None:
			if self.serThread.isRunning():
				self.procEnd.emit() # end serial thread
				time.sleep(1)

		self.appendToConsole("Creating new thread\n", QtGui.QColor('green'))
		try:
			self.serThread = SerialThread(portName, 115200)
			self.appendToConsole("Connected to %s\n" % portName, QtGui.QColor('green'))
		except:
			self.appendToConsoleErr("Error connecting to %s\n" % portName)
			self.procEnd.emit() # end serial thread
			return
		self.serThread.newDataSig.connect(self.receiveNewData)
		self.serThread.newNamesSig.connect(self.receiveNewNames)
		self.procSend.connect(self.serThread.send_text)
		self.procEnd.connect(self.serThread.close)
		self.connect(self.serThread, SIGNAL("append_text(QString)"), self.ui.plainTextEdit.appendPlainText)
		self.connect(self.serThread, SIGNAL("append_console(QString)"), self.appendToConsole)
		self.connect(self.serThread, SIGNAL("append_console_err(QString)"), self.appendToConsoleErr)
		self.serThread.start()
		
		# Create variables
		self.data = []
		self.dataInitialised = False
		self.dataColumns = 0
		self.names = []
		self.receiveNewDataCnt = 0

		time.sleep(0.5)

		self.plotTimer.start(50)  # 20Hz timer

	def receiveNewData(self, myNewData):	
		for newDataRow in myNewData:
			self.receiveNewDataCnt = self.receiveNewDataCnt + 1

			for i in range(len(newDataRow)):
				if self.dataInitialised is False:
					self.data.append([])
				self.data[i].append(newDataRow[i])

		if self.dataInitialised is False:
			self.dataInitialised = True

	def receiveNewNames(self, newNames):
		print("Receiving new names")
		self.names = newNames
		self.dataColumns = len(self.names)

		for i in range(self.dataColumns):      
			color = pg.intColor(i, self.dataColumns) 
			self.curveColors.append(color)    
			item = QtGui.QStandardItem(self.names[i])
			item.setBackground(color)
			item.setCheckState(Qt.Checked)
			item.setCheckable(True)
			self.listViewModel.appendRow(item)
			self.nameCheckItems.append(item)

	def curveEnabled(self, name):
		for i in range(self.dataColumns):
			if self.curves[i].name() == name and self.curveStates[i] == True:
				return True
		return False

	def plot(self):
		if len(self.curves) <= 0 and self.dataInitialised:
			rgn = pg.LinearRegionItem([self.data[0][0],self.data[0][0]+1000000])
			self.ui.MyPlotWidget.addItem(rgn)
			# initialise curves
			print(self.dataColumns)
			for i in range(self.dataColumns):
				curve = pg.PlotCurveItem(pen=self.curveColors[i], name=self.names[i])
				self.ui.MyPlotWidget.addItem(curve)
				self.curves.append(curve)
				self.curveStates.append(True)
				

		if self.ui.tabWidget.currentIndex() == 1:
			for i in range(self.dataColumns):
				if self.nameCheckItems[i].checkState() == Qt.Checked:
					# add curve if not there already
					if self.curveEnabled(self.nameCheckItems[i].text()) is False:
						self.ui.MyPlotWidget.addItem(self.curves[i])
						self.curveStates[i] = True
						print ("adding")

					if (len(self.data[0]) == len(self.data[i+1])):
						self.curves[i].setData(self.data[0][-10000:],self.data[i+1][-10000:])
				else:
					# remove curve if not already
					if self.curveEnabled(self.nameCheckItems[i].text()):
						self.ui.MyPlotWidget.removeItem(self.curves[i])
						self.curveStates[i] = False
						print ("removing")

			if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
				QtGui.QApplication.processEvents()

	def sendText(self, textOut):
		if self.serThread is None:
			self.appendToConsole("Cannot send. Not connected to serial port\n")
			return False
		else:
			self.ui.sendTextBox.setText("")
			self.appendToConsole("sent %s" % textOut, color = QtGui.QColor('blue'))
			self.procSend.emit(textOut)
			return True

	def sendMsg(self):
		self.sendText(self.ui.sendTextBox.text() + "\n")
			

	def appendToConsole(self, text, color = QtGui.QColor('red')):
		self.ui.console.setTextColor(color)
		# cursor should always be at end of contents of QTextEdit
		self.ui.console.insertPlainText("$ %s" % text)

		c =  self.ui.console.textCursor();
		c.movePosition(QtGui.QTextCursor.End);
		self.ui.console.setTextCursor(c);
		# txtedit.ensureCursorVisible(); // you might need this also

	def appendToConsoleErr(self, text):
		self.appendToConsole(text, color = QtGui.QColor('purple'))

		
class SerialParser(object):
	def __init__(self, port, baud, t = 1, delim = '\t', dirMsgSig = 'd'):
		try:
			self.ser = Serial(port, baud, timeout=t)
		except:
			raise Exception("SerialParser_serialerror")
		self.delimiter = delim
		self.dirMsgSig = dirMsgSig
		self.names = []
		self.numberOfElements = 0
		self.buff = ''
		self.consoleBuff = ''
		self.printBuff = ''
		self.lines = []
		self.newData = []
		self.goodRow = False
		self.lineCount = 0

	def readline(self):
		return self.ser.readline().decode("utf-8") 

	def start():
		for i in range(500):
			self.readline()

	def getNames(self):
		for i in range(4):
			time.sleep(0.05)
			self.ser.write(b']\n')

		self.ser.read(self.ser.inWaiting()) # read all in buff
		self.ser.write(b'?\n')

		# wait until '$' is the first character of line
		line = self.readline()
		while line[0] != '$':
			line = self.readline()

		self.ser.write(b'[\n')
		# print(line)

		# remove the first character ('$') and split
		self.names = line[1:].split(self.delimiter)
		self.names.pop(0) # the first element of the list should be time, so remove
		self.numberOfElements = len(self.names)

		return self.numberOfElements

	def read(self):
		try:
			self.buff += self.readline()
		except:
			raise Exception("SerialParser_serialerrorreading")
		newLines = self.buff.splitlines(True)  # split lines and keep newline characters
		self.buff = ''
		
		for eachLine in newLines:
			if "\n" not in eachLine:
				self.buff += eachLine
			else:
				# lines with $ as first character are not to be graphed
				if (eachLine[:1] == '$'):
					# needs to be outputed to console
					self.consoleBuff += eachLine.strip('\r')
				elif (eachLine.count(self.delimiter)) == self.numberOfElements:
					self.lineCount = self.lineCount + 1
					try:
						appendingRow = [float(numStr) for numStr in eachLine.split(self.delimiter)]
						self.goodData = True
						self.newData.append(appendingRow)
						# this is to be outputed to output textbox
						self.printBuff += eachLine
					except:
						# something wrong with converting data to float
						self.goodData = False

		self.lines.append(newLines)


class SerialThread(QThread):
	newDataSig = QtCore.pyqtSignal(object)
	newNamesSig = QtCore.pyqtSignal(object)
	def __init__(self, port_, baud_, t_ = 1, delim_ = '\t', dirMsgSig_ = 'd'):
		QThread.__init__(self)
		self.enabled = True
		self.serParser = None
		try:
			self.serParser = SerialParser(port_, baud_, t = t_, delim = delim_, dirMsgSig = dirMsgSig_)
		except:
			raise Exception("SerialThread_serialerror")
	def __del__(self):
		self.wait()
	def run(self):
		# self.start()
		self.serParser.getNames()
		self.newNamesSig.emit(self.serParser.names)

		while self.enabled:
			try:
				self.serParser.read()
			except:
				self.emit(SIGNAL('append_console_err(QString)'), "Error reading from serial\n")
				self.enabled = False
			if len(self.serParser.consoleBuff) > 0:
				self.emit(SIGNAL('append_console(QString)'), self.serParser.consoleBuff[1:])
				self.serParser.consoleBuff = ""
			if len(self.serParser.printBuff) > 0:
				self.emit(SIGNAL('append_text(QString)'), self.serParser.printBuff.rstrip())
				self.serParser.printBuff = ""
			if len(self.serParser.newData) > 0:
				self.newDataSig.emit(self.serParser.newData)
				self.serParser.newData = []

		self.emit(SIGNAL('append_console_err(QString)'), "Closing serial port\n")
		self.serParser.ser.close()
		self.serParser.ser = None
		self.emit(SIGNAL('append_console_err(QString)'), "Closing serial thread\n")

	@QtCore.pyqtSlot(str)
	def send_text(self, text):
		self.serParser.ser.write(text.encode("utf-8"))

	@QtCore.pyqtSlot()
	def close(self):
		self.enabled = False


win = MainWindow()

if __name__ == '__main__':
	QtGui.QApplication.instance().exec_()