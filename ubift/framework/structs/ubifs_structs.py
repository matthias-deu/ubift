from typing import Dict, Any, List

from cstruct import LITTLE_ENDIAN, CEnum

from ubift.framework.structs.structs import MemCStructExt, COMMON_TYPEDEFS


class UBIFS_NODE_TYPES(CEnum):
    __size__ = 1
    __def__ = """
        enum {
            UBIFS_INO_NODE,
            UBIFS_DATA_NODE,
            UBIFS_DENT_NODE,
            UBIFS_XENT_NODE,
            UBIFS_TRUN_NODE,
            UBIFS_PAD_NODE,
            UBIFS_SB_NODE,
            UBIFS_MST_NODE,
            UBIFS_REF_NODE,
            UBIFS_IDX_NODE,
            UBIFS_CS_NODE,
            UBIFS_ORPH_NODE,
            UBIFS_AUTH_NODE,
            UBIFS_SIG_NODE,
            UBIFS_NODE_TYPES_CNT,
        }
    """

class UBIFS_CH(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __magic__ = "\x06\x10\x18\x31".encode("utf-8")  # 0x06101831
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_ch {
            __le32 magic;
            __le32 crc;
            __le64 sqnum;
            __le32 len;
            __u8 node_type;
            __u8 group_type;
            __u8 padding[2];
        };
    """
class UBIFS_BRANCH(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        #define UBIFS_KEY_SIZE 8
        
        struct ubifs_branch {
            __le32 lnum;
            __le32 offs;
            __le32 len;
            __u8 key[UBIFS_KEY_SIZE]; /* This is normally __u8 key[] but changed to fixed size for easy access */
        };
    """

class UBIFS_IDX_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_idx_node {
            struct UBIFS_CH ch;
            __le16 child_cnt;
            __le16 level;
            struct UBIFS_BRANCH branches[]; /* This is normally __u8 but changed to struct UBIFS_BRANCH for easy access */
        };
    """

class UBIFS_SB_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        #define UBIFS_MAX_HMAC_LEN 64
        #define UBIFS_MAX_HASH_LEN 64
    
        struct ubifs_sb_node {
            struct UBIFS_CH ch;
            __u8 padding[2];
            __u8 key_hash;
            __u8 key_fmt;
            __le32 flags;
            __le32 min_io_size;
            __le32 leb_size;
            __le32 leb_cnt;
            __le32 max_leb_cnt;
            __le64 max_bud_bytes;
            __le32 log_lebs;
            __le32 lpt_lebs;
            __le32 orph_lebs;
            __le32 jhead_cnt;
            __le32 fanout;
            __le32 lsave_cnt;
            __le32 fmt_version;
            __le16 default_compr;
            __u8 padding1[2];
            __le32 rp_uid;
            __le32 rp_gid;
            __le64 rp_size;
            __le32 time_gran;
            __u8 uuid[16];
            __le32 ro_compat_version;
            __u8 hmac[UBIFS_MAX_HMAC_LEN];
            __u8 hmac_wkm[UBIFS_MAX_HMAC_LEN];
            __le16 hash_algo;
            __u8 hash_mst[UBIFS_MAX_HASH_LEN];
            __u8 padding2[3774];
        };
    """


class UBIFS_MST_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_mst_node {
            struct UBIFS_CH ch;
            __le64 highest_inum;
            __le64 cmt_no;
            __le32 flags;
            __le32 log_lnum;
            __le32 root_lnum;
            __le32 root_offs;
            __le32 root_len;
            __le32 gc_lnum;
            __le32 ihead_lnum;
            __le32 ihead_offs;
            __le64 index_size;
            __le64 total_free;
            __le64 total_dirty;
            __le64 total_used;
            __le64 total_dead;
            __le64 total_dark;
            __le32 lpt_lnum;
            __le32 lpt_offs;
            __le32 nhead_lnum;
            __le32 nhead_offs;
            __le32 ltab_lnum;
            __le32 ltab_offs;
            __le32 lsave_lnum;
            __le32 lsave_offs;
            __le32 lscan_lnum;
            __le32 empty_lebs;
            __le32 idx_lebs;
            __le32 leb_cnt;
            __u8 hash_root_idx[UBIFS_MAX_HASH_LEN];
            __u8 hash_lpt[UBIFS_MAX_HASH_LEN];
            __u8 hmac[UBIFS_MAX_HMAC_LEN];
            __u8 padding[152];
        };
    """
