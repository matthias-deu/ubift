import argparse
import errno
import logging
import os
import sys
from typing import Any, List

from ubift.cli.renderer import render_lebs, render_ubi_instances, render_image, render_dents, render_inode_node, \
    render_data_nodes, render_inode_list, write_to_file
from ubift.framework import visitor
from ubift.framework.mtd import Image
from ubift.framework.partitioner import UBIPartitioner
from ubift.framework.structs.ubifs_structs import UBIFS_KEY, UBIFS_KEY_TYPES, UBIFS_INODE_TYPES, UBIFS_MST_NODE, \
    UBIFS_CH
from ubift.framework.ubi import UBI
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
        mtdls = subparsers.add_parser("mtdls", help="Lists information about all available Partitions, including UBI instances. UBI instances have the description 'UBI'.")
        mtdls.add_argument("input", help="Input flash memory dump.")
        mtdls.set_defaults(func=self.mtdls)

        # mtdcat
        mtdcat = subparsers.add_parser("mtdcat", help="Outputs the binary data of an MTD partition, given by its index. Use 'mtdls' to see all indeces.")
        mtdcat.add_argument("input", help="Input flash memory dump.")
        mtdcat.add_argument("index", type=int)
        mtdcat.set_defaults(func=self.mtdcat)

        # pebcat
        pebcat = subparsers.add_parser("pebcat", help="Outputs a specific phyiscal erase block.")
        pebcat.add_argument("input", help="Input flash memory dump.")
        pebcat.add_argument("index", type=int)
        pebcat.set_defaults(func=self.pebcat)

        # ubils
        ubils = subparsers.add_parser("ubils", help="Lists all instances of UBI and their volumes.")
        ubils.add_argument("input", help="Input flash memory dump.")
        ubils.set_defaults(func=self.ubils)

        # lebls
        lebls = subparsers.add_parser("lebls", help="Lists all mapped LEBs of a specific UBI volume.")
        lebls.add_argument("input", help="Input flash memory dump.")
        lebls.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        lebls.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        lebls.set_defaults(func=self.lebls)

        # lebcat
        lebcat = subparsers.add_parser("lebcat", help="Outputs a specific mapped logical erase block of a specified UBI volume.")
        lebcat.add_argument("input", help="Input flash memory dump.")
        lebcat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        lebcat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        lebcat.add_argument("leb", help="Number of the logical erase block. Use 'lebls' to determine LEBs.", type=int)
        lebcat.set_defaults(func=self.lebcat)

        # fsstat
        fsstat = subparsers.add_parser("fsstat", help="Outputs information regarding the UBIFS file-system within a specific UBI volume.")
        fsstat.add_argument("input", help="Input flash memory dump.")
        fsstat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        fsstat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        fsstat.set_defaults(func=self.fsstat)

        # fls
        fls = subparsers.add_parser("fls", help="Outputs information regarding file names in an UBIFS instance within a specific UBI volume.")
        fls.add_argument("input", help="Input flash memory dump.")
        fls.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        fls.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        fls.add_argument("--path", "-p", help="If set, will output full paths for every file.", default=False, action="store_true")
        fls.add_argument("--scan", "-s", help="If set, will perform scanning for signatures instead of traversing the file-index.", default=False, action="store_true")
        fls.add_argument("--deleted", "-d",
                         help="Similar to scan. Will perform scanning for signatures instead of using the file index. Will only show deleted directory entries. This will take priority over --scan.",
                         default=False, action="store_true")
        fls.set_defaults(func=self.fls)

        # istat
        istat = subparsers.add_parser("istat", help="Displays information about a specific inode in an UBIFS instance.")
        istat.add_argument("input", help="Input flash memory dump.")
        istat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        istat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        istat.add_argument("--scan", "-s",
                         help="If set, will perform scanning for inodes instead of traversing the file-index. Thus allowing to use istat on inodes that are no longer part of the file index.",
                         default=False, action="store_true")
        istat.add_argument("inode", help="Inode number.", type=int)
        istat.set_defaults(func=self.istat)

        # icat
        icat = subparsers.add_parser("icat", help="Outputs the data of an inode.")
        icat.add_argument("input", help="Input flash memory dump.")
        icat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        icat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        icat.add_argument("inode", help="Inode number.", type=int)
        icat.add_argument("-o", "--output", help="If specified, will output data to given file.", type=argparse.FileType('w'))
        icat.add_argument("--scan", "-s",
                         help="If set, will perform scanning for signatures instead of traversing the file-index for data nodes. NOTE: This needs to be set if trying to restore deleted inodes.",
                         default=False, action="store_true")
        icat.set_defaults(func=self.icat)

        # ils
        ils = subparsers.add_parser("ils", help="Lists all inodes of a given UBIFS instance.")
        ils.add_argument("input", help="Input flash memory dump.")
        ils.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        ils.add_argument("vol_name", help="Name of the UBI volume that contains the UBIFS instance.", type=str)
        ils.add_argument("--scan", "-s",
                         help="If set, will perform scanning for signatures instead of traversing the file-index.",
                         default=False, action="store_true")
        ils.add_argument("--deleted", "-d",
                         help="Similar to scan. Will perform scanning for signatures instead of using the file index. Will only show deleted inodes. This will take priority over --scan.",
                         default=False, action="store_true")
        ils.set_defaults(func=self.ils)

        # ffind
        ffind = subparsers.add_parser("ffind", help="Outputs directory entries associated with a given inode number.")
        ffind.add_argument("input", help="Input flash memory dump.")
        ffind.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        ffind.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        ffind.add_argument("--path", "-p", help="If set, will output full paths for every file.", default=False, action="store_true")
        ffind.add_argument("inode", help="Inode number.", type=int)
        ffind.add_argument("--scan", "-s",
                         help="If set, will perform scanning for signatures instead of traversing the file-index for data nodes. NOTE: This needs to be set if trying to find directory entries for deleted inodes.",
                         default=False, action="store_true")
        ffind.set_defaults(func=self.ffind)

        # ubift_recover
        # This command is used by the Autopsy plugin
        ubift_recover = subparsers.add_parser("ubift_recover", help="Extracts all files found in UBIFS instances. Creates one directory for each UBI volume with UBIFS.")
        ubift_recover.add_argument("input", help="Input flash memory dump.")
        ubift_recover.add_argument("--deleted", "-d",
                         help="If this parameter is set, all inodes not present within the file index which are found by scanning the dump will be recovered if possible. For each UBIFS instance, the recovered files will be saved to an additional folder 'RECOVERED_FILES'.",
                         default=False, action="store_true")
        ubift_recover.add_argument("-o", "--output", help="Output directory where all files and directories will be dumped to.", type=str)
        ubift_recover.set_defaults(func=self.ubift_recover)

        # Adds default arguments such as --blocksize to all previously defined commands
        commands = [mtdls, mtdcat, pebcat, ubils, lebls, lebcat, fls, istat, icat, ils, fsstat, ffind, ubift_recover]
        for command in commands:
            self.add_default_image_args(command)

        file_system_layer_commands = [fls, ffind, istat, ils]
        for command in file_system_layer_commands:
            self.add_default_ubifs_args(command)

        args = parser.parse_args()
        args.func(args)

    def add_default_ubifs_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Adds default arguments to Parsers for commands that work on the file system (UBIFS) layer
        :param ubifs_parser:
        :return:
        """
        parser.add_argument("--master", help="Defines the index of which master node will be used. Amount of master nodes can be identified with 'fsstat'.",
                            type=int)

    def add_default_image_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Adds default arguments to a Parser that are commonly needed, such as defining the block- or pagesize.
        :param parser: Parser that will have common arguments added
        :return:
        """
        parser.add_argument("--oob", help="Out of Bounds size in Bytes. If specified, will automatically extract OOB.",
                            type=int)
        parser.add_argument("--pagesize", help="Page size in Bytes. If not specified, will try to guess the size based on UBI headers.", type=int)
        parser.add_argument("--blocksize", help="Block size in Bytes. If not specified, will try to guess the block size based on UBI headers.", type=int)
        parser.add_argument("--verbose", help="Outputs a lot more debug information", default=False, action="store_true")

    def _initialize_image(self, data: Any, args: argparse.Namespace) -> Image:
        """
        Convenience method for initalizing an instance of Image with default args
        :param data: Flash dump
        :param args: default args that contains blocksiz etc.
        :return: An instance of Image or None if it fails
        """
        oob_size = args.oob if args.oob is not None and args.oob > 0 else -1
        page_size = args.pagesize if args.pagesize is not None and args.pagesize > 0 else -1
        block_size = args.blocksize if args.blocksize is not None and args.blocksize > 0 else -1

        return Image(data, block_size, page_size, oob_size)

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

    def ubift_recover(self, args) -> None:
        """
        Recovers all files of all found UBIFS instances.
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        output_dir = args.output
        deleted = args.deleted

        if output_dir is None or not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            rootlog.error(f"[-] Folder {output_dir} not specified or does not exist.")
            return
        else:
            rootlog.info(f"[!] Extracting all files to {output_dir}")

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for i,ubi in enumerate(ubi_instances):
                ubi_dir = os.path.join(output_dir, f"ubi_{i}")
                if not os.path.exists(ubi_dir):
                    os.mkdir(ubi_dir)
                    rootlog.info(f"[+] Creating directory {ubi_dir}")

                for j, ubi_vol in enumerate(ubi.volumes):

                    ubifs = UBIFS(ubi_vol)
                    if ubifs is None:
                        continue

                    ubi_vol_name = ubi_vol.name if len(ubi_vol.name) <= 10 else ubi_vol.name[:10]
                    ubi_vol_dir = os.path.join(ubi_dir, f"ubi_{i}_{j}_{ubi_vol_name}")
                    if not os.path.exists(ubi_vol_dir):
                        os.mkdir(ubi_vol_dir)
                        rootlog.info(f"[+] Creating directory {ubi_vol_dir}")

                    inodes = {}
                    dents = {}
                    data = {}
                    ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_data_collector_visitor, inodes=inodes,
                                    dents=dents, data=data)

                    if deleted:
                        scanned_inodes = {}
                        scanned_dents = {}
                        scanned_data_nodes = {}
                        ubifs._scan_lebs(visitor._all_collector_visitor, inodes=scanned_inodes, dents=scanned_dents, datanodes=scanned_data_nodes)

                    for dent_list in dents.values():
                        for dent in dent_list:
                            if UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_DIR:
                                full_dir = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                                rootlog.info(f"[+] Creating directory {full_dir}")
                                os.makedirs(full_dir, exist_ok=True)
                            elif UBIFS_INODE_TYPES(dent.type) == UBIFS_INODE_TYPES.UBIFS_ITYPE_REG:
                                inode_num = dent.inum
                                full_filepath = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                                os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
                                if inode_num not in inodes or inode_num not in data or len(data[inode_num]) == 0:
                                    rootlog.warning(f"[-] Cannot create file because cannot find its inode ({inode_num not in inodes}) or it has no data nodes ({inode_num not in data}): {full_filepath}")
                                    continue
                                write_to_file(inodes[inode_num], data[inode_num], full_filepath)
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
                                rootlog.warning(f"[!] Encountered unknown type (will be skipped): {dent.formatted_name()}")

                    if not deleted:
                        return

                    deleted_dir = os.path.join(ubi_vol_dir, "UBIFT_RECOVERED_FILES")
                    if not os.path.exists(deleted_dir):
                        os.mkdir(deleted_dir)

                    for inode_num, inode in scanned_inodes.items():
                        if inode_num in inodes: # This file is in the file index, so ignore it here.
                            continue
                        # TODO: maybe restore full path instead of putting everything into the recovered-folder
                        #full_filepath = os.path.join(ubi_vol_dir, ubifs._unroll_path(dent, dents))
                        #os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
                        if inode_num not in scanned_data_nodes or len(scanned_data_nodes[inode_num]) == 0:
                            name = ""
                            if inode_num in scanned_dents and len(scanned_dents[inode_num]) > 0:
                                name = scanned_dents[inode_num][0].formatted_name()
                            rootlog.warning(f"[-] Cannot recover deleted inode {inode_num} ({name}) because there are no more data nodes for it.")
                            continue

                        if inode_num in scanned_dents and len(scanned_dents[inode_num]) > 0:
                            full_filepath = os.path.join(deleted_dir, scanned_dents[inode_num][0].formatted_name())
                        else:
                            full_filepath = os.path.join(deleted_dir, f"RECOVERED_INODE_DATA_{inode_num}")

                        write_to_file(inode, scanned_data_nodes[inode_num], full_filepath)
                        rootlog.info(f"[+] Recovering file {full_filepath} from inode {inode_num}.")



    def istat(self, args) -> None:
        """
        Displays information about a specific inode.
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        do_scan = args.scan
        inode_num = args.inode

        if inode_num <= 0:
            rootlog.error(f"[-] Invalid inode number {inode_num}.")
            return

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol)

                    # Construct key and try to find it in B-Tree
                    inode_node_key = UBIFS_KEY.create_key(inode_num, UBIFS_KEY_TYPES.UBIFS_INO_KEY, 0)
                    if do_scan:
                        # TODO: When scanning, multiple inodes can possibly be found (the original one and the deletion one with nlink=0)
                        #   Therefore maybe it is necessary to utilize dict[int, list] approach for scan methods instead of mere lists
                        dents = {}
                        inodes = {}
                        datanodes = {}
                        ubifs._scan_lebs(visitor._all_collector_visitor, inodes=inodes, dents=dents, datanodes=datanodes)
                        if inode_num in inodes:
                            node = inodes[inode_num]
                    else:
                        node = ubifs._find(ubifs._root_idx_node, inode_node_key)

                    if node == None or inode_node_key != UBIFS_KEY(bytes(node.key[:8])):
                        rootlog.error(f"[-] Inode {inode_num} could not be found in UBIFS of UBI Volume {ubi_vol_name}.")
                        return
                    else:
                        render_inode_node(ubifs, inode_num, node)
                        return

            rootlog.error(f"[-] Inode {inode_num} could not be found in UBIFS of UBI Volume {ubi_vol_name}.")

    def ils(self, args) -> None:
        """
        Lists all available inodes of an UBIFS instance (by default by traversing its B-Tree)
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        do_scan = args.scan
        deleted = args.deleted

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol)

                    dents = {}
                    inodes = {}
                    datanodes = {}
                    if do_scan or deleted:
                        ubifs._scan_lebs(visitor._all_collector_visitor, inodes=inodes, dents=dents, datanodes=datanodes)
                        render_inode_list(image, ubifs, inodes, deleted=deleted, datanodes=datanodes, dents=dents)
                    else:
                        ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_collector_visitor, inodes=inodes,
                                        dents=dents)
                        render_inode_list(image, ubifs, inodes)



                    return

            ubiftlog.error(
                f"[-] UBI Volume {ubi_vol_name} could not be found. Use 'mtdls' and 'ubils' to determine available UBI instances and their volumes.")

    def icat(self, args) -> None:
        """
        Outputs the data of a specific inode by searching for all of its data nodes (UBIFS_DATA_NODE)
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        inode_num = args.inode
        do_scan = args.scan
        output = args.output if args.output is not None else sys.stdout

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol)

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

                    return

            ubiftlog.error(f"[-] UBI Volume {ubi_vol_name} could not be found. Use 'mtdls' and 'ubils' to determine available UBI instances and their volumes.")
            output.close()
            os.remove(output.name)

    def ffind(self, args) -> None:
        """
        Lists all directory entries for a given inode number. They can either be found by traversing the file-index
        or by scanning for ubifs_ch headers (with the --scan flag).
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        use_full_paths = args.path
        inode_number = args.inode
        do_scan = args.scan
        master_node_index = args.master

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol, masternode_index=master_node_index)

                    # Traverse B-Tree and collect all dents (inodes dont matter here but are collected too)
                    # TODO: Maybe traverse etc shouldnt be protected functions
                    if do_scan:
                        dents = {}
                        ubifs._scan_lebs(visitor._dent_scan_leb_visitor, dents=dents)
                        if inode_number not in dents:
                            dents = {}
                        else:
                            dents = { inode_number: dents[inode_number] }
                        render_dents(ubifs, dents, use_full_paths)
                    else:
                        # TODO: This can be done more efficiently with traverse_range for the dents
                        inodes = {}
                        dents = {}
                        ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_collector_visitor, inodes=inodes, dents=dents)
                        if inode_number not in dents:
                            dents = {}
                        else:
                            dents = { inode_number: dents[inode_number] }
                        render_dents(ubifs, dents, use_full_paths)

                    return

            rootlog.error(f"[-] UBI Volume {ubi_vol_name} could not be found.")

    def fls(self, args) -> None:
        """
        Lists all files by analyzing UBIFS_DENT_NODES. They can either be found by traversing the file-index
        or by scanning for ubifs_ch headers and checking if they are of type UBIFS_DENT_NODE.
        Example: /ubift.py fls "/path/to/dump" 445 linux
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        use_full_paths = args.path
        do_scan = args.scan
        master_node_index = args.master
        deleted = args.deleted

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol, masternode_index=master_node_index)

                    # Traverse B-Tree and collect all dents (inodes dont matter here but are collected too)
                    # TODO: Maybe traverse etc shouldnt be protected functions
                    if do_scan or deleted:
                        dents = {}
                        ubifs._scan_lebs(visitor._dent_scan_leb_visitor, dents=dents)
                        render_dents(ubifs, dents, use_full_paths, deleted=deleted)
                    else:
                        inodes = {}
                        dents = {}
                        ubifs._traverse(ubifs._root_idx_node, visitor._inode_dent_collector_visitor, inodes=inodes, dents=dents)
                        render_dents(ubifs, dents, use_full_paths)

                    return

            rootlog.error(f"[-] UBI Volume {ubi_vol_name} could not be found.")

    def lebcat(self, args) -> None:
        """
        Prints the data of a specific LEB of a specific UBI Volume to stdout
        Example: ./ubift.py lebcat "/path/to/dump" 445 linux 463
        (Outputs LEB 463 of UBI Volume 'linux' whose UBI Instance starts at PEB 445)
        :param args:
        :return:
        """
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        leb_num = args.leb

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            image.partitions = UBIPartitioner().partition(image, fill_partitions=False)

            for part in image.partitions:
                if ubi_offset == (part.offset // image.block_size):
                    ubi = UBI(part)
                    for ubi_vol in part.ubi_instance.volumes:
                        if ubi_vol.name == ubi_vol_name:
                            if leb_num not in ubi_vol.lebs:
                                rootlog.error(f"[-] LEB {leb_num} does not exist in UBI Volume {ubi_vol.name}. It might not be mapped to a PEB.")
                                return
                            else:
                                try:
                                    sys.stdout.buffer.write(ubi_vol.lebs[leb_num].data)
                                except IOError as e:
                                    if e.errno == errno.EPIPE:
                                        pass
                                return

            rootlog.error(f"[-] UBI Volume {ubi_vol_name} could not be found.")

    def lebls(self, args):
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            image.partitions = UBIPartitioner().partition(image, fill_partitions=False)

            for part in image.partitions:
                if ubi_offset == (part.offset // image.block_size):
                    ubi = UBI(part)
                    for ubi_vol in part.ubi_instance.volumes:
                        if ubi_vol.name == ubi_vol_name:
                            render_lebs(ubi_vol)
                            return

            rootlog.error("[-] Offset or volume name could not be found.")


    def pebcat(self, args):
        CommandLine.verbose(args)

        input = args.input
        block_num = args.index

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            if block_num < 0 or block_num > len(image.data) // image.block_size:
                rootlog.error("[-] Invalid physical Erase Block index.")
            else:
                start = block_num * image.block_size
                end = ((block_num+1) * image.block_size)
                try:
                    sys.stdout.buffer.write(image.data[start:end])
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass

    def ubils(self, args):
        CommandLine.verbose(args)

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            image.partitions = UBIPartitioner().partition(image, fill_partitions=False)
            for partition in image.partitions:
                ubi = UBI(partition)

            render_ubi_instances(image)

    def fsstat(self, args: argparse.Namespace):
        CommandLine.verbose(args)

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            image.partitions = UBIPartitioner().partition(image, fill_partitions=False)

            for part in image.partitions:
                if ubi_offset == (part.offset // image.block_size):
                    ubi = UBI(part)
                    for ubi_vol in part.ubi_instance.volumes:
                        if ubi_vol.name == ubi_vol_name:
                            ubifs = UBIFS(ubi_vol)

                            sys.stdout.write("Superblock node:\n")
                            for field in ubifs.superblock.__fields__:
                                sys.stdout.write(f"{field}: {getattr(ubifs.superblock, field)}\n")

                            sys.stdout.write(f"\nMaster nodes in LEB1: {len(ubifs.masternodes[0])}, LEB2: {len(ubifs.masternodes[1])}\n")
                            sys.stdout.write("\n(newest) Master node in LEB1:\n")
                            for field in ubifs.masternodes[0][0].__fields__:
                                sys.stdout.write(f"{field}: {getattr(ubifs.masternodes[0][0], field)}\n")

                            return

    def mtdls(self, args):
        CommandLine.verbose(args)

        input = args.input

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)

            image.partitions = UBIPartitioner().partition(image, fill_partitions=True)

            render_image(image)

    def mtdcat(self, args):
        CommandLine.verbose(args)

        input = args.input
        num = args.index

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            image.partitions = UBIPartitioner().partition(image, fill_partitions=True)

            if num < 0 or num >= len(image.partitions):
                rootlog.error("[-] Invalid Partition index. Use 'mtdls' to see available partitions.")
            else:
                try:
                    sys.stdout.buffer.write(image.partitions[num].data)
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass