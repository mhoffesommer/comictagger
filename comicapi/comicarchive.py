"""A class to represent a single comic, be it file or folder of images"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import natsort
import io
from typing import Optional
# import filetype

from comicapi.comicinfoxml import ComicInfoXml
from comicapi.comicbookinfo import ComicBookInfo
from comicapi.comet import CoMet
from comicapi.genericmetadata import GenericMetadata, PageType
from comicapi.filenameparser import FileNameParser
from comicapi.plugin import Archiver, UnknownArchiver, plugin_settings
from comicapi.plugin_collection import PluginCollection
from comicapi.plugins.zip import ZipArchiver


try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False


archive_types: Optional[PluginCollection] = None
builtin_archive_types: PluginCollection = PluginCollection(['comicapi.plugins'], Archiver)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MetaDataStyle:
    CBI = 0
    CIX = 1
    COMET = 2
    name = ['ComicBookLover', 'ComicRack', 'CoMet']


class ComicArchive:
    logo_data = None

    def __init__(self, path, default_image_path=None):
        self.path = path

        self.ci_xml_filename = "ComicInfo.xml"
        self.comet_default_filename = "CoMet.xml"
        self.resetCache()
        self.default_image_path = default_image_path

        self.archive_type = "Unknown"
        self.archiver: Archiver = UnknownArchiver(self.path, plugin_settings[UnknownArchiver.archive_ext])
        if os.path.isdir(path):
            b = path
        else:
            with open(path, 'rb') as f:
                b = f.read(30)

        found = False
        for typ in archive_types.plugins:
            if typ.isValid(b):
                self.archiver = typ(path, plugin_settings[typ.archive_ext])
                self.archive_type = self.archiver.archive_type
                found = True

        if not found:
            for typ in builtin_archive_types.plugins:
                if typ.isValid(b):
                    self.archiver = typ(path, plugin_settings[typ.archive_ext])
                    self.archive_type = self.archiver.archive_type

        if ComicArchive.logo_data is None:
            fname = self.default_image_path
            with open(fname, "rb") as fd:
                ComicArchive.logo_data = fd.read()

    def resetCache(self):
        """Clears the cached data"""

        self.has_cix = None
        self.has_cbi = None
        self.has_comet = None
        self.comet_filename = None
        self.page_count = None
        self.page_list = None
        self.cix_md = None
        self.cbi_md = None
        self.comet_md = None

    def loadCache(self, style_list):
        for style in style_list:
            self.readMetadata(style)

    def rename(self, path):
        self.path = path
        self.archiver.path = path

    def isWritable(self):
        return self.archiver.isWritable()

    def isWritableForStyle(self, data_style):
        if self.archiver.has_comment and data_style == MetaDataStyle.CBI:
            return False

        return self.isWritable()

    def seemsToBeAComicArchive(self):
        # Do we even care about extensions??
        ext = os.path.splitext(self.path)[1].lower()
        if issubclass(type(self.archiver), Archiver) and self.archiver is not UnknownArchiver and (self.getNumberOfPages() > 0):
            return True
        else:
            return False

    def readMetadata(self, style):
        if style == MetaDataStyle.CIX:
            return self.readCIX()
        elif style == MetaDataStyle.CBI:
            return self.readCBI()
        elif style == MetaDataStyle.COMET:
            return self.readCoMet()
        else:
            return GenericMetadata()

    def writeMetadata(self, metadata, style):
        retcode = None
        if style == MetaDataStyle.CIX:
            retcode = self.writeCIX(metadata)
        elif style == MetaDataStyle.CBI:
            retcode = self.writeCBI(metadata)
        elif style == MetaDataStyle.COMET:
            retcode = self.writeCoMet(metadata)
        return retcode

    def hasMetadata(self, style):
        if style == MetaDataStyle.CIX:
            return self.hasCIX()
        elif style == MetaDataStyle.CBI:
            return self.hasCBI()
        elif style == MetaDataStyle.COMET:
            return self.hasCoMet()
        else:
            return False

    def removeMetadata(self, style):
        retcode = True
        if style == MetaDataStyle.CIX:
            retcode = self.removeCIX()
        elif style == MetaDataStyle.CBI:
            retcode = self.removeCBI()
        elif style == MetaDataStyle.COMET:
            retcode = self.removeCoMet()
        return retcode

    def getPage(self, index):
        image_data = None

        filename = self.getPageName(index)

        if filename is not None:
            try:
                image_data = self.archiver.readFile(filename)
            except IOError:
                errMsg = "Error reading in page. Substituting logo page."
                logger.info(errMsg)
                image_data = ComicArchive.logo_data

        return image_data

    def getPageName(self, index):
        if index is None:
            return None

        page_list = self.getPageNameList()

        num_pages = len(page_list)
        if num_pages == 0 or index >= num_pages:
            return None

        return page_list[index]

    def getScannerPageIndex(self):
        scanner_page_index = None

        # make a guess at the scanner page
        name_list = self.getPageNameList()
        count = self.getNumberOfPages()

        # too few pages to really know
        if count < 5:
            return None

        # count the length of every filename, and count occurences
        length_buckets = dict()
        for name in name_list:
            fname = os.path.split(name)[1]
            length = len(fname)
            if length in length_buckets:
                length_buckets[length] += 1
            else:
                length_buckets[length] = 1

        # sort by most common
        sorted_buckets = sorted(iter(length_buckets.items()), key=lambda k_v: (k_v[1], k_v[0]), reverse=True)

        # statistical mode occurence is first
        mode_length = sorted_buckets[0][0]

        # we are only going to consider the final image file:
        final_name = os.path.split(name_list[count - 1])[1]

        common_length_list = list()
        for name in name_list:
            if len(os.path.split(name)[1]) == mode_length:
                common_length_list.append(os.path.split(name)[1])

        prefix = os.path.commonprefix(common_length_list)

        if mode_length <= 7 and prefix == "":
            # probably all numbers
            if len(final_name) > mode_length:
                scanner_page_index = count - 1

        # see if the last page doesn't start with the same prefix as most others
        elif not final_name.startswith(prefix):
            scanner_page_index = count - 1

        return scanner_page_index

    def getPageNameList(self, sort_list=True):
        if self.page_list is None:
            # get the list file names in the archive, and sort
            files = self.archiver.getFilenameList()

            # seems like some archive creators are on  Windows, and don't know about case-sensitivity!
            if sort_list:
                def keyfunc(k):
                    # hack to account for some weird scanner ID pages
                    # basename=os.path.split(k)[1]
                    # if basename < '0':
                    #   k = os.path.join(os.path.split(k)[0], "z" + basename)
                    return k.lower()

                files = natsort.natsorted(files, alg=natsort.ns.IC | natsort.ns.I)

            # make a sub-list of image files
            self.page_list = []
            for name in files:
                if os.path.splitext(name)[1].lower() in [".jpg", "jpeg", ".png", ".gif", ".webp"] and os.path.basename(name)[0] != ".":
                    self.page_list.append(name)

        return self.page_list

    def getNumberOfPages(self):
        if self.page_count is None:
            self.page_count = len(self.getPageNameList())
        return self.page_count

    def readCBI(self):
        if self.cbi_md is None:
            raw_cbi = self.readRawCBI()
            if raw_cbi is None:
                self.cbi_md = GenericMetadata()
            else:
                self.cbi_md = ComicBookInfo().metadataFromString(raw_cbi)

            self.cbi_md.setDefaultPageList(self.getNumberOfPages())

        return self.cbi_md

    def readRawCBI(self):
        if not self.hasCBI():
            return None

        return self.archiver.getComment()

    def hasCBI(self):
        if self.has_cbi is None:
            if not self.seemsToBeAComicArchive():
                self.has_cbi = False
            else:
                comment = self.archiver.getComment()
                self.has_cbi = ComicBookInfo().validateString(comment)

        return self.has_cbi

    def writeCBI(self, metadata):
        if metadata is not None:
            self.applyArchiveInfoToMetadata(metadata)
            cbi_string = ComicBookInfo().stringFromMetadata(metadata)
            write_success = self.archiver.setComment(cbi_string)
            if write_success:
                self.has_cbi = True
                self.cbi_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCBI(self):
        if self.hasCBI():
            write_success = self.archiver.setComment("")
            if write_success:
                self.has_cbi = False
                self.cbi_md = None
            self.resetCache()
            return write_success
        return True

    def readCIX(self):
        if self.cix_md is None:
            raw_cix = self.readRawCIX()
            if raw_cix is None or raw_cix == "":
                self.cix_md = GenericMetadata()
            else:
                self.cix_md = ComicInfoXml().metadataFromString(raw_cix)

            # validate the existing page list (make sure count is correct)
            if len(self.cix_md.pages) != 0:
                if len(self.cix_md.pages) != self.getNumberOfPages():
                    # pages array doesn't match the actual number of images we're seeing
                    # in the archive, so discard the data
                    self.cix_md.pages = []

            if len(self.cix_md.pages) == 0:
                self.cix_md.setDefaultPageList(self.getNumberOfPages())

        return self.cix_md

    def readRawCIX(self):
        if not self.hasCIX():
            return None
        try:
            raw_cix = self.archiver.readFile(self.ci_xml_filename)
        except IOError:
            print("Error reading in raw CIX!")
            raw_cix = ""
        return raw_cix

    def writeCIX(self, metadata):
        if metadata is not None:
            self.applyArchiveInfoToMetadata(metadata, calc_page_sizes=True)
            cix_string = ComicInfoXml().stringFromMetadata(metadata)
            write_success = self.archiver.writeFile(self.ci_xml_filename, cix_string)
            if write_success:
                self.has_cix = True
                self.cix_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCIX(self):
        if self.hasCIX():
            write_success = self.archiver.removeFile(self.ci_xml_filename)
            if write_success:
                self.has_cix = False
                self.cix_md = None
            self.resetCache()
            return write_success
        return True

    def hasCIX(self):
        if self.has_cix is None:

            if not self.seemsToBeAComicArchive():
                self.has_cix = False
            elif self.ci_xml_filename in self.archiver.getFilenameList():
                self.has_cix = True
            else:
                self.has_cix = False
        return self.has_cix

    def readCoMet(self):
        if self.comet_md is None:
            raw_comet = self.readRawCoMet()
            if raw_comet is None or raw_comet == "":
                self.comet_md = GenericMetadata()
            else:
                self.comet_md = CoMet().metadataFromString(raw_comet)

            self.comet_md.setDefaultPageList(self.getNumberOfPages())
            # use the coverImage value from the comet_data to mark the cover in this struct
            # walk through list of images in file, and find the matching one for md.coverImage
            # need to remove the existing one in the default
            if self.comet_md.coverImage is not None:
                cover_idx = 0
                for idx, f in enumerate(self.getPageNameList()):
                    if self.comet_md.coverImage == f:
                        cover_idx = idx
                        break
                if cover_idx != 0:
                    del self.comet_md.pages[0]["Type"]
                    self.comet_md.pages[cover_idx]["Type"] = PageType.FrontCover

        return self.comet_md

    def readRawCoMet(self):
        if not self.hasCoMet():
            errMsg = "{} doesn't have CoMet data!".format(self.path)
            logger.info(errMsg)
            return None

        try:
            raw_comet = self.archiver.readFile(self.comet_filename)
        except IOError:
            errMsg = "Error reading in raw CoMet!"
            logger.info(errMsg)
            raw_comet = ""
        return raw_comet

    def writeCoMet(self, metadata):

        if metadata is not None:
            if not self.hasCoMet():
                self.comet_filename = self.comet_default_filename

            self.applyArchiveInfoToMetadata(metadata)
            # Set the coverImage value, if it's not the first page
            cover_idx = int(metadata.getCoverPageIndexList()[0])
            if cover_idx != 0:
                metadata.coverImage = self.getPageName(cover_idx)

            comet_string = CoMet().stringFromMetadata(metadata)
            write_success = self.archiver.writeFile(self.comet_filename, comet_string)
            if write_success:
                self.has_comet = True
                self.comet_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCoMet(self):
        if self.hasCoMet():
            write_success = self.archiver.removeFile(self.comet_filename)
            if write_success:
                self.has_comet = False
                self.comet_md = None
            self.resetCache()
            return write_success
        return True

    def hasCoMet(self):
        if self.has_comet is None:
            self.has_comet = False
            if not self.seemsToBeAComicArchive():
                return self.has_comet

            # look at all xml files in root, and search for CoMet data, get first
            for n in self.archiver.getFilenameList():
                if os.path.dirname(n) == "" and os.path.splitext(n)[1].lower() == ".xml":
                    # read in XML file, and validate it
                    try:
                        data = self.archiver.readFile(n)
                    except:
                        data = ""
                        errMsg = "Error reading in Comet XML for validation!"
                        logger.info(errMsg)
                    if CoMet().validateString(data):
                        # since we found it, save it!
                        self.comet_filename = n
                        self.has_comet = True
                        break

            return self.has_comet

    def applyArchiveInfoToMetadata(self, md, calc_page_sizes=False):
        md.pageCount = self.getNumberOfPages()

        if calc_page_sizes:
            for p in md.pages:
                idx = int(p["Image"])
                if pil_available:
                    if "ImageSize" not in p or "ImageHeight" not in p or "ImageWidth" not in p:
                        data = self.getPage(idx)
                        if data is not None:
                            try:
                                if isinstance(data, bytes):
                                    im = Image.open(io.BytesIO(data))
                                else:
                                    im = Image.open(io.StringIO(data))
                                w, h = im.size

                                p["ImageSize"] = str(len(data))
                                p["ImageHeight"] = str(h)
                                p["ImageWidth"] = str(w)
                            except IOError:
                                p["ImageSize"] = str(len(data))

                else:
                    if "ImageSize" not in p:
                        data = self.getPage(idx)
                        p["ImageSize"] = str(len(data))

    def metadataFromFilename(self, parse_scan_info=True):

        metadata = GenericMetadata()

        fnp = FileNameParser()
        fnp.parseFilename(self.path)

        if fnp.issue != "":
            metadata.issue = fnp.issue
        if fnp.series != "":
            metadata.series = fnp.series
        if fnp.volume != "":
            metadata.volume = fnp.volume
        if fnp.year != "":
            metadata.year = fnp.year
        if fnp.issue_count != "":
            metadata.issueCount = fnp.issue_count
        if parse_scan_info:
            if fnp.remainder != "":
                metadata.scanInfo = fnp.remainder

        metadata.isEmpty = False

        return metadata

    def exportAsZip(self, zipfilename):
        if self.archive_type == self.ArchiveType.Zip:
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver(zipfilename)
        return zip_archiver.copyFromArchive(self.archiver)
