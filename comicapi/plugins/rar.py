import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from typing import BinaryIO, Mapping, Union

import filetype
from unrar.cffi import rarfile

from comicapi.plugin import Archiver

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RarArchiver(Archiver):
    """RAR implementation"""

    has_comment = True
    archive_type = "RAR"
    archive_ext = "cbr"
    settings: Mapping[str, str] = defaultdict(
        lambda: "",
        {
            "rar_exe_path": "[str] Path to the rar executable",
            "rar_options": "list[str] Options to pass to the rar executable",
        },
    )

    devnull = None

    def __init__(self, path, settings: Mapping[str, any]):
        super().__init__(path, settings)
        self.path = path
        self.settings = settings

        if RarArchiver.devnull is None:
            RarArchiver.devnull = open(os.devnull, "w")

        # windows only, keeps the cmd.exe from popping up
        if platform.system() == "Windows":
            self.startupinfo = subprocess.STARTUPINFO()
            self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            self.startupinfo = None

    @staticmethod
    def isValid(file: Union[str, bytearray, bytes, BinaryIO]) -> bool:
        return filetype.get_type(ext="rar").match(filetype.utils.get_bytes(file))

    def getComment(self):
        rarc = self.getRARObj()
        return rarc.comment

    def setComment(self, comment):
        if "rar_exe_path" in self.settings and self.settings["rar_exe_path"]:
            try:
                # write comment to temp file
                tmp_fd, tmp_name = tempfile.mkstemp()
                f = os.fdopen(tmp_fd, "w+")
                f.write(comment)
                f.close()

                working_dir = os.path.dirname(os.path.abspath(self.path))

                # use external program to write comment to Rar archive
                proc_args = [
                    self.settings["rar_exe_path"],
                    "c",
                    "-w" + working_dir,
                    "-c-",
                    "-z" + tmp_name,
                    *self.settings["rar_options"],
                    self.path,
                ]
                subprocess.call(
                    proc_args,
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
                os.remove(tmp_name)
            except Exception as e:
                print(e)
                return False
            else:
                return True
        else:
            return False

    def readFile(self, archive_file):
        entries = []

        rarc = self.getRARObj()

        tries = 0
        while tries < 7:
            try:
                tries = tries + 1
                data = rarc.open(archive_file).read()
                entries = [(rarc.getinfo(archive_file), data)]

                if entries[0][0].file_size != len(entries[0][1]):
                    print(
                        f"readFile(): [file is not expected size: {entries[0][0].file_size} vs {len(entries[0][1])}]  {self.path}:{archive_file} [attempt#{tries}]",
                        file=sys.stderr,
                    )
                    continue
            except (OSError, IOError) as e:
                print(f"readFile(): [{e}]  {self.path}:{archive_file} attempt#{tries}", file=sys.stderr)
                time.sleep(1)
            except Exception as e:
                print(f"Unexpected exception in readFile(): [{e}] for {self.path}:{archive_file} attempt#{tries}", file=sys.stderr)
                break

            else:
                # Success"
                # entries is a list of of tuples:  ( rarinfo, filedata)
                if tries > 1:
                    print(f"Attempted read_files() {tries} times", file=sys.stderr)
                if len(entries) == 1:
                    return entries[0][1]
                else:
                    raise IOError

        raise IOError

    def writeFile(self, archive_file, data):
        if "rar_exe_path" in self.settings and self.settings["rar_exe_path"]:
            try:
                tmp_folder = tempfile.mkdtemp()

                tmp_file = os.path.join(tmp_folder, archive_file)

                working_dir = os.path.dirname(os.path.abspath(self.path))

                # TODO: will this break if 'archive_file' is in a subfolder. i.e. "foo/bar.txt"
                # will need to create the subfolder above, I guess...
                f = open(tmp_file, "w")
                f.write(data)
                f.close()

                # use external program to write file to Rar archive
                subprocess.call(
                    [
                        self.settings["rar_exe_path"],
                        "a",
                        "-w" + working_dir,
                        "-c-",
                        "-ep",
                        *self.settings["rar_options"],
                        self.path,
                        tmp_file,
                    ],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
                os.remove(tmp_file)
                os.rmdir(tmp_folder)
            except:
                return False
            else:
                return True
        else:
            return False

    def removeFile(self, archive_file):
        if "rar_exe_path" in self.settings and self.settings["rar_exe_path"]:
            try:
                # use external program to remove file from Rar archive
                subprocess.call(
                    [
                        self.settings["rar_exe_path"],
                        "d",
                        "-c-",
                        *self.settings["rar_options"],
                        self.path,
                        archive_file,
                    ],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull,
                    stdin=RarArchiver.devnull,
                    stderr=RarArchiver.devnull,
                )

                if platform.system() == "Darwin":
                    time.sleep(1)
            except:
                return False
            else:
                return True
        else:
            return False

    def getFilenameList(self):
        rarc = self.getRARObj()
        tries = 0
        while tries < 7:
            try:
                tries = tries + 1
                namelist = []
                for item in rarc.infolist():
                    if item.file_size != 0:
                        namelist.append(item.filename)

            except (OSError, IOError) as e:
                print(f"getFilenameList(): [{e}] {self.path} attempt#{tries}", file=sys.stderr)
                time.sleep(1)
                raise e

            else:
                # Success"
                return namelist

    def isWritable(self) -> bool:
        if not ("rar_exe_path" in self.settings and self.settings["rar_exe_path"]):
            return False

        if not os.access(self.path, os.W_OK) or not os.access(os.path.dirname(os.path.abspath(self.path)), os.W_OK):
            return False

        return True

    def getRARObj(self):
        tries = 0
        while tries < 7:
            try:
                tries = tries + 1
                rarc = rarfile.RarFile(self.path)

            except (OSError, IOError) as e:
                print(f"getRARObj(): [{e}] {self.path} attempt#{tries}", file=sys.stderr)
                time.sleep(1)
                raise e

            else:
                # Success"
                return rarc
