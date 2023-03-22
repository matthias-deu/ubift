import os
from typing import List

import cstruct
import struct
import logging

ubiftlog = logging.getLogger(__name__)

class UBI:
    def __init__(self, data: bytes, start: int, len: int):
        pass

    def parse_vtbl_headers(self):
        pass

class UBIVolume:
    def __init__(self):
        pass

class PEB:
    def __init__(self):
        pass

class LEB:
    def __init__(self):
        pass

# if __name__ == '_kjhkmain__':
#    with open(UBI_IMG_PATH, "rb") as f:
#
#        for i in range(10, 20):
#            print(1 << i)
#        exit()
#
#        print(UBI_EC_HDR_MAGIC.encode("utf-8"))
#        content = f.read()
#        next_hit = content.find(UBI_EC_HDR_MAGIC.encode("utf-8"), 0)
#        hits = []
#        while next_hit >= 0:
#            hits.append(next_hit)
#            next_hit = content.find(EraseCounterHeader.__magic__, next_hit + 1)
#            #next_hit = content.find(UBI_EC_HDR_MAGIC.encode("utf-8"), next_hit + 1)
#
#        print(f"Found {len(hits)} ubi_ec_hdr headers.")
#        print(f"{len(hits)} would accumulate to {len(hits) * 2048 * 64 / 1024} KiB -> image size {UBI_IMG_PATH} is {int(os.stat(UBI_IMG_PATH).st_size / 1024)} KiB")
#
#        vtbl_read = False # The ubi-layout volume is redundantly available 2 times, but theres on no need to print it twice
#        for i,hit in enumerate(hits):
#            ec_hdr = EraseCounterHeader()
#            #ec_hdr.unpack_from(content, hit)
#            ec_hdr.parse(content, hit)
#            #ec_hdr.unpack(content[hit:hit+ec_hdr.size])
#            #print(ec_hdr.inspect())
#
#            vid_hdr = VolumeIdentificationHeader()
#            #vid_hdr.unpack_from(content, hit+ec_hdr.vid_hdr_offset)
#            vid_hdr.unpack(content[hit+ec_hdr.vid_hdr_offset:hit+ec_hdr.vid_hdr_offset+vid_hdr.size])
#            #print(vid_hdr.inspect())
#            #print(f"{hit / 1024 / 128} -> {vid_hdr.vol_id}")
#
#            # Check if this volume is the ubi-volume containing info about all volumes
#            if vid_hdr.vol_id == VTBL_VOLUME_ID:
#                print("volume table entries names:")
#                for i in range(128):
#                    record = VolumeTableRecord()
#                    #record.unpack_from(content, hit+ec_hdr.data_offset + i * cstruct.sizeof(VolumeTableRecord))
#                    pos = hit+ec_hdr.data_offset + i * cstruct.sizeof(VolumeTableRecord)
#                    record.unpack(content[pos:pos+record.size])
#                    #print(record)
#                    if record.reserved_pebs > 0: # 0 reserved_pebs mean that the volume table entry is empty
#                        name = [f"{x:x}" for x in list(record.name)]
#                        name = name[:record.name_len]
#                        test = "".join(name)
#                        print("volume name: %s" % bytearray.fromhex(test).decode())
#
#                        vtbl_read = True








