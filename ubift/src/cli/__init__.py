import argparse
import errno
import logging
import sys

from ubift.src.cli.renderer import render_image, render_ubi_instances, render_lebs
from ubift.src.framework.base.partitioner import UBIPartitioner
from ubift.src.framework.disk_image_layer.mtd import Image

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
        mtdls.add_argument("input")
        mtdls.set_defaults(func=self.mtdls)

        # mtdcat
        mtdcat = subparsers.add_parser("mtdcat", help="Outputs the binary data of an MTD partition, given by its index.")
        mtdcat.add_argument("input")
        mtdcat.add_argument("index", type=int)
        mtdcat.set_defaults(func=self.mtdcat)

        # pebcat
        pebcat = subparsers.add_parser("pebcat", help="Outputs a specific phyiscal erase block.")
        pebcat.add_argument("input")
        pebcat.add_argument("index", type=int)
        pebcat.set_defaults(func=self.pebcat)

        # ubils
        ubils = subparsers.add_parser("ubils", help="Lists all instances of UBI and their volumes.")
        ubils.add_argument("input")
        ubils.set_defaults(func=self.ubils)

        # lebls
        lebls = subparsers.add_parser("lebls", help="Lists all mapped LEBs of a specific UBI volume.")
        lebls.add_argument("input")
        lebls.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        lebls.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        lebls.set_defaults(func=self.lebls)

        lebcat = subparsers.add_parser("lebcat", help="Outputs a specific mapped logical erase block of a specified UBI volume.")
        lebcat.add_argument("input")
        lebcat.add_argument("offset", help="Offset in PEBs to where the UBI instance starts. Use 'mtdls' to determine offset.", type=int)
        lebcat.add_argument("vol_name", help="Name of the UBI volume.", type=str)
        lebcat.add_argument("leb", help="Number of the logical erase block. Use 'lebls' to determine LEBs.", type=int)
        lebcat.set_defaults(func=self.lebcat)

        args = parser.parse_args()
        args.func(args)

    def lebcat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        ubi_offset = args.offset
        ubi_vol_name = args.vol_name
        leb_num = args.leb

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t)

            for part in t.partitions:
                if ubi_offset == (part.offset // t.block_size):
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
            t.partitions = UBIPartitioner().partition(t)

            for part in t.partitions:
                if ubi_offset == (part.offset // t.block_size):
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
            t.partitions = UBIPartitioner().partition(t)

            render_ubi_instances(t)


    def mtdls(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t)

            render_image(t)

    def mtdcat(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        num = args.index

        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t)
            all_parts  = t.get_full_partitions()

            if num < 0 or num >= len(all_parts):
                rootlog.error("[-] Invalid Partition index.")
            else:
                try:
                    sys.stdout.buffer.write(all_parts[num].data)
                except IOError as e:
                    if e.errno == errno.EPIPE:
                        pass


if __name__=="__main__":
    CommandLine().start()