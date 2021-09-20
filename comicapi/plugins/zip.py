import logging
import os
import struct
import tempfile
import zipfile
from collections import defaultdict
from typing import BinaryIO, Mapping, Union

import filetype

from comicapi.plugin import Archiver

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def write_zip_comment(filename, comment):
    """
    This is a custom function for writing a comment to a zip file,
    since the built-in one doesn't seem to work on Windows and Mac OS/X

    Fortunately, the zip comment is at the end of the file, and it's
    easy to manipulate.  See this website for more info:
    see: http://en.wikipedia.org/wiki/Zip_(file_format)#Structure
    """

    statinfo = os.stat(filename)
    file_length = statinfo.st_size

    try:
        fo = open(filename, "r+b")

        # the starting position, relative to EOF
        pos = -4

        found = False
        value = bytearray()

        # walk backwards to find the "End of Central Directory" record
        while (not found) and (-pos != file_length):
            # seek, relative to EOF
            fo.seek(pos, 2)

            value = fo.read(4)

            # look for the end of central directory signature
            if bytearray(value) == bytearray([0x50, 0x4B, 0x05, 0x06]):
                found = True
            else:
                # not found, step back another byte
                pos = pos - 1

        if found:

            # now skip forward 20 bytes to the comment length word
            pos += 20
            fo.seek(pos, 2)

            # Pack the length of the comment string
            form = "H"  # one 2-byte integer
            comment_length = struct.pack(form, len(comment))  # pack integer in a binary string

            # write out the length
            fo.write(comment_length)
            fo.seek(pos + 2, 2)

            # write out the comment itself
            fo.write(bytes(comment))
            fo.truncate()
            fo.close()
        else:
            raise Exception("Failed to write comment to zip file!")
    except Exception as e:
        return False
    else:
        return True


class ZipArchiver(Archiver):
    """ZIP implementation"""

    has_comment = True
    archive_type = "ZIP"
    archive_ext = "cbz"
    settings: Mapping[str, str] = defaultdict(lambda: "", {})

    def __init__(self, path, settings: Mapping[str, any]):
        super().__init__(path, settings)
        self.path = path

    @staticmethod
    def isValid(file: Union[str, bytearray, bytes, BinaryIO]) -> bool:
        return filetype.get_type(ext="zip").match(filetype.utils.get_bytes(file))

    def getComment(self):
        zf = zipfile.ZipFile(self.path, "r")
        comment = zf.comment
        zf.close()
        return comment

    def setComment(self, comment):
        zf = zipfile.ZipFile(self.path, "a")
        zf.comment = bytes(comment, "utf-8")
        zf.close()
        return True

    def readFile(self, archive_file):
        data = ""
        zf = zipfile.ZipFile(self.path, "r")

        try:
            data = zf.read(archive_file)
        except zipfile.BadZipfile as e:
            errMsg = f"bad zipfile [{e}]: {self.path} :: {archive_file}"
            logger.info(errMsg)
            zf.close()
            raise IOError
        except Exception as e:
            zf.close()
            errMsg = f"bad zipfile [{e}]: {self.path} :: {archive_file}"
            logger.info(errMsg)
            raise IOError
        finally:
            zf.close()
        return data

    def removeFile(self, archive_file):
        try:
            self.rebuildZipFile([archive_file])
        except:
            return False
        else:
            return True

    def writeFile(self, archive_file, data):
        # At the moment, no other option but to rebuild the whole
        # zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        try:
            self.rebuildZipFile([archive_file])

            # now just add the archive file as a new one
            zf = zipfile.ZipFile(self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED)
            zf.writestr(archive_file, data)
            zf.close()
            return True
        except:
            return False

    def getFilenameList(self):
        try:
            zf = zipfile.ZipFile(self.path, "r")
            namelist = zf.namelist()
            zf.close()
            return namelist
        except Exception as e:
            errMsg = f"Unable to get zipfile list [{e}]: {self.path}"
            logger.info(errMsg)
            return []

    def isWritable(self) -> bool:
        if not os.access(self.path, os.W_OK) or not os.access(os.path.dirname(os.path.abspath(self.path)), os.W_OK):
            return False

        return True

    def rebuildZipFile(self, exclude_list):
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """
        tmp_fd, tmp_name = tempfile.mkstemp(dir=os.path.dirname(self.path))
        os.close(tmp_fd)

        zin = zipfile.ZipFile(self.path, "r")
        zout = zipfile.ZipFile(tmp_name, "w", allowZip64=True)
        for item in zin.infolist():
            buffer = zin.read(item.filename)
            if item.filename not in exclude_list:
                zout.writestr(item, buffer)

        # preserve the old comment
        zout.comment = zin.comment

        zout.close()
        zin.close()

        # replace with the new file
        os.remove(self.path)
        os.rename(tmp_name, self.path)
