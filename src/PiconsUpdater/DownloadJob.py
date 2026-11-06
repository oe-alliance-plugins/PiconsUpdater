from os.path import isfile
from requests import exceptions, get
from twisted.internet.reactor import callFromThread, callInThread, callLater

from . import printToConsole


class download:
	def __init__(self, url, outputfile):
		self.url = url
		self.file = outputfile

	def start(self, success, fail=None):
		return callInThread(self.downloadPage, self.url, self.file, success, fail)

	def stop(self):
		return

	def downloadPage(self, link, file, success, fail=None):
		link = link.encode("ascii", "xmlcharrefreplace").decode().replace(" ", "%20").replace("\n", "").encode("utf-8")
		try:
			response = get(link, timeout=(3.05, 6))
			content = response.content
			response.raise_for_status()
			with open(file, "wb") as f:
				f.write(content)
		except (exceptions.RequestException, OSError) as err:
			if fail is not None:
				printToConsole(f"Error in module 'downloadPage': {err}")
				callFromThread(fail, err)
		else:
			callFromThread(success, file)


class DownloadJob:
	def __init__(self, downloadUrl, targetFileName, callbackFinished=None, callbackFailed=None, override=False):
		self.downloadUrl = downloadUrl
		self.targetFileName = targetFileName
		self.callbackFinished = callbackFinished
		self.callbackFailed = callbackFailed
		self.download = None
		if not override and isfile(self.targetFileName):
			callLater(0, self.__downloadFromCache)
		else:
			self.run()

	def __del__(self):
		self.clean()

	def clean(self):
		try:
			del self.callbackFailed
			del self.callbackFinished
		except Exception:
			pass

	def run(self):
		self.download = download(self.downloadUrl, self.targetFileName)
		self.download.start(self.__downloadFinished, self.__downloadFailed)

	def __downloadFromCache(self):
		printToConsole(f"file '{self.targetFileName}' already exists.")
		self.__downloadFinished()

	def __downloadFinished(self, string=""):
		if self.callbackFinished is not None:
			callback = self.callbackFinished
			self.clean()
			callback(self)
		if self.download:
			self.download.stop()
			self.download = None

	def __downloadFailed(self, errorMessage=""):
		self.errorMessage = errorMessage
# if errorMessage == "" and failureInstance is not None:
# self.errorMessage = failureInstance.getErrorMessage()
# self.errorMessage = f"{self.downloadUrl} - {self.errorMessage}"
		if self.callbackFailed is not None:
			callback = self.callbackFailed
			self.clean()
			callback(self)
		if self.download:
			self.download.stop()
		self.download = None
