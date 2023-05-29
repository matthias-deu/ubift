from __future__ import annotations

import logging
from typing import List

from ubift.exception import UBIFTException
from ubift.framework.structs.ubi_structs import UBI_EC_HDR
from ubift.framework.util import find_signature

ubiftlog = logging.getLogger(__name__)

class Image:
    """
    A Image is a raw dump file, i.e., bunch of bytes from a NAND flash.
    Basically, an Image represents an MTD device which can have multiple MTD-partitions.

    The block_size is the size of a full PEB, without OOB
    The page_size is the minimal I/O unit, without OOB
    If pages contain an extra OOB area after their data, this can be specified in 'oob_size'
    """
    def __init__(self, data: bytes, block_size: int = -1, page_size: int = -1, oob_size: int = -1):
        self._oob_size = oob_size
        self._page_size = page_size if page_size > 0 else self._guess_page_size(data)
        self._block_size = block_size if block_size > 0 else self._guess_block_size(data)
        self._data = data if oob_size <= 0 else Image.strip_oob(data, self.block_size, self.page_size, oob_size)
        self._partitions = []

        if len(self._data) % block_size != 0:
            ubiftlog.error(
                f"[-] Invalid block_size (data_len: {len(self.data)} not divisible by block_size {block_size})")
        if block_size % page_size != 0:
            ubiftlog.error(
                f"[-] Invalid page_size (block_size: {block_size} not divisible by page_size {page_size})")

        ubiftlog.info(f"[!] Initialized Image (block_size:{self.block_size}, page_size:{self.page_size}, oob_size:{self.oob_size}, data_len:{len(self.data)})")

    @property
    def partitions(self) -> List[Partition]:
        if len(self._partitions) == 0:
            return [Partition(self, 0, len(self.data)-1, "Unallocated")]
        return self._partitions
    
    @partitions.setter
    def partitions(self, partitions: List[Partition]):
        self._partitions = partitions

    @property
    def data(self):
        return self._data

    @property
    def oob_size(self):
        return self._oob_size

    @property
    def block_size(self):
        return self._block_size

    @property
    def page_size(self):
        return self._page_size

    def _guess_block_size(self, data: bytes) -> int:
        """
        Tries to 'guess' the size of a PEB. This is done by searching for a "UBI#" signature (ec-header)
        and calculating its distance to the next ec-header. Therefore, this method requires the data to have at least one instance of UBI.
        TODO: The block-size can also be looked up in the UBIFS supernode
        :param data:
        :return: Size of a PEB or raises an exception if guess failed.
        """
        ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
        if ec_hdr_offset < 0:
            raise UBIFTException("Block size not specified, cannot guess size neither because no UBI_EC_HDR signatures found.")
        possible_block_sizes = [i*self.page_size if self.oob_size < 0 else (i*self.page_size+i*self.oob_size) for i in range(1, 1024)]

        # print(possible_block_sizes)
        # print(ec_hdr_offset)
        # a = find_signature(data, UBI_EC_HDR.__magic__, ec_hdr_offset + 1)
        # print(a)
        # print(a - ec_hdr_offset)
        # exit()

        for i,block_size in enumerate(possible_block_sizes):
            if data[ec_hdr_offset+block_size:ec_hdr_offset+block_size+4] == UBI_EC_HDR.__magic__:
                guessed_size = (self.page_size * (i+1))
                ubiftlog.info(f"[+] Guessed block_size: {guessed_size} ({guessed_size / 1024}KiB)")
                return guessed_size

        raise UBIFTException(f"[-] Block size not specified, cannot guess size neither.")

    def _guess_page_size(self, data: bytes) -> int:
        """
        Tries to guess the page size by calculating the space between an ubi_ec_hdr and a ubi_vid_hdr.
        This is simply done by looking at the 'vid_hdr_offset' field of an ec-header.
        :return: Size of a page or raises an exception if guess failed.
        """
        ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
        if ec_hdr_offset < 0:
            raise UBIFTException(
                "Page size not specified, cannot guess size neither because no UBI_EC_HDR signatures found.")
        ec_hdr = UBI_EC_HDR(data, ec_hdr_offset)
        if ec_hdr.vid_hdr_offset > 0:
            ubiftlog.info(f"[+] Guessed page_size: {ec_hdr.vid_hdr_offset} ({ec_hdr.vid_hdr_offset / 1024}KiB)")
            return ec_hdr.vid_hdr_offset

        raise UBIFTException(f"[-] Page size not specified, cannot guess size neither.")

    @classmethod
    def strip_oob(cls, data: bytes, block_size: int, page_size: int, oob_size: int) -> bytes:
        """
        Strips OOB data out of binary data. This assumes that the OOB is located at the end of every page.
        TODO: OOB can also be located as a group in some flashes (needs testing)
        """

        ubiftlog.info(f"[!] Stripping OOB with size {oob_size} from every page.")

        ptr = 0
        pages = block_size // page_size
        block_size = block_size + pages * oob_size
        blocks = len(data) // block_size

        stripped_data = bytearray()
        for page in range(0, len(data), 2112):
            stripped_data += data[page:page + page_size]

        return bytes(stripped_data)

class Partition:
    """
    A Partition represents an MTD-partition.
    """
    def __init__(self, image: Image, offset: int, end: int, name: str):
        self._image = image
        self._offset = offset
        self._end = end
        self._name = name
        self._ubi_instance = None

        if len(self) % self.image.block_size != 0:
            ubiftlog.error(f"[-] Partition {self.name} is not aligned to erase block size.")

        ubiftlog.info(
            f"[!] Initialized Partition {self.offset} to {self.end} "
            f"(len: {len(self)}, PEBs: {(len(self)) // self.image.block_size})")

    def __len__(self):
        return self._end - self._offset + 1

    @property
    def data(self):
        return self.image.data[self.offset:self.end+1]

    @property
    def ubi_instance(self):
        return self._ubi_instance

    @ubi_instance.setter
    def ubi_instance(self, value):
        self._ubi_instance = value

    @property
    def image(self):
        return self._image

    @property
    def offset(self):
        return self._offset

    @property
    def end(self):
        return self._end

    @property
    def name(self):
        return self._name

