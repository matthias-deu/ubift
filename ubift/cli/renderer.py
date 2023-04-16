import logging
import os
import sys
import tempfile
from datetime import datetime
from typing import Dict, List

from ubift.framework import ubifs
from ubift.framework.mtd import Image
from ubift.framework.structs.ubi_structs import UBI_VTBL_RECORD
from ubift.framework.structs.ubifs_structs import UBIFS_DENT_NODE, UBIFS_INODE_TYPES, UBIFS_INO_NODE, UBIFS_KEY, \
    UBIFS_DATA_NODE, UBIFS_KEY_TYPES
from ubift.framework.ubi import UBIVolume
from ubift.framework.ubifs import UBIFS
from ubift.logging import ubiftlog


def readable_size(num: int, suffix="B"):
    """
    Converts amount of bytes to a readable format depending on its size.
    Example: 336896B -> 329KiB
    :param num:
    :param suffix:
    :return:
    """
    if num < 0:
        return "-"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}" if unit != "" else f"{num:}B"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def zpad(num: int, len: str) -> int:
    """
    Pads a number with a given amount of zeroes.
    Example: "1" with len of 3 will be padded to 001
    :param num: The number to be padded with zeroes.
    :param len: How many digits the output number will contain, filled with zeroes at the beginning.
    :return: Zero-padded digit.
    """
    len = "0" + str(len)
    return format(num, len)


def render_inode_list(image: Image, ubifs: UBIFS, inodes: Dict[int, UBIFS_DATA_NODE], human_readable: bool = True,
                      outfd=sys.stdout) -> None:
    """
    Renders a list of inodes to given output. Utilizes same sequence as TSK ils (apart from st_block0, st_block1 and st_alloc entries), see http://www.sleuthkit.org/sleuthkit/man/ils.html
    For the "modes" field in an inode, refer to https://man7.org/linux/man-pages/man7/inode.7.html, it has file_type and a file_mode components
    :param image:
    :param ubifs:
    :param inodes:
    :param outfd:
    :return:
    """
    outfd.write(f"inum,uid,gid,mtime,atime,ctime,mode,nlink,inode_size\n")
    for inum, inode in inodes.items():
        uid = inode.uid
        gid = inode.gid
        mtime = inode.mtime_sec if not human_readable else datetime.utcfromtimestamp(inode.mtime_sec).strftime(
            "%Y-%m-%d %H:%M:%S")
        atime = inode.atime_sec if not human_readable else datetime.utcfromtimestamp(inode.atime_sec).strftime(
            "%Y-%m-%d %H:%M:%S")
        ctime = inode.ctime_sec if not human_readable else datetime.utcfromtimestamp(inode.ctime_sec).strftime(
            "%Y-%m-%d %H:%M:%S")
        mode = inode.mode if not human_readable else f"{InodeMode(inode.mode).file_type}|{InodeMode(inode.mode).full_perm}"
        nlink = inode.nlink
        size = inode.ino_size if not human_readable else readable_size(inode.ino_size)

        sys.stdout.write(f"{inum}|{uid}|{gid}|{mtime}|{atime}|{ctime}|{mode}|{nlink}|{size}\n")


