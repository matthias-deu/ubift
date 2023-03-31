import argparse
import errno
import logging
import sys

from ubift.cli.renderer import render_lebs, render_ubi_instances, render_image
from ubift.framework.mtd import Image
from ubift.framework.partitioner import UBIPartitioner
from ubift.framework.structs.ubifs_structs import UBIFS_SB_NODE
from ubift.framework.ubi import UBI

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

        # fsstat
        fsstat = subparsers.add_parser("fsstat", help="Outputs information regarding the file-system in a specific UBI volume.")
        fsstat.add_argument("input", help="Input flash memory dump.")
        fsstat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        fsstat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        fsstat.set_defaults(func=self.fsstat)

        # Adds default arguments such as --blocksize to all previously defined commands
        commands = [mtdls, mtdcat, pebcat, ubils, lebls, lebcat, fsstat]
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

    def lebcat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        leb_num = args.leb

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=False)

            for part in t.partitions:
                if ubi_offset == (part.offset // t.block_size):
                    ubi = UBI(part)
                    for ubi_vol in part.ubi_instance.volumes:
                        if ubi_vol.name == ubi_vol_name:
                            for leb in ubi_vol._blocks:
                                if leb.leb_num == leb_num:
                                    try:
                                        sys.stdout.buffer.write(leb.data)
                                    except IOError as e:
                                        if e.errno == errno.EPIPE:
                                            pass
                                    return


            rootlog.error("[-] Offset or volume name could not be found. It is also possible that the LEB is not available or not mapped.")

    def lebls(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=False)

            for part in t.partitions:
                if ubi_offset == (part.offset // t.block_size):
                    ubi = UBI(part)
                    for ubi_vol in part.ubi_instance.volumes:
                        if ubi_vol.name == ubi_vol_name:
                            render_lebs(ubi_vol)
                            return

            rootlog.error("[-] Offset or volume name could not be found.")


    def pebcat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        block_num = args.index

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            if block_num < 0 or block_num > len(t.data) // t.block_size:
                rootlog.error("[-] Invalid physical Erase Block index.")
            else:
                start = block_num * t.block_size
                end = ((block_num+1) * t.block_size)
                try:
                    sys.stdout.buffer.write(t.data[start:end])
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass

    def ubils(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=False)
            for partition in t.partitions:
                ubi = UBI(partition)

            render_ubi_instances(t)

    def fsstat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=False)

            for partition in t.partitions:
                ubi = UBI(partition)

            ubi_vol = t.partitions[0].ubi_instance.volumes[0] # linux
            sb_data = ubi_vol._blocks[0].data

            sb = UBIFS_SB_NODE(sb_data, 0)
            print(len(sb_data))
            print(sb)

    def mtdls(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        oob_size = args.oob if args.oob is not None and args.oob > 0 else -1
        page_size = args.pagesize if args.pagesize is not None and args.pagesize > 0 else -1
        block_size = args.blocksize if args.blocksize is not None and args.blocksize > 0 else -1

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, block_size, page_size, oob_size)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=True)

            render_image(t)

    def mtdcat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        num = args.index

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t, fill_partitions=True)

            if num < 0 or num >= len(t.partitions):
                rootlog.error("[-] Invalid Partition index.")
            else:
                try:
                    sys.stdout.buffer.write(t.partitions[num].data)
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass


if __name__=="__main__":
    CommandLine().start()