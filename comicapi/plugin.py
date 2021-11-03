import io
from collections import defaultdict
from typing import BinaryIO, List, Mapping, Tuple, Union

from packaging import version

from comicapi.genericmetadata import GenericMetadata


class Plugin:
    """docstring for Plugin"""

    settings_section: str = ""
    version: version.Version = None


class Archiver(Plugin):
    settings_section: str = ""
    version: version.Version = None

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

    settings_section: str = "Unknown"
    version: version.Version = version.parse("1.0.0")

    def __init__(self, path, settings: Mapping[str, any]):
        super().__init__(path, settings)
        self.path = path

    def getComment(self) -> str:
        return ""

    def setComment(self, comment: str) -> bool:
        return False

    def readFile(self, archive_file: str) -> Union[bytearray, bytes, str]:
        return None

    def writeFile(self, archive_file: str, data: Union[bytearray, bytes, str]) -> bool:
        return False

    def removeFile(self, archive_file: str) -> bool:
        return False

    def getFilenameList(self) -> List[str]:
        return []

    def isWritable(self) -> bool:
        return False


class Metadata(Plugin):
    settings_section: str = ""
    version: version.Version = None

    def archiveSupportsMetadata(self, archive: Archiver) -> bool:
        pass

    def archiveHasMetadata(self, archive: Archiver) -> bool:
        pass

    def metadataFromString(self, string: str) -> GenericMetadata:
        pass

    def stringFromMetadata(self, metadata: GenericMetadata) -> str:
        pass

    def metadataFromArchive(self, archive: Archiver) -> GenericMetadata:
        pass

    def metadataToArchive(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        pass


# Settings sections should be named after the archive type or the metadata type.
# Currently this is only a convenience, settings still need to be passed to the constructor manually.

# Example:
# rar_settings = plugin_settings['rar']
# comic_rack_settings = plugin_settings['comicrack']
plugin_settings: defaultdict[str, defaultdict[str, any]] = defaultdict(lambda: defaultdict(str), {})
