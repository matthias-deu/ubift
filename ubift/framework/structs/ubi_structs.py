import cstruct as cstruct

from ubift.framework.structs.structs import MemCStructExt

VTBL_VOLUME_ID = 0x7fffefff

"""
64-byte header which stores the volume ID and the logical eraseblock (LEB) number to which PEB it belongs
"""
class UBI_VID_HDR(MemCStructExt):
    __byte_order__ = cstruct.BIG_ENDIAN
    __magic__ = "\x55\x42\x49\x21".encode("utf-8") # UBI!
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

class UBI_EC_HDR(MemCStructExt):
    __byte_order__ = cstruct.BIG_ENDIAN
    __magic__ = "\x55\x42\x49\x23".encode("utf-8") # UBI#
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
class UBI_VTBL_RECORD(MemCStructExt):
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

    def formatted_name(self) -> str:
        """
        Prints the name of the Volume by concatenating the hex values and decoding them
        @return:
        """
        formatted_name = [f"{x:x}" for x in list(self.name)]
        formatted_name = formatted_name[:self.name_len]
        formatted_name = "".join(formatted_name)
        return bytearray.fromhex(formatted_name).decode()
