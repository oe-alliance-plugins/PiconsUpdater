from collections import deque
from os.path import isfile
from subprocess import call
from PIL import Image
from twisted.internet.reactor import callLater
from twisted.internet.threads import deferToThread

from Components.config import config

from . import _, getPiconsPath, getTmpLocalPicon, printToConsole
from .BouquetParser import getChannelKey
from .DiskUtils import getCleanFileName, getFiles
from .EventDispatcher import dispatchEvent
from .JobProgressView import JobProgressView
from .reflection import add_reflection

MERGE_PICONS_FINISHED = "mergePiconsFinished"
OPTIMIZE_PICONS_FINISHED = "optimizePiconsFinished"


class MergeVO:
	def __init__(self, channelPicon, targetPicon):
		self.channelPicon = channelPicon
		self.targetPicon = targetPicon


class MergePiconJob:
	def __init__(self, session, serviceList, bgPath, fgPath, factor, size):
		self.session = session
		self.aborted = False
		self.progressDialog = self.session.open(JobProgressView, _("Merge Picons"), onAbort=self.onAbort, msgBoxID="mergePicons")
		self.serviceList = serviceList
		self.bgPath = bgPath
		self.fgPath = fgPath
		self.targetPicon = getPiconsPath().getValue() + "/%s.png"
		self.factor = factor
		self.size = size
		self.executionQueueList = deque()
		for service in self.serviceList:
			piconName = getChannelKey(service)
			if any(piconName.find(i) + 1 for i in ["4097", "5001", "5002", "5003"]):  # Internetstream found, therefore use SNP:
				piconName = getCleanFileName(service.getServiceName()).replace("-", "")
			piconFile = getTmpLocalPicon(piconName)
			if isfile(piconFile):
				job = MergeVO(piconFile, self.targetPicon % piconName)
				self.executionQueueList.append(job)

		self.mergePiconsTotal = len(self.executionQueueList)
		self.mergePiconsCount = 0
		if self.executionQueueList:
			self.execQueue()
		else:
			callLater(0, self.__runFinished, None)

	def __del__(self):
		del self.session

	def execQueue(self):
		try:
			if len(self.executionQueueList) > 0:
				self.mergePiconsCount += 1
				progress = int(100 * (float(self.mergePiconsCount) / float(self.mergePiconsTotal)))
				self.progressDialog.setProgress(progress, _("Merge %d of %d Picons") % (self.mergePiconsCount, self.mergePiconsTotal))
				mergeData = self.executionQueueList.popleft()
				deferToThread(self.mergePicon, mergeData.channelPicon, mergeData.targetPicon).addBoth(self.__runFinished)
		except Exception as err:
			self.__clearExecutionQueueList()
			printToConsole(f"MergePicon execQueue exception:\n{err}")

	def __clearExecutionQueueList(self):
		self.executionQueueList = deque()

	def __runFinished(self, result):
		if self.aborted:
			return
		if result is not None:
			printToConsole(f"Error merging picon: {result.getErrorMessage()}")
		try:
			if len(self.executionQueueList) > 0:
				self.execQueue()
			else:
				printToConsole("MergePicon Queue finished!")
				dispatchEvent(MERGE_PICONS_FINISHED)
		except Exception as err:
			self.__clearExecutionQueueList()
			printToConsole(f"MergePicon runFinished exception:\n{err}")

	def mergePicon(self, channelPicon, targetPicon):
		try:
			background = Image.open(self.bgPath)
		except Exception:
			printToConsole(f"Error: Background '{self.bgPath}' is corrupted!")
			return

		try:
			picon = Image.open(channelPicon)
		except Exception:
			printToConsole(f"Error: Picon '{channelPicon}' is corrupted!")
			return

		backgroundWidth, backgroundHeight = background.size
		piconWidth, piconHeight = picon.size
		scaleWidth = int(piconWidth * self.factor)
		scaleHeight = int(piconHeight * self.factor)
		picon = picon.resize((scaleWidth, scaleHeight), Image.Resampling.LANCZOS)
		centerPoint = ((backgroundWidth - scaleWidth) // 2, (backgroundHeight - scaleHeight) // 2)
		if config.plugins.PiconsUpdater.mirror_effect.getValue():
			try:
				picon = add_reflection(picon)
			except Exception as err:
				printToConsole(f"Error: add_reflection: {err} '{channelPicon}'")
		try:
			background.paste(picon, centerPoint, picon)
			if self.fgPath is not None:
				foreground = Image.open(self.fgPath)
				background.paste(foreground, None, foreground)
		except Exception as err:
			printToConsole(f"Error: ChannelPicon: {err} '{channelPicon}'")
			return

		if piconWidth != self.size[0] or piconHeight != self.size[1]:
			background.thumbnail(self.size, Image.Resampling.LANCZOS)
		else:
			background.thumbnail(self.size)
		background.save(targetPicon)

	def onAbort(self):
		self.aborted = True
		self.executionQueueList.clear()


class OptimizePiconsFileSize:
	def __init__(self, session):
		self.session = session
		self.aborted = False
		self.progressDialog = self.session.open(JobProgressView, _("Optimize Picons Progress"), onAbort=self.onAbort, msgBoxID="optimizePicons")
		self.executionQueueList = deque()
		piconsList = getFiles(getPiconsPath().getValue(), ".png")
		if piconsList:
			self.optimizePiconsTotal = len(piconsList)
			self.optimizePiconsCount = 0
			self.executionQueueList.extend(piconsList)
			self.execQueue()
		else:
			callLater(0, self.__runFinished)

	def __del__(self):
		del self.session

	def execQueue(self):
		try:
			if len(self.executionQueueList) > 0:
				self.optimizePiconsCount += 1
				progress = int(100 * (float(self.optimizePiconsCount) / float(self.optimizePiconsTotal)))
				self.progressDialog.setProgress(progress, _("Optimize %d of %d Picons") % (self.optimizePiconsCount, self.optimizePiconsTotal))
				self.execCommand = ("/usr/bin/pngquant", "--ext", ".png", "--speed", "10", "--force", "128", self.executionQueueList.popleft())
				deferToThread(self.optimizePicon).addBoth(self.__runFinished)
		except Exception as err:
			self.__clearExecutionQueueList()
			printToConsole(f"OptimizePicons execQueue exception:\n{err}")

	def __clearExecutionQueueList(self):
		self.executionQueueList = deque()

	def __runFinished(self, retval=None):
		if self.aborted:
			return
		if retval:
			printToConsole(f"Error optimizing picon: {retval}")
		try:
			if len(self.executionQueueList) > 0:
				self.execQueue()
			else:
				printToConsole("OptimizePicons Queue finished!")
				dispatchEvent(OPTIMIZE_PICONS_FINISHED)
		except Exception as err:
			self.__clearExecutionQueueList()
			printToConsole(f"OptimizePicons runFinished exception:\n{err}")

	def optimizePicon(self):
		return call(self.execCommand)

	def onAbort(self):
		self.aborted = True
		self.__clearExecutionQueueList()
