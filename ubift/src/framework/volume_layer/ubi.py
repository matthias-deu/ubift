import os
from typing import List

import cstruct
import struct
import logging

from ubift.src.framework.disk_image_layer.mtd import Partition
from ubift.src.framework.volume_layer.ubi_structs import UBI_EC_HDR, UBI_VID_HDR, VTBL_VOLUME_ID, UBI_VTBL_RECORD

ubiftlog = logging.getLogger(__name__)


class UBIVolume:
    def __init__(self, vol_num: int, blocks: List[int], vtbl_record: UBI_VTBL_RECORD):
        self._vol_num = vol_num
        self._blocks = blocks
        self._vtbl_record = vtbl_record
    @property
    def name(self):
        return self._vtbl_record.formatted_name()

class UBI:
    """
    Represents an UBI instance which can have zero or more UBIVolumes.
    """
    def __init__(self, partition: Partition, offset: int = -1, len: int = -1):
        self._partition = partition
        self._offset = offset if offset >= 0 else 0
        self._len = len if len >= 0 else partition.len
        self._volumes = []

        if self._validate() == False:
            ubiftlog.error(f"[-] Invalid UBI instance for Partition {partition} at offset {self._offset}, len: {self._len}")

        # Populates self._volumes by searching and parsing the layout volume and its vtbl_records
        self._parse_volumes()

        ubiftlog.info(f"[!] Initialized UBI instance for Partition {partition} (offset: {offset}, len:{len})")

    @property
    def offset(self):
        return self._offset

    @property
    def volumes(self):
        return self._volumes

    @property
    def partition(self):
        return self._partition

    def _validate(self) -> bool:
        """
        Checks if this is a valid UBI instance
        @return: True if this is a valid UBI instance, otherwise False.
        """
        image = self._partition.image
        for i in range(0, self._len, image.block_size):
            if image.data[self.partition.offset+self._offset+i:self.partition.offset+self._offset+i+4] != UBI_EC_HDR.__magic__:
                return False
        return True

    def _parse_volumes(self):
        volume_table = {} # Maps volume_number to a list of blocks belonging to it
        image = self._partition.image
        for peb_num,offset in enumerate(range(0, self._len, image.block_size)):
            #leb = LEB(self, peb_num)
            ec_hdr = UBI_EC_HDR(image.data, self.partition.offset+self._offset+offset)
            vid_hdr_offset = self.partition.offset+self._offset+offset+ec_hdr.vid_hdr_offset
            if image.data[vid_hdr_offset:vid_hdr_offset+4] == UBI_VID_HDR.__magic__:
                vid_hdr = UBI_VID_HDR(image.data, vid_hdr_offset)
                if vid_hdr.vol_id not in volume_table:
                    volume_table[vid_hdr.vol_id] = [peb_num]
                else:
                    volume_table[vid_hdr.vol_id].append(peb_num)

        if VTBL_VOLUME_ID not in volume_table:
            ubiftlog.error(
                f"[-] There is no 'layout volume' in the UBI instance, therefore UBI volumes cannot be parsed correctly.")
        else:
            self._parse_vtbl_records(volume_table)

    def _parse_vtbl_records(self, block_table: dict[int, List[int]]) -> None:
        vtbl_blocks = block_table[VTBL_VOLUME_ID]
        offset = self._partition.offset + self._offset + vtbl_blocks[0] * self.partition.image.block_size
        ec_hdr = UBI_EC_HDR(self._partition.image.data, offset)
        data_offset = ec_hdr.data_offset

        for i in range(128):
            vtbl_record = UBI_VTBL_RECORD(self._partition.image.data, offset + data_offset + i * UBI_VTBL_RECORD.size)
            if vtbl_record.reserved_pebs > 0:
                vol = self._create_volume(i, vtbl_record, block_table)
                self.volumes.append(vol)

    def _create_volume(self, vol_num: int, vtbl_record: UBI_VTBL_RECORD, block_table: dict[int, List[int]]) -> UBIVolume:
        vol = UBIVolume(vol_num, block_table[vol_num], vtbl_record)

        ubiftlog.info(
            f"[+] Created UBI Volume '{vol.name}' (vol_num: {vol_num}, blocks: {len(block_table[vol_num])}).")

        return vol

class LEB():
    def __init__(self, ubi_instance: UBI, peb_num: int):
        self._ubi_instance = ubi_instance
        self._peb_num = peb_num

        image = ubi_instance.partition.image
        self._ec_hdr = UBI_EC_HDR(image.data, ubi_instance.partition.offset + ubi_instance.offset + peb_num * image.block_size)
        self._vid_hdr = UBI_VID_HDR(image.data, ubi_instance.partition.offset + ubi_instance.offset + peb_num * image.block_size + self.ec_hdr.vid_hdr_offset)

    @property
    def size(self) -> int:
        return self._ubi_instance.partition.image.block_size-self.ec_hdr.data_offset

    @property
    def ec_hdr(self):
        return self._ec_hdr

    @property
    def vid_hdr(self):
        return self._vid_hdr

    @property
    def leb_num(self):
        return self._vid_hdr.lnum if self._vid_hdr.validate_magic() else -1

    def is_mapped(self) -> bool:
        return self._vid_hdr.validate_magic() and self._vid_hdr.lnum >= 0

    @property
    def data(self):
        image = self._ubi_instance.partition.image
        data = image.data
        start = self._ubi_instance.partition.offset + self._ubi_instance.offset + self._peb_num * image.block_size
        start += self.ec_hdr.data_offset
        return data[start:start+image.block_size-self.ec_hdr.data_offset]




