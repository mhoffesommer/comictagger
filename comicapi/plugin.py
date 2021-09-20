from typing import Union, BinaryIO, Mapping, List, Tuple
from collections import defaultdict
import io


class Archiver:
    has_comment: bool = False
    archive_type: str = ""
    archive_ext: str = ""
    settings: Mapping[str, str] = defaultdict(lambda: "", {})

    def __init__(self, path, settings: Mapping[str, any]):
        self.path = path

    @staticmethod
    def isValid(file: Union[str, bytearray, bytes, BinaryIO]) -> bool:
        pass

    def getComment(self) -> str:
        pass

    def setComment(self, comment: str) -> bool:
        pass

    def readFile(self, archive_file: str) -> Union[bytearray, bytes, str]:
        pass

    def removeFile(self, archive_file: str) -> bool:
        pass

    def removeFiles(self, archive_files: List[str]) -> bool:
        for file in archive_files:
            if not self.removeFile(file):
                return False

        return True

    def writeFile(self, archive_file: str, data: Union[bytearray, bytes, str]) -> bool:
        pass

    def writeFiles(self, archive_files: List[Tuple[str, bytearray]]) -> bool:
        for file, data in archive_files:
            if not self.writeFile(file, data):
                return False

        return True

    def getFilenameList(self) -> List[str]:
        pass

    def isWritable(self) -> bool:
        pass

    def copyFromArchive(self, otherArchive):
        # Replace the current contents with one copied from another archive
        try:
            self.removeFiles(self.getFilenameList())
            for fname in otherArchive.getArchiveFilenameList():
                data = otherArchive.readArchiveFile(fname)
                if data is not None:
                    self.writeFile(fname, data)

        except Exception as e:
            errMsg = u"Error while copying to {0}: {1}".format(self.path, e)
            logger.info(errMsg)
            return False
        else:
            return True


class UnknownArchiver(Archiver):
    """Unknown implementation"""

    def __init__(self, path, settings: Mapping[str, any]):
        super().__init__(path, settings)
        self.path = path

    def getComment(self):
        return ""

    def setComment(self, comment):
        return False

    def readFile(self, archive_file: str) -> Union[bytearray, bytes, None]:
        return None

    def writeFile(self, archive_file, data):
        return False

    def removeFile(self, archive_file):
        return False

    def getFilenameList(self):
        return []

    def isWritable(self) -> bool:
        return False


plugin_settings: defaultdict[str, defaultdict[str, any]] = defaultdict(lambda: defaultdict(str), {})
