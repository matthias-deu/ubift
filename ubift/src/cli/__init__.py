import argparse
import logging
from collections import Counter

from src.framework.disk_image_layer.mtd import Image
from src.framework.volume_layer.ubi import find_signature
from src.framework.volume_layer.ubi_structs import UBI_EC_HDR, UBI_VID_HDR

rootlog = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)-8s %(name)-12s: %(message)s")
console.setFormatter(formatter)

class CommandLine:

    def __init__(self):
        self.initialize_logger()

    @classmethod
    def initialize_logger(cls):
        rootlog.setLevel(1)
        rootlog.addHandler(console)

    def run(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", help="Commands to run", required=True)

        # blk
        # blk = subparsers.add_parser("blkls", help="Lists information about all available physical erase blocks.")
        # blk.add_argument("-i", "--input")
        #
        # blk = subparsers.add_parser("blkcat", help="Outputs a specific physical erase block.")
        # blk.add_argument("-i", "--input")
        #
        # blk = subparsers.add_parser("blkstat", help="Outputs information about a specific physical erase block")
        # blk.add_argument("-i", "--input")

        # mm
        mm = subparsers.add_parser("mmls", help="Lists information about all available UBI volumes.")
        mm.add_argument("input")
        mm.set_defaults(func=self.mmls)


        # mm = subparsers.add_parser("mmcat", help="Outputs a specific UBI volume.")
        # mm.add_argument("-i", "--input")
        #
        # mm = subparsers.add_parser("mmstat", help="Outputs information about a specific UBI volume")
        # mm.add_argument("-i", "--input")

        args = parser.parse_args()
        args.func(args)

    def mmls(self, args):
        input = args.input
        with open(input, "rb") as f:
            data = f.read()
            #ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
            #print(ec_hdr_offset)
            t = Image(data, -1, -1, 64)
            # hits = find_signature(data, UBI_EC_HDR.__magic__)
            #
            # for hit in hits:
            #     ec = UBI_EC_HDR()
            #     ec.parse(data, hit)
            #     #print(ec.data_offset)
            #     print(ec.vid_hdr_offset)
            #
            #     vid = UBI_VID_HDR()
            #     vid.parse(data, hit+ec.vid_hdr_offset)

if __name__=="__main__":
    CommandLine().start()