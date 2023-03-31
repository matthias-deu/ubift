import cstruct as cstruct

from ubift.framework.structs.structs import MemCStructExt, COMMON_TYPEDEFS

VTBL_VOLUME_ID = 0x7fffefff

"""
64-byte header which stores the volume ID and the logical eraseblock (LEB) number to which PEB it belongs
"""
class UBI_VID_HDR(MemCStructExt):
    __byte_order__ = cstruct.BIG_ENDIAN
    __magic__ = "\x55\x42\x49\x21".encode("utf-8") # UBI!
    __def__ = COMMON_TYPEDEFS + """
        struct ubi_vid_hdr {
            __be32  magic;
            __u8    version;
            __u8    vol_type;
            __u8    copy_flag;
            __u8    compat;
            __be32  vol_id;
            __be32  lnum;
            __u8    padding1[4];
            __be32  data_size;
            __be32  used_ebs;
            __be32  data_pad;
            __be32  data_crc;
            __u8    padding2[4];
            __be64  sqnum;
            __u8    padding3[12];
            __be32  hdr_crc;
        };
    """

class UBI_EC_HDR(MemCStructExt):
    __byte_order__ = cstruct.BIG_ENDIAN
    __magic__ = "\x55\x42\x49\x23".encode("utf-8") # UBI#
    __def__ = COMMON_TYPEDEFS + """
        struct ubi_ec_hdr {
            __be32  magic;
            __u8    version;
            __u8    padding1[3];
            __be64  ec;
            __be32  vid_hdr_offset;
            __be32  data_offset;
            __be32  image_seq;
            __u8    padding2[32];
            __be32  hdr_crc;
        };
    """


"""
The volume table is an on-flash data structure which contains information about each volume on this UBI device. The volume table is an array of volume table records.

Each record describes one UBI volume. The record index in the volume table array corresponds
to the volume ID it describes. I.e, UBI volume 0 is described by record 0 in the volume table,
and so on. The total number of records in the volume table is limited by the LEB size, and cannot be greater than 128.
This means that UBI devices cannot have more than 128 volumes.
"""
class UBI_VTBL_RECORD(MemCStructExt):
    __byte_order__ = cstruct.BIG_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        #define UBI_VOL_NAME_MAX 127

        struct ubi_vtbl_record {
            __be32  reserved_pebs;
            __be32  alignment;
            __be32  data_pad;
            __u8    vol_type;
            __u8    upd_marker;
            __be16  name_len;
            __u8    name[UBI_VOL_NAME_MAX+1];
            __u8    flags;
            __u8    padding[23];
            __be32  crc;
        };
    """

    def formatted_name(self) -> str:
        """
        Prints the name of the Volume by concatenating the hex values and decoding them
        @return:
        """
        formatted_name = [f"{x:x}" for x in list(self.name)]
        formatted_name = formatted_name[:self.name_len]
        formatted_name = "".join(formatted_name)
        return bytearray.fromhex(formatted_name).decode()
