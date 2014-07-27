import shelve
import sys
import os
from queue import Queue

from PyQt4.Qt import QApplication, QThread, QObject, pyqtSignal, pyqtSlot

from RedditDataExtractor.redditDataExtractor import RedditDataExtractor
from RedditDataExtractor.GUI.listModel import ListModel
from RedditDataExtractor.GUI.genericListModelObjects import User, Subreddit
from RedditDataExtractor.GUI.redditDataExtractorGUI import RddtDataExtractorGUI

class QueueMessageReceiver(QObject):
    queuePutSignal = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, queue, *args, **kwargs):
        """
        A QObject (to be run in a QThread) which sits waiting for data to come through a Queue.Queue().
        It blocks until data is available, and once it has got something from the queue, it sends
        it to the main GUI thread by emitting the pyqtSignal 'finished'

        :type queue: Queue.queue
        """
        QObject.__init__(self, *args, **kwargs)
        self.queue = queue
        self.continueOperation = True

    @pyqtSlot()
    def run(self):
        while(self.continueOperation):
            text = self.queue.get()
            self.queuePutSignal.emit(text)
        self.finished.emit()

    def stop(self):
        """
        Stop the receiver thread from running. Useful for cleaning up threads when the program is exiting.
        """
        self.continueOperation = False
        self.queue.put("") # wake up the queue (it blocks until it gets something)

def loadState():
    """
    Attempt to load the program from a pickled state in the saves directory.
    """
    shelf = shelve.open(os.path.join("RedditDataExtractor", "saves", "settings.db"))
    rddtDataExtractor = None
    try:
        rddtDataExtractor = shelf['rddtDataExtractor']
        userListSettings = shelf['userLists']
        subredditListSettings = shelf['subredditLists']
        rddtDataExtractor.userLists = {}
        rddtDataExtractor.subredditLists = {}
        # Reconstruct the lists because GUI stuff isn't pickleable
        for key, val in userListSettings.items():
            rddtDataExtractor.userLists[key] = ListModel(val, User)
        for key, val in subredditListSettings.items():
            rddtDataExtractor.subredditLists[key] = ListModel(val, Subreddit)
    except KeyError as e:
        print(e)
    finally:
        shelf.close()
        return rddtDataExtractor

def main():
    app = QApplication(sys.argv)
    rddtDataExtractor = loadState()
    if rddtDataExtractor is None:
        print("rddt data client was None, making new one")
        rddtDataExtractor = RedditDataExtractor()
    rddtDataExtractor.currentlyDownloading = False # If something weird happened to cause currentlyDownloading to be saved as True, set it back to False

    queue = Queue()
    thread = QThread()
    recv = QueueMessageReceiver(queue)
    mainGUIWindow = RddtDataExtractorGUI(rddtDataExtractor, queue, recv)

    recv.queuePutSignal.connect(mainGUIWindow.append_text)
    recv.moveToThread(thread)
    thread.started.connect(recv.run)
    # Add clean up finished signals so the threads end appropriately when the program ends
    recv.finished.connect(thread.quit)
    recv.finished.connect(recv.deleteLater)
    thread.finished.connect(thread.deleteLater)

    # start the receiver
    thread.start()
    # show the GUI
    mainGUIWindow.show()
    # display Imgur API pop up if not hidden by user and client-id isn't set
    if rddtDataExtractor.showImgurAPINotification and rddtDataExtractor.imgurAPIClientID is None:
        mainGUIWindow.notifyImgurAPI()
    # and wait for the user to exit
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()