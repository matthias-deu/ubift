import struct
from typing import Dict, Any, List

from cstruct import LITTLE_ENDIAN, CEnum

from ubift.framework.structs.structs import MemCStructExt, COMMON_TYPEDEFS


class UBIFS_INODE_TYPES(CEnum):
    __size__ = 1
    __def__ = """
        enum {
            UBIFS_ITYPE_REG,  /* regular file */
            UBIFS_ITYPE_DIR,  /* directory */
            UBIFS_ITYPE_LNK,  /* soft link */
            UBIFS_ITYPE_BLK,  /* block device node */
            UBIFS_ITYPE_CHR,  /* character device node*/
            UBIFS_ITYPE_FIFO, /* fifo*/
            UBIFS_ITYPE_SOCK, /* socket */
            UBIFS_ITYPES_CNT, /* counth of possible inode types */
        };
    """


class UBIFS_KEY_TYPES(CEnum):
    __size__ = 1
    __def__ = """
        enum {
            UBIFS_INO_KEY,
            UBIFS_DATA_KEY,
            UBIFS_DENT_KEY,
            UBIFS_XENT_KEY,
            UBIFS_KEY_TYPES_CNT,
        };
    """


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


class UBIFS_KEY:
    def __init__(self, data: bytes):
        self.inode_num = struct.unpack("<L", data[:4])[0]
        value = struct.unpack("<L", data[4:])[0]
        self.key_type = value >> 29
        self.payload = value & 0x1FFFFFFF

    @classmethod
    def create_key(cls, inum: int, key_type: UBIFS_KEY_TYPES, payload: bytes = 0) -> 'UBIFS_KEY':
        """
        Creates an instance of a UBIFS_KEY with given parameters. The payload can be None, putting 0-bytes in their place.
        :param inum: inode number
        :param key_type: Type of the key, see 'UBIFS_KEY_TYPES'-Enum for possible types.
        :param payload: Payload (last 29bits of key), can be None, in which case 0-bits will be used.
        :return: Returns an instance of UBIFS_KEY
        """
        return UBIFS_KEY(struct.pack("<LL", inum, (key_type << 29) | payload))

    def __str__(self):
        return f"UBIFS_KEY(inode_num:{self.inode_num}, key_type:{UBIFS_KEY_TYPES(self.key_type)}, payload:{self.payload})"

    def __repr__(self):
        return f"UBIFS_KEY(inode_num:{self.inode_num}, key_type:{UBIFS_KEY_TYPES(self.key_type)}, payload:{self.payload})"


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
            __u8 key[UBIFS_KEY_SIZE];  /* This is normally __u8 key[] but changed to fixed size for easy access */
        };
    """


class UBIFS_IDX_NODE(MemCStructExt):
    def __init__(self, data=None, offset=None, *args, **kwargs):
        """
        Creates an instance of a UBIFS_IDX_NODE. Automatically parses its instances of UBIFS_BRANCH.
        :param data:
        :param offset:
        :param args:
        :param kwargs:
        """
        child_cnt = struct.unpack("<H", data[offset + UBIFS_CH.size:offset + UBIFS_CH.size + 2])[0]
        if child_cnt is not None and child_cnt > 0:
            self.set_flexible_array_length(child_cnt)
        super(UBIFS_IDX_NODE, self).__init__(data, offset, *args, **kwargs)

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


class UBIFS_INO_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_ino_node {
            struct UBIFS_CH ch;
            __u8 key[UBIFS_MAX_KEY_LEN];
            __le64 creat_sqnum;
            __le64 ino_size; /* The original name is size, but this is a reserved keyword in cstruct */
            __le64 atime_sec;
            __le64 ctime_sec;
            __le64 mtime_sec;
            __le32 atime_nsec;
            __le32 ctime_nsec;
            __le32 mtime_nsec;
            __le32 nlink;
            __le32 uid;
            __le32 gid;
            __le32 mode;
            __le32 flags;
            __le32 data_len;
            __le32 xattr_cnt;
            __le32 xattr_size;
            __u8 padding1[4]; /* Watch 'zero_ino_node_unused()' if changing! */
            __le32 xattr_names;
            __le16 compr_type;
            __u8 padding2[26]; /* Watch 'zero_ino_node_unused()' if changing! */
            __u8 data[];
    };
    """


class UBIFS_DENT_NODE(MemCStructExt):
    def __init__(self, data=None, offset=None, *args, **kwargs):
        """
        Creates an instance of a UBIFS_DENT_NODE. Automatically parses its name based on name_len.
        :param data:
        :param offset:
        :param args:
        :param kwargs:
        """
        nlen_offs = offset + UBIFS_CH.size + 16 + 8 + 1 + 1
        name_len = struct.unpack("<H", data[nlen_offs:nlen_offs + 2])[0]
        if name_len is not None and name_len > 0:
            self.set_flexible_array_length(name_len)
        super(UBIFS_DENT_NODE, self).__init__(data, offset, *args, **kwargs)

    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_dent_node {
        struct UBIFS_CH ch;
        __u8 key[UBIFS_MAX_KEY_LEN];
        __le64 inum;
        __u8 padding1;
        __u8 type;
        __le16 nlen;
        __le32 cookie;
        __u8 name[];
    } __packed;
    """

    def formatted_name(self) -> str:
        """
        Prints the name of the Volume by concatenating the hex values and decoding them
        @return:
        """
        formatted_name = [f"{x:x}" for x in list(self.name)]
        formatted_name = "".join(formatted_name)
        return bytearray.fromhex(formatted_name).decode()
