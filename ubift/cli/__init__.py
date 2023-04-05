import argparse
import errno
import logging
import sys
from typing import Any, List

from ubift.cli.renderer import render_lebs, render_ubi_instances, render_image, render_dents
from ubift.framework.mtd import Image
from ubift.framework.partitioner import UBIPartitioner
from ubift.framework.structs.ubifs_structs import UBIFS_SB_NODE, UBIFS_INODE_TYPES
from ubift.framework.ubi import UBI
from ubift.framework.ubifs import UBIFS

rootlog = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)-8s %(name)-12s: %(message)s")
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
        mtdls = subparsers.add_parser("mtdls", help="Lists information about all available Partitions, including UBI instances.")
        mtdls.add_argument("input", help="Input flash memory dump.")
        mtdls.set_defaults(func=self.mtdls)

        # mtdcat
        mtdcat = subparsers.add_parser("mtdcat", help="Outputs the binary data of an MTD partition, given by its index.")
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

        # WiP
        # fsstat
        # fsstat = subparsers.add_parser("fsstat", help="Outputs information regarding the file-system in a specific UBI volume.")
        # fsstat.add_argument("input", help="Input flash memory dump.")
        # fsstat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        # fsstat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        # fsstat.set_defaults(func=self.fsstat)

        # fls
        fls = subparsers.add_parser("fls", help="Outputs information regarding file names in a specific UBI volume.")
        fls.add_argument("input", help="Input flash memory dump.")
        fls.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        fls.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        fls.add_argument("--path", "-p", help="If set, will output full paths for every file.", default=False, action="store_true")
        fls.add_argument("--scan", "-s", help="If set, will perform scanning for signatures instead of traversing the file-index.", default=False, action="store_true")
        fls.set_defaults(func=self.fls)

        # Adds default arguments such as --blocksize to all previously defined commands
        commands = [mtdls, mtdcat, pebcat, ubils, lebls, lebcat, fls]
        for command in commands:
            self.add_default_image_args(command)

        args = parser.parse_args()
        args.func(args)

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
        Checks if --verbose is set True, if yes, will enable logging.
        :param args:
        :return:
        """
        if hasattr(args, "verbose") and args.verbose is False:
            logging.disable(logging.INFO)
            logging.disable(logging.WARN)

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

        with open(input, "rb") as f:
            data = f.read()

            image = self._initialize_image(data, args)
            ubi_instances = self._initialize_ubi_instances(image, True)

            for ubi in ubi_instances:
                if ubi.peb_offset == ubi_offset and ubi.get_volume(ubi_vol_name) is not None:
                    vol = ubi.get_volume(ubi_vol_name)
                    ubifs = UBIFS(vol)

                    # Traverse B-Tree and collect all dents (inodes dont matter here but are collected too)
                    # TODO: Maybe traverse etc shouldnt be protected functions
                    if do_scan:
                        dents = []
                        ubifs._scan(ubifs._dent_scan_visitor, dents=dents)
                        render_dents(ubifs, dents, use_full_paths)
                    else:
                        inodes = {}
                        dents = {}
                        ubifs._traverse(ubifs._root_idx_node, ubifs._inode_dent_collector_visitor, inodes=inodes, dents=dents)
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
                rootlog.error("[-] Invalid Partition index.")
            else:
                try:
                    sys.stdout.buffer.write(image.partitions[num].data)
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass