import argparse
import errno
import logging
import os
import struct
import sys
from typing import List
import codecs

from pathvalidate import sanitize_filepath

from ubift import exception
from ubift.cli.renderer import render_lebs, render_ubi_instances, render_image, render_dents, render_inode_node, \
    render_data_nodes, render_inodes, write_to_file, render_xents
from ubift.framework import visitor, structs
from ubift.framework.mtd import Image
from ubift.framework.partitioner import UBIPartitioner
from ubift.framework.structs.ubifs_structs import UBIFS_KEY, UBIFS_KEY_TYPES, UBIFS_INODE_TYPES, UBIFS_DENT_NODE, UBIFS_INO_NODE
from ubift.framework.ubi import UBI, UBIVolume
from ubift.framework.ubifs import UBIFS
from ubift.logging import ubiftlog

rootlog = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)-4s %(name)-3s: %(message)s")
console.setFormatter(formatter)

rootlog.setLevel(1)
rootlog.addHandler(console)


class CommandLine:

    def __init__(self):
        pass

    def run(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", help="Commands to run", required=True)

        # mtdls
        mtdls = subparsers.add_parser("mtdls",
                                      help="Lists information about all available Partitions, including UBI instances. UBI instances have the description 'UBI'.")
        self.add_default_mtd_args(mtdls)
        mtdls.set_defaults(func=self.mtdls)

        # mtdcat
        mtdcat = subparsers.add_parser("mtdcat",
                                       help="Outputs the binary data of an MTD partition, given by its index. Use 'mtdls' to see all indeces.")
        self.add_default_mtd_args(mtdcat)
        mtdcat.add_argument("index", type=int)
        mtdcat.set_defaults(func=self.mtdcat)

        # pebcat
        pebcat = subparsers.add_parser("pebcat", help="Outputs a specific phyiscal erase block.")
        self.add_default_mtd_args(pebcat)
        pebcat.add_argument("index", type=int)
        pebcat.set_defaults(func=self.pebcat)

        # ubils
        ubils = subparsers.add_parser("ubils", help="Lists all instances of UBI and their volumes.")
        self.add_default_mtd_args(ubils)
        self.add_default_ubi_args(ubils, ubils=True)
        ubils.set_defaults(func=self.ubils)

        # lebls
        lebls = subparsers.add_parser("lebls", help="Lists all mapped LEBs of a specific UBI volume.")
        self.add_default_mtd_args(lebls)
        lebls.set_defaults(func=self.lebls)

        # lebcat
        lebcat = subparsers.add_parser("lebcat",
                                       help="Outputs a specific mapped logical erase block of a specified UBI volume.")
        self.add_default_mtd_args(lebcat)
        lebcat.add_argument("lebnumber", help="Number of the logical erase block. Use 'lebls' to determine LEBs.", type=int)
        lebcat.add_argument("--headers", help="If set, will also output headers instead of just data of the LEB.", default=False,
                         action="store_true")
        lebcat.set_defaults(func=self.lebcat)

        # ubicat
        ubicat = subparsers.add_parser("ubicat", help="Outputs a specific UBI volume.")
        ubicat.add_argument("--headers", help="If set, output will include UBI headers instead of just data of the UBI volume.",
                            default=False,
                            action="store_true")
        self.add_default_mtd_args(ubicat)
        ubicat.set_defaults(func=self.ubicat)

        # fsstat
        fsstat = subparsers.add_parser("fsstat",
                                       help="Outputs information regarding the UBIFS file-system within a specific UBI volume.")
        self.add_default_mtd_args(fsstat)
        fsstat.set_defaults(func=self.fsstat)

        # fls
        fls = subparsers.add_parser("fls",
                                    help="Outputs information regarding file names in an UBIFS instance within a specific UBI volume.")
        self.add_default_mtd_args(fls)
        fls.add_argument("--path", "-p", help="If set, will output full paths for every file.", default=False,
                         action="store_true")
        fls.add_argument("--xentries", "-x", help="If set, will output xentries (extended attribute entries).", default=False, action="store_true")
        fls.add_argument("--scan", "-s",
                         help="If set, will perform scanning for signatures instead of traversing the file-index.",
                         default=False, action="store_true")
        fls.add_argument("--deleted", "-d",
                         help="Similar to scan. Will perform scanning for signatures instead of using the file index. Will only show deleted directory entries. This will take priority over --scan.",
                         default=False, action="store_true")
        fls.add_argument("--format", "-f", help="Output format. (default: %(default)s)", default="table", choices=["table", "csv"])
        fls.set_defaults(func=self.fls)

        # istat
        istat = subparsers.add_parser("istat", help="Displays information about a specific inode in an UBIFS instance.")
        self.add_default_mtd_args(istat)
        istat.add_argument("--scan", "-s",
                           help="If set, will perform scanning for inodes instead of traversing the file-index. Thus allowing to use istat on inodes that are no longer part of the file index.",
                           default=False, action="store_true")
        istat.add_argument("inode", help="Inode number.", type=int)
        istat.set_defaults(func=self.istat)

        # icat
        icat = subparsers.add_parser("icat", help="Outputs the data of an inode.")
        self.add_default_mtd_args(icat)
        icat.add_argument("inode", help="Inode number.", type=int)
        icat.add_argument("--output", help="If specified, will output data to given file.", type=argparse.FileType('w'))
        icat.add_argument("--scan", "-s",
                          help="If set, will perform scanning for signatures instead of traversing the file-index for data nodes. NOTE: This needs to be set if trying to restore deleted inodes.",
                          default=False, action="store_true")
        icat.set_defaults(func=self.icat)

        # ils
        ils = subparsers.add_parser("ils", help="Lists all inodes of a given UBIFS instance.")
        self.add_default_mtd_args(ils)
        ils.add_argument("--scan", "-s",
                         help="If set, will perform scanning for signatures instead of traversing the file-index.",
                         default=False, action="store_true")
        ils.add_argument("--deleted", "-d",
                         help="Similar to scan. Will perform scanning for signatures instead of using the file index. Will only show deleted inodes. This will take priority over --scan.",
                         default=False, action="store_true")
        ils.add_argument("--format", "-f", help="Output format. (default: %(default)s)", default="table", choices=["table", "csv"])
        ils.set_defaults(func=self.ils)

        # ffind
        ffind = subparsers.add_parser("ffind", help="Outputs directory entries associated with a given inode number.")
        self.add_default_mtd_args(ffind)
        ffind.add_argument("--path", "-p", help="If set, will output full paths for every file.", default=False,
                           action="store_true")
        ffind.add_argument("inode", help="Inode number.", type=int)
        ffind.add_argument("--scan", "-s",
                           help="If set, will perform scanning for signatures instead of traversing the file-index for data nodes. NOTE: This needs to be set if trying to find directory entries for deleted inodes.",
                           default=False, action="store_true")
        ffind.set_defaults(func=self.ffind)

        # jls
        jls = subparsers.add_parser("jls", help="Lists all nodes within the journal.")
        self.add_default_mtd_args(jls)
        jls.set_defaults(func=self.jls)

        # ubift_recover
        # This command is used by the Autopsy plugin
        ubift_recover = subparsers.add_parser("ubift_recover",
                                              help="Extracts all files found in UBIFS instances. Creates one directory for each UBI volume with UBIFS.")
        self.add_default_mtd_args(ubift_recover)
        ubift_recover.add_argument("--deleted", "-d",
                                   help="If this parameter is set, all inodes not present within the file index which are found by scanning the dump will be recovered if possible. For each UBIFS instance, the recovered files will be saved to an additional folder 'RECOVERED_FILES'.",
                                   default=False, action="store_true")
        ubift_recover.add_argument("--raw", "-r",
                                   help="If this parameter is set, UBI volumes that do not contain UBIFS will be output as binary data.",
                                   default=False, action="store_true")
        ubift_recover.add_argument("--output",
                                   help="Output directory where all files and directories will be dumped to.", type=str)
        ubift_recover.set_defaults(func=self.ubift_recover)

        # ubift_info
        ubift_info = subparsers.add_parser("ubift_info",
                                           help="Outputs information regarding recoverability of deleted inodes. This parameter takes priority over all other parameters.")
        self.add_default_mtd_args(ubift_info)
        ubift_info.add_argument("--inode_info", "-ii",
                                help="If set, will output recoverability information for every found deleted inode.",
                                default=False, action="store_true")
        ubift_info.set_defaults(func=self.ubift_info)

        # Adds default arguments such as --offset to all previously defined commands that operate in the UBI layer
        ubi_layer_commands = [lebls, jls, lebcat, ubicat, fls, istat, icat, ils, fsstat, ffind, ubift_info]
        for command in ubi_layer_commands:
            self.add_default_ubi_args(command)

        # Adds default arguments such as --master to all previously defined commands that operate in the UBIFS layer
        ubifs_layer_commands = [fls, ffind, istat, ils, jls]
        for command in ubifs_layer_commands:
            self.add_default_ubifs_args(command)

        args = parser.parse_args()
        args.func(args)

    def add_default_ubifs_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Adds default arguments to Parsers for commands that work on the file system (UBIFS) layer
        :param ubifs_parser:
        :return:
        """
        parser.add_argument("--master",
                            help="Defines the index of which master node will be used. Amount of master nodes can be identified with 'fsstat'.",
                            type=int)

    def add_default_ubi_args(self, parser: argparse.ArgumentParser, ubils: bool = False) -> None:
        """
        Adds default arguments to Parsers for commands that work on the UBI layer
        :param parser:
        :param ubils: Special treatment for ubils (TODO: maybe solve this another way)
        :return:
        """
        if ubils:
            group = parser.add_mutually_exclusive_group(required=True)
            group.add_argument("-o", "--offset",
                               help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.",
                               type=int)
            group.add_argument("-a", "--all", help="Lists all UBI instances.", default=False, action="store_true")
        else:
            parser.add_argument("-o", "--offset",
                                help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.",
                                type=int, required=True)

            group = parser.add_mutually_exclusive_group(required=True)
            group.add_argument("-n", "--volname", help="Name of the UBI volume.", type=str)
            group.add_argument("-i", "--volindex", help="Index of the UBI volume within the UBI instance.", type=int)

    def add_default_mtd_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Adds default arguments to a Parser that are commonly needed, such as defining the block- or pagesize.
        :param parser: Parser that will have common arguments added
        :return:
        """
        parser.add_argument("input", help="Path to input flash memory dump.")

        parser.add_argument("--oob", help="Out of Bounds size in Bytes. If specified, will automatically extract OOB.",
                            type=int)
        parser.add_argument("--pagesize",
                            help="Page size in Bytes. If not specified, will try to guess the size based on UBI headers.",
                            type=int)
        parser.add_argument("--blocksize",
                            help="Block size in Bytes. If not specified, will try to guess the block size based on UBI headers.",
                            type=int)
        parser.add_argument("--pebthreshold",
                            help="Gaps between multiple instances of UBI that fall within the threshold are assumed to belong to the same UBI instance.",
                            type=int,
                            default=3)
        parser.add_argument("--verbose", help="Outputs a lot more debug information", default=False,
                            action="store_true")

    def _initialize_mtd(self, args: argparse.Namespace) -> Image:
        """
        Convenience method for initalizing an instance of Image with default args
        :param path: Path to Flash dump
        :param args: default args that contains blocksiz etc.
        :return: An instance of Image or None if it fails
        """
        path = args.input
        with open(path, "rb") as f:
            data = f.read()

            oob_size = args.oob if args.oob is not None and args.oob > 0 else -1
            page_size = args.pagesize if args.pagesize is not None and args.pagesize > 0 else -1
            block_size = args.blocksize if args.blocksize is not None and args.blocksize > 0 else -1

            mtd = Image(data, block_size, page_size, oob_size)

            peb_threshold = args.pebthreshold
            if peb_threshold is not None:
                setattr(mtd, "peb_threshold", peb_threshold)

            return mtd

    def _initialize_ubi(self, image: Image, args: argparse.Namespace) -> UBI:
        """
        Initializes the UBI layer. Finds the specific UBI instance provided by the --offset parameter in args
        :param image: Previously initialized Image
        :param args:
        :return: Instance of UBI or None if it couldnt be found
        """
        peb_offset = args.offset

        for partition in image.partitions:
            if peb_offset == (partition.offset // image.block_size):
                ubi = UBI(partition)
                return ubi

        raise exception.UBIFTException("[-] Cannot find UBI Instance. Maybe the offset is incorrect?")

    def _initialize_ubi_volume(self, ubi: UBI, args: argparse.Namespace) -> UBIVolume:
        """
        Searches a specific UBI volume within an instance of UBI given by either name (--volname) or index (--volindex)
        :param ubi:
        :param args:
        :return:
        """
        volname = args.volname
        volindex = args.volindex

        # Search by index
        if volindex is not None and volindex >= 0 and volindex < len(ubi.volumes):
            return ubi.volumes[volindex]

        # Search by name
        if volname is not None and len(volname) > 0:
            for ubivol in ubi.volumes:
                if ubivol.name == volname:
                    return ubivol

        raise exception.UBIFTException(
            "[-] Cannot find specified UBI Volume. Either the volname or volindex is invalid.")

    def _initialize_ubi_instances(self, image: Image, do_partitioning: bool = False) -> List[UBI]:
        """
        Convenience method for initalizing all UBI instances in an Image (requires the Partitions that include an UBI instance to be named "UBI")
        :param image: Image
        :param do_partitioning: If True, will partition the Image using an UBIPartitioner
        :return: List of initialized UBI instances
        """
        ubi_instances = []

        if do_partitioning:
            image.partitions = UBIPartitioner().partition(image, fill_partitions=False)

        for partition in image.partitions:
            if partition.name == "UBI":
                ubi = UBI(partition)
                ubi_instances.append(ubi)
        return ubi_instances

    @classmethod
    def verbose(cls, args: argparse.Namespace) -> None:
        """
        Checks if --verbose is set True, if not, will disable logging.
        :param args:
        :return:
        """
        if hasattr(args, "verbose") and args.verbose is False:
            logging.disable(logging.INFO)
            logging.disable(logging.WARN)

    def ubift_info(self, args) -> None:
        """
        Sub-command of ubift_recover
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        inode_info = args.inode_info

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol)

        scanned_inodes = {}
        scanned_dents = {}
        scanned_data_nodes = {}
        ubifs._scan_lebs(visitor._all_collector_visitor, inodes=scanned_inodes, dents=scanned_dents,
                         datanodes=scanned_data_nodes)

        renderer.render_recoverability_info(mtd, ubifs, scanned_inodes, scanned_dents, scanned_data_nodes,
                                            inode_info=inode_info)

    def ubift_recover(self, args) -> None:
        """
        Recovers all files of all found UBIFS instances.
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        output_dir = args.output
        deleted = args.deleted

        if output_dir is None or not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            rootlog.error(f"[-] Folder {output_dir} not specified or does not exist.")
            return
        else:
            rootlog.info(f"[!] Extracting all files to {output_dir}")

        image = self._initialize_mtd(args)
        ubi_instances = self._initialize_ubi_instances(image, True)

        for i, ubi in enumerate(ubi_instances):
            ubi_dir = os.path.join(output_dir, f"ubi_{i}")
            if not os.path.exists(ubi_dir):
                os.mkdir(ubi_dir)
                rootlog.info(f"[+] Creating directory {ubi_dir}")

            for j, ubi_vol in enumerate(ubi.volumes):
                # Create dir for UBI volume, e.g., ubi_0_1_data
                ubi_vol_name = ubi_vol.name if len(ubi_vol.name) <= 10 else ubi_vol.name[:10]
                ubi_vol_dir = os.path.join(ubi_dir, f"ubi_{i}_{j}_{ubi_vol_name}")
                if not os.path.exists(ubi_vol_dir):
                    os.mkdir(ubi_vol_dir)
                    rootlog.info(f"[+] Creating directory {ubi_vol_dir}")

                ubifs = UBIFS(ubi_vol)
                if ubifs is None or (not ubifs._used_masternode and not ubifs.superblock):
                    # Output ubi volume as binary data
                    ubi_raw_data_path = "RAW_UBI_VOL_DATA.bin"
                    full_path = os.path.join(ubi_vol_dir, ubi_raw_data_path)
                    with open(full_path, "wb") as f:
                        f.write(ubi_vol.get_data())
                        rootlog.info(f"[+] Wrote raw UBI volume data to: {full_path}")
                    continue

                inodes = {}
                dents = {}
                data = {}
                if hasattr(ubifs, "_root_idx_node"): # TODO: Temporary fix if there are no master nodes
                    ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_data_collector_visitor, inodes=inodes,
                                    dents=dents, data=data)

                if deleted:
                    scanned_inodes = {}
                    scanned_dents = {}
                    scanned_data_nodes = {}
                    ubifs._scan_lebs(visitor._all_collector_visitor, inodes=scanned_inodes, dents=scanned_dents,
                                     datanodes=scanned_data_nodes)

                for dent_list in dents.values():
                    for dent in dent_list:
                        if UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_DIR:
                            full_dir = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                            rootlog.info(f"[+] Creating directory {full_dir}")
                            try:
                                os.makedirs(full_dir, exist_ok=True)
                            except:
                                sanitized_path = sanitize_filepath(full_dir)
                                rootlog.info(f"[!] Sanitizing filepath {full_dir} to {sanitized_path}")
                                os.makedirs(sanitized_path, exist_ok=True)
                            inode_num = dent.inum
                            if inode_num in inodes:
                                atime = inodes[inode_num].atime_sec + inodes[inode_num].atime_nsec / 1000000000.0
                                mtime = inodes[inode_num].mtime_sec + inodes[inode_num].mtime_nsec / 1000000000.0
                                try:
                                    os.utime(full_dir, (atime, mtime))
                                    os.chmod(full_dir, inodes[inode_num].mode)
                                except:
                                    pass # TODO: print verbose warning msg
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_REG:
                            inode_num = dent.inum
                            full_filepath = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                            os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
                            if inode_num not in inodes or inode_num not in data or len(data[inode_num]) == 0:
                                rootlog.warning(
                                    f"[-] Cannot create file because cannot find its inode ({inode_num not in inodes}) or it has no data nodes ({inode_num not in data}): {full_filepath}")
                                continue
                            write_to_file(inodes[inode_num], data[inode_num], full_filepath)
                            atime = inodes[inode_num].atime_sec + inodes[inode_num].atime_nsec / 1000000000.0
                            mtime = inodes[inode_num].mtime_sec + inodes[inode_num].mtime_nsec / 1000000000.0
                            try:
                                os.utime(full_filepath, (atime, mtime))
                                os.chmod(full_filepath, inode.mode)
                            except:
                                pass
                            rootlog.info(f"[+] Creating file {full_filepath}")
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_LNK:
                            rootlog.warning(f"[!] Encountered type LNK (will be skipped): {dent.formatted_name()}")
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_BLK:
                            rootlog.warning(f"[!] Encountered type BLK (will be skipped): {dent.formatted_name()}")
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_CHR:
                            rootlog.warning(f"[!] Encountered type CHR (will be skipped): {dent.formatted_name()}")
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_FIFO:
                            rootlog.warning(f"[!] Encountered type FIFO (will be skipped): {dent.formatted_name()}")
                        elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_SOCK:
                            rootlog.warning(f"[!] Encountered type SOCK (will be skipped): {dent.formatted_name()}")
                        else:
                            rootlog.warning(
                                f"[!] Encountered unknown type (will be skipped): {dent.formatted_name()}")

                if not deleted:
                    continue

                rootlog.info(f"[+] Recovering deleted files.")
                deleted_dir = os.path.join(ubi_vol_dir, "UBIFT_RECOVERED_FILES")
                if not os.path.exists(deleted_dir):
                    os.mkdir(deleted_dir)

                for inode_num, inode in scanned_inodes.items():
                    if inode_num in inodes:  # This file is in the file index, so ignore it here.
                        continue
                    # TODO: maybe restore full path instead of putting everything into the recovered-folder
                    # TODO: Skip if not a regular file
                    # full_filepath = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                    # os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
                    if inode_num not in scanned_data_nodes or len(scanned_data_nodes[inode_num]) == 0:
                        name = ""
                        if inode_num in scanned_dents and len(scanned_dents[inode_num]) > 0:
                            name = scanned_dents[inode_num][0].formatted_name()
                        rootlog.warning(
                            f"[-] Cannot recover deleted inode {inode_num} ({name}) because there are no more data nodes for it.")
                        continue

                    if inode_num in scanned_dents and len(scanned_dents[inode_num]) > 0:
                        full_filepath = os.path.join(deleted_dir, scanned_dents[inode_num][0].formatted_name())
                    else:
                        full_filepath = os.path.join(deleted_dir, f"RECOVERED_INODE_DATA_{inode_num}")

                    write_to_file(inode, scanned_data_nodes[inode_num], full_filepath)

                    atime = inode.atime_sec + inode.atime_nsec / 1000000000.0
                    mtime = inode.mtime_sec + inode.mtime_nsec / 1000000000.0
                    try:
                        os.utime(full_dir, (atime, mtime))
                        os.chmod(full_dir, inode.mode)
                    except:
                        pass

                    rootlog.info(f"[+] Recovering file {full_filepath} from inode {inode_num}.")

    def istat(self, args) -> None:
        """
        Displays information about a specific inode.
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        do_scan = args.scan
        inode_num = args.inode

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol)

        if inode_num <= 0:
            rootlog.error(f"[-] Invalid inode number {inode_num}.")
            return

        # Construct key and try to find it in B-Tree
        inode_node_key = UBIFS_KEY.create_key(inode_num, UBIFS_KEY_TYPES.UBIFS_INO_KEY, 0)
        if do_scan:
            # TODO: When scanning, multiple inodes can possibly be found (the original one and the deletion one with nlink=0)
            #   Therefore maybe it is necessary to utilize dict[int, list] approach for scan methods instead of mere lists
            dents = {}
            inodes = {}
            datanodes = {}
            ubifs._scan_lebs(visitor._all_collector_visitor, inodes=inodes, dents=dents,
                             datanodes=datanodes)
            if inode_num in inodes:
                node = inodes[inode_num]
            else:
                node = None
        else:
            node = ubifs._find(ubifs._root_idx_node, inode_node_key)

        if node == None or inode_node_key != UBIFS_KEY(bytes(node.key[:8])):
            rootlog.error(
                f"[-] Inode {inode_num} could not be found.")
        else:
            render_inode_node(ubifs, inode_num, node)

            xattrs = self._get_xattrs(ubifs, inode_num, do_scan=do_scan)
            if len(xattrs) > 0:
                ubiftlog.info(f"[+] Found {len(xattrs)} extended attributes for inode {inode_num}")
                sys.stdout.write(f"Extended Attributes:\n")
                for xent, xent_inode in xattrs:
                    xent_data = [f"{x:x}" for x in list(xent_inode.data)]
                    xent_data = "".join(xent_data)
                    try:
                        u = bytearray(xent_inode.data).hex()
                        b = codecs.decode(u, "hex")
                        result = b.decode("ascii", errors="ignore")
                    except:
                        result = ""
                    sys.stdout.write(f"{xent.formatted_name()} --> {xent_data} ({result})\n")

    def _get_xattrs(self, ubifs: UBIFS, inode_num: int, do_scan: bool) -> list[tuple[UBIFS_DENT_NODE, UBIFS_INO_NODE]]:
        """
        Fetches all extended attributes for a given inode.
        Right now this is done in a 'complicated' way by first fetching all UBIFS_DENT_NODE nodes with a key_type of UBIFS_XENT_KEY
        Then all inodes of those specific UBIFS_DENT_NODES are fetched
        :param ubifs:
        :param inode_num:
        :return: A dictionary of xent nodes (UBIFS_DENT_NODE with specific key) mapping to inodes representing the extended attributes
        """
        if do_scan:
            dents = {}
            xentries = {}
            ubifs._scan_lebs(visitor._dent_xent_scan_leb_visitor, dents=dents, xentries=xentries)
        else:
            inodes = {}
            dents = {}
            xentries = {}
            ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_xent_collector_visitor, inodes=inodes,
                            dents=dents, xentries=xentries)
        xents = []
        for k,v in xentries.items():
            for xent in v:
                host_inum = UBIFS_KEY.from_bytearray(xent.key).inode_num
                if host_inum == inode_num:
                    if do_scan:
                        xents.append((xent, inodes[xent.inum] if xent.inum in inodes else None))
                    else:
                        inode_node_xent_key = UBIFS_KEY.create_key(xent.inum, UBIFS_KEY_TYPES.UBIFS_INO_KEY, 0)
                        xent_inode = ubifs._find(ubifs._root_idx_node, inode_node_xent_key)
                        xents.append((xent, xent_inode))

        return xents

    def jls(self, args) -> None:
        """
        Lists all nodes within the journal
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol)

        renderer.render_journal(mtd, ubifs, ubifs.journal)


    def ils(self, args) -> None:
        """
        Lists all available inodes of an UBIFS instance (by default by traversing its B-Tree)
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        do_scan = args.scan
        deleted = args.deleted
        format = args.format

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol)

        dents = {}
        inodes = {}
        datanodes = {}
        if do_scan or deleted:
            ubifs._scan_lebs(visitor._all_collector_visitor, inodes=inodes, dents=dents,
                             datanodes=datanodes)
            render_inodes(mtd, ubifs, inodes, deleted=deleted, datanodes=datanodes, dents=dents, format=format)
        else:
            ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_collector_visitor, inodes=inodes,
                            dents=dents)
            render_inodes(mtd, ubifs, inodes, format=format)

    def icat(self, args) -> None:
        """
        Outputs the data of a specific inode by searching for all of its data nodes (UBIFS_DATA_NODE)
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        inode_num = args.inode
        do_scan = args.scan
        output = args.output if args.output is not None else sys.stdout

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol)

        data_nodes = []
        # For deleted content a scan has to be performed otherwise the data nodes cannot be found
        if do_scan:
            dents = {}
            inodes = {}
            datanodes = {}
            ubifs._scan_lebs(visitor._all_collector_visitor, inodes=inodes, dents=dents,
                             datanodes=datanodes)
            if inode_num in datanodes:
                data_nodes = datanodes[inode_num]
            render_data_nodes(ubifs, inode_num, data_nodes, output, inodes=inodes)
        else:
            # Find all data nodes for given inode number
            min_key = UBIFS_KEY.create_key(inode_num, UBIFS_KEY_TYPES.UBIFS_DATA_KEY, 0)
            max_key = UBIFS_KEY.create_key(inode_num, UBIFS_KEY_TYPES.UBIFS_DATA_KEY + 1, 0)
            data_nodes = ubifs._find_range(ubifs._root_idx_node, min_key, max_key)
            render_data_nodes(ubifs, inode_num, data_nodes, output)

        # ubiftlog.error(
        #     f"[-] UBI Volume {ubi_vol_name} could not be found. Use 'mtdls' and 'ubils' to determine available UBI instances and their volumes.")
        # output.close()
        # os.remove(output.name)

    def ffind(self, args) -> None:
        """
        Lists all directory entries for a given inode number. They can either be found by traversing the file-index
        or by scanning for ubifs_ch headers (with the --scan flag).
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        use_full_paths = args.path
        inode_number = args.inode
        do_scan = args.scan
        master_node_index = args.master

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol, masternode_index=master_node_index)

        # Traverse B-Tree and collect all dents (inodes dont matter here but are collected too)
        # TODO: Maybe traverse etc shouldnt be protected functions
        if do_scan:
            dents = {}
            ubifs._scan_lebs(visitor._dent_scan_leb_visitor, dents=dents)
            if inode_number not in dents:
                dents = {}
            else:
                dents = {inode_number: dents[inode_number]}
            render_dents(ubifs, dents, use_full_paths)
        else:
            # TODO: This can be done more efficiently with traverse_range for the dents
            inodes = {}
            dents = {}
            ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_collector_visitor, inodes=inodes,
                            dents=dents)
            if inode_number not in dents:
                dents = {}
            else:
                dents = {inode_number: dents[inode_number]}
            render_dents(ubifs, dents, use_full_paths)

    def fls(self, args) -> None:
        """
        Lists all files by analyzing UBIFS_DENT_NODES. They can either be found by traversing the file-index
        or by scanning for ubifs_ch headers and checking if they are of type UBIFS_DENT_NODE.
        :param args:
        :return:
        """
        CommandLine.verbose(args)
        use_full_paths = args.path
        do_scan = args.scan
        master_node_index = args.master
        deleted = args.deleted
        format = args.format
        output_xentries = args.xentries

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)
        ubifs = UBIFS(ubi_vol, masternode_index=master_node_index)

        # Traverse B-Tree and collect all dents (inodes dont matter here but are collected too)
        # TODO: Maybe traverse etc shouldnt be protected functions
        if do_scan or deleted:
            dents = {}
            xentries = {}
            ubifs._scan_lebs(visitor._dent_xent_scan_leb_visitor, dents=dents, xentries=xentries)
        else:
            inodes = {}
            dents = {}
            xentries = {}
            ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_xent_collector_visitor, inodes=inodes,
                            dents=dents, xentries=xentries)

        if output_xentries:
            render_xents(ubifs, xentries)
        else:
            render_dents(ubifs, dents, use_full_paths, deleted=deleted, print_related_dents=True, format=format)

    def ubicat(self, args) -> None:
        """
        Prints contents of a specific UBI Volume to stdout
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        include_headers = args.headers

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)

        try:
            sys.stdout.buffer.write(ubi_vol.get_data(include_headers=include_headers))
        except IOError as e:
            if e.errno == errno.EPIPE:
                pass

    def lebcat(self, args) -> None:
        """
        Prints contents of a specific LEB of a specific UBI Volume to stdout
        :param args:
        :return:
        """
        CommandLine.verbose(args)
        leb_num = args.lebnumber
        headers = args.headers

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)

        if leb_num not in ubi_vol.lebs:
            rootlog.error(
                f"[-] LEB {leb_num} does not exist in UBI Volume {ubi_vol.name}. It might not be mapped to a PEB, this can be validated with 'lebls'.")
            return
        else:
            try:
                if headers:
                    sys.stdout.buffer.write(ubi_vol.lebs[leb_num].peb)
                else:
                    sys.stdout.buffer.write(ubi_vol.lebs[leb_num].data)
            except IOError as e:
                if e.errno == errno.EPIPE:
                    pass
            return

    def lebls(self, args):
        CommandLine.verbose(args)

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)

        if ubi_vol is not None:
            render_lebs(ubi_vol)
        else:
            rootlog.error("[-] Offset or volume name could not be found.")

    def pebcat(self, args):
        CommandLine.verbose(args)
        block_num = args.index

        mtd = self._initialize_mtd(args)

        if block_num < 0 or block_num >= len(mtd.data) // mtd.block_size:
            rootlog.error(f"[-] Invalid physical Erase Block index. Available PEBs for this image are from to 0 to {len(mtd.data) // mtd.block_size - 1}")
        else:
            start = block_num * mtd.block_size
            end = ((block_num + 1) * mtd.block_size)
            try:
                sys.stdout.buffer.write(mtd.data[start:end])
            except IOError as e:
                if e.errno == errno.EPIPE:
                    pass

    def ubils(self, args):
        CommandLine.verbose(args)

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)

        if args.all:
            for partition in mtd.partitions:
                ubi = UBI(partition)
        else:
            self._initialize_ubi(mtd, args)

        render_ubi_instances(mtd)

    def fsstat(self, args: argparse.Namespace):
        CommandLine.verbose(args)

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=False)
        ubi = self._initialize_ubi(mtd, args)
        ubi_vol = self._initialize_ubi_volume(ubi, args)

        ubifs = UBIFS(ubi_vol)
        sys.stdout.write("Superblock node:\n")
        for field in ubifs.superblock.__fields__:
            sys.stdout.write(f"{field}: {getattr(ubifs.superblock, field)}\n")

        sys.stdout.write(f"\nMaster nodes in LEB1: {len(ubifs.masternodes[0])}, LEB2: {len(ubifs.masternodes[1])}\n")
        sys.stdout.write("\n(newest) Master node in LEB1:\n")
        for field in ubifs.masternodes[0][0].__fields__:
            sys.stdout.write(f"{field}: {getattr(ubifs.masternodes[0][0], field)}\n")

    def mtdls(self, args):
        CommandLine.verbose(args)

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=True)
        render_image(mtd)

    def mtdcat(self, args):
        CommandLine.verbose(args)
        num = args.index

        mtd = self._initialize_mtd(args)
        mtd.partitions = UBIPartitioner().partition(mtd, fill_partitions=True)

        if num < 0 or num >= len(mtd.partitions):
            rootlog.error("[-] Invalid Partition index. Use 'mtdls' to see available partitions.")
        else:
            try:
                sys.stdout.buffer.write(mtd.partitions[num].data)
            except IOError as e:
                if e.errno == errno.EPIPE:
                    pass
