from __future__ import annotations

import logging
from typing import List

from ubift.src.exception import UBIFTException
from ubift.src.framework.base import find_signature
from ubift.src.framework.volume_layer.ubi_structs import UBI_EC_HDR, UBI_VID_HDR

ubiftlog = logging.getLogger(__name__)

class Image:
    """
    A Image is a raw dump file, i.e., bunch of bytes from a NAND flash.
    Basically, an Image represents an MTD device which can have multiple MTD-partitions.
    """
    def __init__(self, data: bytes, block_size: int = -1, page_size: int = -1, oob_size: int = -1):
        self._oob_size = oob_size
        self._page_size = page_size if page_size > 0 else self._guess_page_size(data)
        self._block_size = block_size if block_size > 0 else self._guess_block_size(data)
        self._data = data if oob_size < 0 else Image.strip_oob(data, self.block_size, self.page_size, oob_size)
        self._partitions = []

        if len(data) % block_size != 0:
            ubiftlog.error(
                f"[-] Invalid block_size (data_len: {len(self.data)} not divisible by block_size {block_size})")
        if block_size % page_size != 0:
            ubiftlog.error(
                f"[-] Invalid page_size (block_size: {block_size} not divisible by page_size {page_size})")

        ubiftlog.info(f"[!] Initialized Image (block_size:{self.block_size}, page_size:{self.page_size}, oob_size:{self.oob_size}, data_len:{len(self.data)})")

    @property
    def partitions(self):
        return self._partitions

    def get_full_partitions(self) -> List[Partition]:
        """

        Returns: Returns a list of Partitions that cover the full size of the Image. If a certain space is
        not covered by a specific Partition in the Image, a temporary Partition is created to mark 'unallocated' space.

        """

        full_partitions = self.partitions.copy()
        self.partitions.sort(key=lambda partition: partition.offset)

        for i,partition in enumerate(self.partitions):
            if i+1 >= len(self.partitions):
                # Add 'unallocated' Partition at the end if necessary
                if partition.offset + partition.len != len(self.data):
                    end_partition = Partition(self, partition.offset + partition.len + 1, len(self.data) - (partition.offset + partition.len + 1), "Unallocated")
                    full_partitions.append(end_partition)
                break
            # Add 'unallocated' Partition at the start if necessary
            if i == 0 and (partition.offset != 0):
                start_partition = Partition(self, 0, self.partitions[i].offset - 1, "Unallocated")
                full_partitions.insert(0, start_partition)
            # Add 'unallocated' Partitions in between Partitions if necessary
            if partition.offset + partition.len + 1 != self.partitions[i+1].offset:
                end = self.partitions[i + 1].offset - 1
                start = self.partitions[i].offset + self.partitions[i].len + 1
                between_partition = Partition(self, start, end-start, "Unallocated")
                full_partitions.insert(full_partitions.index(partition)+1, between_partition)

        return full_partitions
    
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
        ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
        if ec_hdr_offset < 0:
            raise UBIFTException("Block size not specified, cannot guess size neither because no UBI_EC_HDR signatures found.")
        possible_block_sizes = [i*self.page_size if self.oob_size < 0 else (i*self.page_size+i*self.oob_size) for i in range(1, 512)]
        for i,block_size in enumerate(possible_block_sizes):
            if data[ec_hdr_offset+block_size:ec_hdr_offset+block_size+4] == UBI_EC_HDR.__magic__:
                guessed_size = (self.page_size * (i+1))
                ubiftlog.info(f"[+] Guessed block_size: {guessed_size} ({guessed_size / 1024}KiB)")
                return guessed_size

        raise UBIFTException(f"[-] Block size not specified, cannot guess size neither.")

    def _guess_page_size(self, data: bytes) -> int:
        """
        Tries to guess the page size by calculating the space between an ubi_ec_hdr and a ubi_vid_hdr
        NOTE: This will fail if the flash allows sub-paging because UBI will use that feature to fit both headers inside one page
        :return:
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
        TODO: OOB can also be located as a group in some flashes
        """

        ubiftlog.info(f"[!] Stripping OOB with size {oob_size} from every page.")

        ptr = 0
        pages = block_size // page_size
        block_size = block_size + pages * oob_size
        blocks = len(data) // block_size

        stripped_data = bytearray()
        for block in range(blocks):
            ptr = block * 64 * page_size
            for page in range(pages):
                stripped_data += data[ptr:ptr+page_size]
                ptr += oob_size

        return stripped_data

class Partition:
    """
    A Partition represents an MTD-partition.
    """
    def __init__(self, image: Image, offset: int, len: int, name: str):
        self._image = image
        self._offset = offset
        self._len = len
        self._name = name
        self._ubi_instances = []

        ubiftlog.info(
            f"[!] Initialized Partition {self.offset} to {self.offset+self.len} "
            f"(len: {self.len}, blocks: {((self.offset+self.len) - self.offset) // self.image.block_size})")

    @property
    def ubi_instances(self):
        return self._ubi_instances

    @property
    def image(self):
        return self._image

    @property
    def offset(self):
        return self._offset

    @property
    def len(self):
        return self._len

    @property
    def name(self):
        return self._name