class InodeMode:
    """
    Wrapper class for the "mode" field in an UBIFS_INODE_NODE
    It conforms to the POSIX standard. More about the "mode" field can be found at https://man7.org/linux/man-pages/man7/inode.7.html
    It uses 4 bits for the file_type and 12 bits for file_permission

    types:
     1100 sock (12)
     1010 lnk  (10)
     1000 reg  (8)
     0110 blk  (14)
     0100 dir  (4)
     0010 chr  (2)
     0001 fifo (1)

    Example: 000 000 00|0 000| 000 000 000 000
                        type      permission

    file permission is organized like this:
    4000 suid
    2000 sgid
    1000 sticky bit

    0007 rwx for others  -> 000 000 000 111
    0004 r for others
    0002 w for others
    0001 x for others

    second "column" is for group, third for owner
    """
    _file_types = {12: "SOCKET", 10: "LINK", 8: "FILE", 14: "BLOCK DEV", 4: "DIR", 2: "CHAR DEV", 1: "FIFO"}

    def __init__(self, mode: int) -> None:
        self.mode = mode

    @property
    def full_perm(self) -> str:
        return self.owner_perm + self.grp_perm + self.other_perm

    @property
    def owner_perm(self) -> str:
        owner_bits = self.mode >> 6 & 7
        suid_bit = (self.mode >> 11) & 1
        r = f"{'r' if (owner_bits >> 2) & 1 else '-'}"
        w = f"{'w' if (owner_bits >> 1) & 1 else '-'}"
        if suid_bit:
            x = f"s"
        else:
            x = f"{'x' if (owner_bits) & 1 else '-'}"
        return r + w + x

    @property
    def grp_perm(self) -> str:
        grp_bits = self.mode >> 3 & 7
        sgid_bit = (self.mode >> 10) & 1
        r = f"{'r' if (grp_bits >> 2) & 1 else '-'}"
        w = f"{'w' if (grp_bits >> 1) & 1 else '-'}"
        if sgid_bit:
            x = f"s"
        else:
            x = f"{'x' if (grp_bits) & 1 else '-'}"
        return r + w + x

    @property
    def other_perm(self) -> str:
        other_bits = self.mode & 7
        sticky_bit = (self.mode >> 9) & 1
        r = f"{'r' if (other_bits >> 2) & 1 else '-'}"
        w = f"{'w' if (other_bits >> 1) & 1 else '-'}"
        if sticky_bit:
            x = f"t"
        else:
            x = f"{'x' if (other_bits) & 1 else '-'}"
        return r + w + x

    @property
    def file_type(self) -> str:
        return InodeMode._file_types[(self.mode >> 12) & 15]


