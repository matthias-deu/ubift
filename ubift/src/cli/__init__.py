import argparse
import errno
import logging
import sys

from ubift.src.cli.renderer import render_image
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

        # mmls
        mmls = subparsers.add_parser("mmls", help="Lists information about all available Partitions, including UBI instances.")
        mmls.add_argument("input")
        mmls.set_defaults(func=self.mmls)

        # mmcat
        mmcat = subparsers.add_parser("mmcat", help="Outputs the binary data of an MTD partition, given by its index.")
        mmcat.add_argument("input")
        mmcat.add_argument("index", type=int)
        mmcat.set_defaults(func=self.mmcat)

        # blkcat
        blkcat = subparsers.add_parser("blkcat", help="Outputs a specific phyiscal erase block.")
        blkcat.add_argument("input")
        blkcat.add_argument("index", type=int)
        blkcat.set_defaults(func=self.blkcat)

        args = parser.parse_args()
        args.func(args)

    def blkcat(self, args):
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


    def mmls(self, args):
        logging.disable(logging.INFO)  # TODO: Remove this and add a -verbose parameter to enable logging if needed

        input = args.input
        with open(input, "rb") as f:
            data = f.read()

            t = Image(data, -1, -1, -1)
            t.partitions = UBIPartitioner().partition(t)

            render_image(t)

    def mmcat(self, args):
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