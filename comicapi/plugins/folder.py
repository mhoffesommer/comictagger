import logging
import os
from collections import defaultdict
from typing import BinaryIO, Mapping, Union

from comicapi.plugin import Archiver

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FolderArchiver(Archiver):
    """Folder implementation"""

    comment_file_name = "ComicTaggerFolderComment.txt"
    has_comment = True
    archive_type = "Folder"
    archive_ext = ""
    settings: Mapping[str, str] = defaultdict(lambda: "", {})

    def __init__(self, path, settings: Mapping[str, any]):
        super().__init__(path, settings)
        self.path = path

    @staticmethod
    def isValid(file: Union[str, bytearray, bytes, BinaryIO]) -> bool:
        return os.path.isdir(file)

    def getComment(self):
        return self.readFile(self.comment_file_name)

    def setComment(self, comment):
        return self.writeFile(self.comment_file_name, comment)

    def readFile(self, archive_file):
        data = ""
        fname = os.path.join(self.path, archive_file)
        try:
            with open(fname, "rb") as f:
                data = f.read()
                f.close()
        except IOError as e:
            pass

        return data

    def writeFile(self, archive_file, data):
        fname = os.path.join(self.path, archive_file)
        try:
            with open(fname, "w+") as f:
                f.write(data)
                f.close()
        except:
            return False
        else:
            return True

    def removeFile(self, archive_file):

        fname = os.path.join(self.path, archive_file)
        try:
            os.remove(fname)
        except:
            return False
        else:
            return True

    def getFilenameList(self):
        return self.listFiles(self.path)

    def isWritable(self) -> bool:
        if not os.access(self.path, os.W_OK):
            return False

    def listFiles(self, folder):
        item_list = list()

        for item in os.listdir(folder):
            item_list.append(item)
            if os.path.isdir(item):
                item_list.extend(self.listFiles(os.path.join(folder, item)))

        return item_list
