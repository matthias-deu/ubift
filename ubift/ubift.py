import os
import cstruct
import logging

ubiftlog = logging.getLogger(__name__)

UBI_IMG_PATH = r"E:\VM Shared Folder\UBI\ubi.img"
UBI_VID_HDR_MAGIC = "\x55\x42\x49\x21"
UBI_EC_HDR_MAGIC = "\x55\x42\x49\x23"
VTBL_VOLUME_ID = 0x7fffefff

"""
64-byte header which stores the volume ID and the logical eraseblock (LEB) number to which PEB it belongs
"""
class VolumeIdentificationHeader(cstruct.MemCStruct):
    __byte_order__ = cstruct.BIG_ENDIAN
    __def__ = """
        struct ubi_vid_hdr {
            uint32  magic;
            uint8   version;
            uint8   vol_type;
            uint8   copy_flag;
            uint8   compat;
            uint32  vol_id;
            uint32  lnum;
            uint8   padding1[4];
            uint32  data_size;
            uint32  used_ebs;
            uint32  data_pad;
            uint32  data_crc;
            uint8   padding2[4];
            uint64  sqnum;
            uint8   padding3[12];
            uint32  hdr_crc;
        }
    """

class EraseCounterHeader(cstruct.MemCStruct):
    __byte_order__ = cstruct.BIG_ENDIAN
    __def__ = """
        struct ubi_ec_hdr {
            uint32  magic;
            uint8   version;
            uint8   padding1[3];
            uint64  ec;
            uint32  vid_hdr_offset;   /* where the VID header starts !!!!!!!!!!!! */
            uint32  data_offset; /* where the user data start !!!!!!!!!!!!!!! */
            uint32  image_seq;
            uint8   padding2[32];
            uint32  hdr_crc;
        }
    """


"""
The volume table is an on-flash data structure which contains information about each volume on this UBI device. The volume table is an array of volume table records.

Each record describes one UBI volume. The record index in the volume table array corresponds
to the volume ID it describes. I.e, UBI volume 0 is described by record 0 in the volume table,
and so on. The total number of records in the volume table is limited by the LEB size, and cannot be greater than 128.
This means that UBI devices cannot have more than 128 volumes.
"""
class VolumeTableRecord(cstruct.MemCStruct):
    __byte_order__ = cstruct.BIG_ENDIAN
    __def__ = """
        #define UBI_VOL_NAME_MAX 127
    
        struct ubi_vtbl_record {
            uint32   reserved_pebs;
            uint32   alignment;
            uint32   data_pad;
            uint8    vol_type;
            uint8    upd_marker;
            uint16   name_len;
            uint8    name[UBI_VOL_NAME_MAX+1];
            uint8    flags;
            uint8    padding[23];
            uint32   crc;
        }
    """

if __name__ == '__main__':
   with open(UBI_IMG_PATH, "rb") as f:
       content = f.read()
       next_hit = content.find(UBI_EC_HDR_MAGIC.encode("utf-8"), 0)
       hits = []
       while next_hit >= 0:
           hits.append(next_hit)
           next_hit = content.find(UBI_EC_HDR_MAGIC.encode("utf-8"), next_hit + 1)

       print(f"Found {len(hits)} ubi_ec_hdr headers.")
       print(f"{len(hits)} would accumulate to {len(hits) * 128} KiB -> image size {UBI_IMG_PATH} is {int(os.stat(UBI_IMG_PATH).st_size / 1024)} KiB")

       vtbl_read = False # The ubi-layout volume is redundantly available 2 times, but theres on no need to print it twice
       for hit in hits:
           ec_hdr = EraseCounterHeader()
           ec_hdr.unpack_from(content, hit)
           #print(ec_hdr.inspect())

           vid_hdr = VolumeIdentificationHeader()
           vid_hdr.unpack_from(content, hit+ec_hdr.vid_hdr_offset)
           #print(vid_hdr.inspect())
           #print(f"{hit / 1024 / 128} -> {vid_hdr.vol_id}")

           # Check if this volume is the ubi-volume containing info about all volumes
           if vid_hdr.vol_id == VTBL_VOLUME_ID and not vtbl_read:
               print("volume table entries names:")
               for i in range(128):
                   record = VolumeTableRecord()
                   record.unpack_from(content, hit+ec_hdr.data_offset + i * cstruct.sizeof(VolumeTableRecord))
                   #print(record)
                   if record.reserved_pebs > 0: # 0 reserved_pebs mean that the volume table entry is empty
                       name = [f"{x:x}" for x in list(record.name)]
                       name = name[:record.name_len]
                       test = "".join(name)
                       print("volume name: %s" % bytearray.fromhex(test).decode())

                       vtbl_read = True








