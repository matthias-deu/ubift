from cstruct import BIG_ENDIAN, LITTLE_ENDIAN

from ubift.framework.structs.structs import MemCStructExt


class UBIFS_CH(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __magic__ = "\x06\x10\x18\x31".encode("utf-8")  # 0x06101831
    __def__ = """
        struct {
            uint32 magic;
            uint32 crc;
            uint64 sqnum;
            uint32 len;
            uint8 node_type;
            uint8 group_type;
            uint8 padding[2];
        }
    """

class UBIFS_SB_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __magic__ = "\x06\x10\x18\x31".encode("utf-8") # 0x06101831
    __def__ = """
        #define UBIFS_MAX_HMAC_LEN 64
        #define UBIFS_MAX_HASH_LEN 64
    
        struct ubifs_sb_node {
            struct UBIFS_CH ch;
            uint8 padding[2];
            uint8 key_hash;
            uint8 key_fmt;
            uint32 flags;
            uint32 min_io_size;
            uint32 leb_size;
            uint32 leb_cnt;
            uint32 max_leb_cnt;
            uint64 max_bud_bytes;
            uint32 log_lebs;
            uint32 lpt_lebs;
            uint32 orph_lebs;
            uint32 jhead_cnt;
            uint32 fanout;
            uint32 lsave_cnt;
            uint32 fmt_version;
            uint16 default_compr;
            uint8 padding1[2];
            uint32 rp_uid;
            uint32 rp_gid;
            uint64 rp_size;
            uint32 time_gran;
            uint8 uuid[16];
            uint32 ro_compat_version;
            uint8 hmac[UBIFS_MAX_HMAC_LEN];
            uint8 hmac_wkm[UBIFS_MAX_HMAC_LEN];
            uint16 hash_algo;
            uint8 hash_mst[UBIFS_MAX_HASH_LEN];
            uint8 padding2[3774];
        }
    """