def render_ubi_instances(image: Image, outfd=sys.stdout) -> None:
    """
    Writes all UBI instances of an Image to stdout in a readable format
    :param image:
    :param outfd:
    :return:
    """
    ubi_instances = []
    for partition in image.partitions:
        if partition.ubi_instance is not None:
            ubi_instances.append(partition.ubi_instance)

    outfd.write(f"UBI Instances: {len(ubi_instances)}\n\n")

    outfd.write(f"Units are in {readable_size(image.block_size)}-Erase Blocks\n")
    for i, ubi in enumerate(ubi_instances):
        outfd.write("\tStart\t\t\tEnd\t\t\tLength\n")
        index = zpad(i, 4)
        start = zpad(ubi.partition.offset // image.block_size, 10)
        end = zpad(ubi.partition.end // image.block_size, 10)
        length = zpad(len(ubi) // image.block_size, 10)
        outfd.write(f"{index}:\t{start}\t\t{end}\t\t{length}\n")

        outfd.write(f"|\n")
        outfd.write(f"|\tVolumes\n")
        outfd.write("|\tIndex\t\t\tReserved PEBs\t\tType\t\t\tName\n")
        for i, vol in enumerate(ubi.volumes):
            vol_index = vol._vol_num
            vol_reserved_pebs = vol._vtbl_record.reserved_pebs
            vol_type = "STATIC" if vol._vtbl_record.vol_type == 2 else "DYNAMIC" if vol._vtbl_record.vol_type == 1 else "UNKNOWN"
            vol_name = vol.name

            outfd.write(f"|\t{vol_index}\t\t\t{zpad(vol_reserved_pebs, 10)}\t\t{vol_type}\t\t\t{vol_name}\n")
        outfd.write(f"\n")


def render_lebs(vol: UBIVolume, outfd=sys.stdout):
    """
    Writes all LEBS to stdout in a readable format
    TODO: Maybe also write ec_hdr or more info in general?
    :param vol:
    :param outfd:
    :return:
    """
    outfd.write(f"UBI Volume Index:{vol._vol_num} Name:{vol.name}\n\n")

    outfd.write("LEB\t--->\tPEB\n")

    lebs = list(vol.lebs.values())
    lebs.sort(key=lambda leb: leb.leb_num)
    for leb in lebs:
        outfd.write(f"{zpad(leb.leb_num, 5)}\t--->\t{zpad(leb._peb_num, 5)}\n")


def write_to_file(inode: UBIFS_INO_NODE, data_nodes: List[UBIFS_DATA_NODE], abs_path: str) -> None:
    """
    Writes data_nodes to a file. Works like 'render_data_nodes' but writes data content to a given path
    :param inode:
    :param data_nodes:
    :param abs_path:
    :return:
    """

    if os.path.exists(abs_path):
        ubiftlog.error(f"[-] Cannot create file because it already exists: {abs_path}.")
        return

    with open(abs_path, mode="w+b") as f:
        accu_size = 0  # accumulated size of uncompressed data from data nodes
        for data_node in data_nodes:
            data_node_key = UBIFS_KEY.from_bytearray(data_node.key)
            block = data_node_key.payload

            f.seek(4096 * block)
            f.write(data_node.decompressed_data)

            accu_size += len(data_node.decompressed_data)

        if inode.ino_size > accu_size:
            ubiftlog.warning(
                f"[!] Size from inode field {inode.ino_size} is more than written bytes {accu_size}. Filling bytes with zeroes.")
            f.seek(inode.ino_size)
            f.truncate(inode.ino_size)
        elif accu_size > inode.ino_size:
            ubiftlog.error(
                f"[-] More data has been written ({accu_size}) than what should have written indicated by inode size {inode.ino_size}.")

        f.close()

        return


def render_data_nodes(ubifs: UBIFS, inode_num: int, data_nodes: List[UBIFS_DATA_NODE], outfd=sys.stdout) -> None:
    """
    Outputs the content of given data nodes. Also does some validation checks, e.g., checks if size of uncompressed
     data matches the size field in the corersponding UBIFS_INO_NODE
    :param inode_num:
    :param data_nodes:
    :param outfd:
    :return:
    """
    ubiftlog.info(f"[+] Found {len(data_nodes)} data nodes for inode number {inode_num}.")

    if data_nodes is None or len(data_nodes) == 0:
        ubiftlog.error(f"[-] No data nodes for inode number {inode_num} could not be found.")
        return
    else:
        with tempfile.TemporaryFile(mode="w+b") as temp_file:
            accu_size = 0  # accumulated size of uncompressed data from data nodes
            for data_node in data_nodes:
                data_node_key = UBIFS_KEY.from_bytearray(data_node.key)
                block = data_node_key.payload

                temp_file.seek(4096 * block)
                temp_file.write(data_node.decompressed_data)

                accu_size += len(data_node.decompressed_data)

            # Fetch inode_node and do some validation checks (compare its 'size' field with accumulated size of uncompressed data)
            inode_node = ubifs._find(ubifs._root_idx_node,
                                     UBIFS_KEY.create_key(inode_num, UBIFS_KEY_TYPES.UBIFS_INO_KEY, 0))
            if inode_node.ino_size > accu_size:
                ubiftlog.warning(
                    f"[!] Size from inode field {inode_node.ino_size} is more than written bytes {accu_size}. Filling bytes with zeroes.")
                temp_file.seek(inode_node.ino_size)
                temp_file.truncate(inode_node.ino_size)
            elif accu_size > inode_node.ino_size:
                ubiftlog.error(
                    f"[-] More data has been written ({accu_size}) than what should have written indicated by inode size {inode_node.ino_size}.")

            # Write data to disk or to stdout
            temp_file.seek(0)
            outfd.buffer.write(temp_file.read())
            ubiftlog.info(f"[+] Wrote {accu_size} bytes from data nodes for inum {inode_num}")

            temp_file.close()
            outfd.close()

            return


def render_ubi_vtbl_record(vtbl_record: UBI_VTBL_RECORD, outfd=sys.stdout):
    """
    Writes a singel vtbl_record to stdout in a readable format
    :param vtbl_record:
    :param outfd:
    :return:
    """
    outfd.write(f"Reserved PEBs: {vtbl_record.reserved_pebs}\n")
    outfd.write(f"Alignment: {vtbl_record.alignment}\n")
    outfd.write(f"Data Pad: {vtbl_record.data_pad}\n")
    outfd.write(
        f"Volume Type: {'STATIC' if vtbl_record.vol_type == 2 else 'DYNAMIC' if vtbl_record.vol_type == 1 else 'UNKNOWN'}\n")
    outfd.write(f"Update Marker: {vtbl_record.upd_marker}\n")
    outfd.write(f"Flags: {vtbl_record.flags}\n")
    outfd.write(f"CRC: {vtbl_record.crc}\n")


def render_inode_node(ubifs: UBIFS, inode: int, inode_node: UBIFS_INO_NODE, outfd=sys.stdout):
    # TODO: Everything is displayed in DEZIMAL, maybe this is not the best format for this case.
    # outfd.write(f"Inode {inode} of UBIFS Instance in UBI Volume {ubifs.ubi_volume.name}\n")
    for field in inode_node.__fields__:
        print(f"{field}: {getattr(inode_node, field)}")


def render_dents(ubifs: UBIFS, dents: Dict[int, UBIFS_DENT_NODE], full_paths: bool, outfd=sys.stdout) -> None:
    """
    Renders a dict of UBIFS_NODE_DENT to output (like fls in TSK)
    :param ubifs: UBIFS instance, needed to unroll paths
    :param dents: Dict of inode num->dent
    :param full_paths: If True, will print full paths of files
    :param outfd: Where to write output data
    :return:
    """
    dent_list = dents.values() if isinstance(dents, Dict) else dents

    outfd.write("Type\tInode\tName\n")
    for dent in dent_list:
        render_inode_type(dent.type)
        outfd.write(f"\t{dent.inum}\t")
        if full_paths:
            outfd.write(f"{ubifs._unroll_path(dent, dents)}")
        else:
            outfd.write(f"{dent.formatted_name()}")
        outfd.write("\n")


def render_inode_type(inode_type: int, outfd=sys.stdout):
    """
    Renders an UBIFS_INODE_TYPES to a readable format (no newline)
    :param inode_type:
    :return:
    """
    if inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_REG:
        outfd.write(f"file")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_DIR:
        outfd.write(f"dir")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_LNK:
        outfd.write(f"link")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_BLK:
        outfd.write(f"blk")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_CHR:
        outfd.write(f"chr")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_FIFO:
        outfd.write(f"link")
    elif inode_type == UBIFS_INODE_TYPES.UBIFS_ITYPE_SOCK:
        outfd.write(f"sock")
    else:
        outfd.write(f"unkn")


def render_image(image: Image, outfd=sys.stdout) -> None:
    """
    Writes information about an Image to stdout in a readable format
    :param image:
    :param outfd:
    :return:
    """
    outfd.write(f"MTD Image\n\n")
    outfd.write(f"Size: {readable_size(len(image.data))}\n")

    outfd.write(f"Erase Block Size: {readable_size(image.block_size)}\n")
    outfd.write(f"Page Size: {readable_size(image.page_size)}\n")
    outfd.write(f"OOB Size: {readable_size(image.oob_size)}\n\n")

    outfd.write(f"Physical Erase Blocks: {len(image.data) // image.block_size}\n")
    outfd.write(f"Pages per Erase Block: {image.block_size // image.page_size}\n")
    outfd.write("\n")

    outfd.write(f"Units are in {readable_size(image.block_size)}-Erase Blocks\n")
    mtd_parts = image.partitions

    outfd.write("\tStart\t\t\tEnd\t\t\tLength\t\t\tDescription\n")
    for i, partition in enumerate(mtd_parts):
        start = zpad(partition.offset // image.block_size, 10)
        end = zpad(partition.end // image.block_size, 10)
        length = zpad(len(partition) // image.block_size, 10)
        outfd.write(f"{zpad(i, 3)}:\t{start}\t\t{end}\t\t{length}\t\t{partition.name}\n")

    # TODO: Maybe add a switch if sizes in bytes are prefered?
    # outfd.write("\tStart\t\t\tEnd\t\t\tLength\t\t\tDescription\n")
    # for i,partition in enumerate(mtd_parts):
    #     start = zpad(partition.offset, 10)
    #     end = zpad(partition.end, 10)
    #     length = zpad(len(partition), 10)
    #     outfd.write(f"{zpad(i, 3)}:\t{start}\t\t{end}\t\t{length}\t\t{partition.name}\n")
