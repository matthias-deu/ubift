from __future__ import annotations

from typing import List

from ubift.framework.mtd import Partition
from ubift.framework.structs.ubi_structs import UBI_VTBL_RECORD, UBI_EC_HDR, VTBL_VOLUME_ID, UBI_VID_HDR
from ubift.framework.structs.ubifs_structs import UBIFS_CH, UBIFS_NODE_TYPES, UBIFS_DENT_NODE
from ubift.framework.util import find_signature
from ubift.logging import ubiftlog


class UBIVolume:
    """
    Represents an UBI volume within an UBI instance.
    Note: All PEBs that are mapped by LEBs are relative to the UBI instance, e.g., LEB x mapped to PEB 0
     does not refer to the PEB which is at the start of the image dump but at the start of the UBI instance
    """
    def __init__(self, ubi: UBI, vol_num: int, lebs: List[LEB], vtbl_record: UBI_VTBL_RECORD):
        self._ubi = ubi
        self._vol_num = vol_num
        self._lebs = {leb.leb_num: leb for leb in lebs}
        self._vtbl_record = vtbl_record

    @property
    def ubi(self):
        return self._ubi

    @property
    def name(self):
        return self._vtbl_record.formatted_name()

    @property
    def lebs(self):
        return self._lebs

    def __str__(self):
        return f"UBI Volume '{self.name}' (vol_index: {self._vol_num})" # LEBs: {len(self._lebs)}"


class UBI:
    """
    Represents an UBI instance which can have multiple UBIVolumes.
    The 'offset' and 'end'-fields are relative to the Partition.
    """

    def __init__(self, partition: Partition, offset: int = -1, end: int = -1):
        self._partition = partition
        self._offset = offset if offset >= 0 else 0
        self._end = end if end >= 0 else (partition.end - partition.offset)
        self._volumes = []

        if self._validate() == False:
            ubiftlog.error(
                f"[-] Invalid UBI instance for Partition {partition} at offset {self._offset}, end: {self._end}")

        # Populates self._volumes by searching and parsing the layout volume and its vtbl_records
        self._parse_volumes()

        ubiftlog.info(
            f"[!] Initialized UBI instance for Partition {partition} (offset: {self._offset}, end:{self._end})")

        self._partition.ubi_instance = self

    def __len__(self):
        return self._end - self._offset + 1

    @property
    def offset(self):
        return self._offset

    @property
    def peb_offset(self):
        return self.partition.offset // self.partition.image.block_size

    def end(self):
        return self._end

    @property
    def volumes(self):
        return self._volumes

    def get_volume(self, name: str) -> UBIVolume:
        """
        Gets an UBIVolume by name
        :param name: Name of the UBIVolume
        :return: UBIVolume with name or None if there is no such UBIVolume
        """
        for volume in self.volumes:
            if volume.name == name:
                return volume
        return None

    @property
    def partition(self):
        return self._partition

    def _validate(self) -> bool:
        """
        Checks if this is a valid and non-faulty UBI instance by making sure that every PEB has an erase counter header.
        @return: True if this is a valid UBI instance, otherwise False.
        """
        image = self._partition.image
        for i in range(0, len(self), image.block_size):
            if image.data[
               self.partition.offset + self._offset + i:self.partition.offset + self._offset + i + 4] != UBI_EC_HDR.__magic__:
                return False
        return True

    def _parse_volumes(self) -> None:
        volume_table = {}  # Maps volume_number to a list of LEBS belonging to it
        image = self._partition.image
        for peb_num, offset in enumerate(range(0, len(self), image.block_size)):
            leb = LEB(self, peb_num)
            if leb.is_mapped():
                if leb.vid_hdr.vol_id not in volume_table:
                    volume_table[leb.vid_hdr.vol_id] = [leb]
                else:
                    volume_table[leb.vid_hdr.vol_id].append(leb)

        # TODO: Should this also create volumes from internal volumes such as the layout volume and fastmap volumes?

        if VTBL_VOLUME_ID not in volume_table:
            ubiftlog.error(
                f"[-] There is no 'layout volume' in the UBI instance, therefore UBI volumes cannot be parsed correctly.")
        else:
            self._parse_vtbl_records(volume_table)

    def _parse_vtbl_records(self, block_table: dict[int, List['LEB']]) -> None:
        vtbl_blocks = block_table[VTBL_VOLUME_ID]
        offset = self._partition.offset + self._offset + vtbl_blocks[0]._peb_num * self.partition.image.block_size
        ec_hdr = UBI_EC_HDR(self._partition.image.data, offset)
        data_offset = ec_hdr.data_offset

        for i in range(128):
            vtbl_record = UBI_VTBL_RECORD(self._partition.image.data, offset + data_offset + i * UBI_VTBL_RECORD.size)
            if vtbl_record.reserved_pebs > 0:
                vol = self._create_volume(i, vtbl_record, block_table)
                self.volumes.append(vol)

    def _create_volume(self, vol_num: int, vtbl_record: UBI_VTBL_RECORD,
                       block_table: dict[int, List[LEB]]) -> UBIVolume:
        vol = UBIVolume(self, vol_num, block_table[vol_num], vtbl_record)

        ubiftlog.info(
            f"[+] Created UBI Volume '{vol.name}' (vol_num: {vol_num}, PEBs: {len(block_table[vol_num])}).")

        return vol


class LEB():
    def __init__(self, ubi_instance: UBI, peb_num: int):
        self._ubi_instance = ubi_instance
        self._peb_num = peb_num

        image = ubi_instance.partition.image
        self._ec_hdr = UBI_EC_HDR(image.data,
                                  ubi_instance.partition.offset + ubi_instance.offset + peb_num * image.block_size)
        self._vid_hdr = UBI_VID_HDR(image.data,
                                    ubi_instance.partition.offset + ubi_instance.offset + peb_num * image.block_size + self.ec_hdr.vid_hdr_offset)

    def __repr__(self):
        return f"{self.leb_num} -> {self._peb_num}"

    @property
    def size(self) -> int:
        return self._ubi_instance.partition.image.block_size - self.ec_hdr.data_offset

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
        return data[start:start + image.block_size - self.ec_hdr.data_offset]
