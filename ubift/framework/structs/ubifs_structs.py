# NOTE!
# The structs and enums etc are taken from the Linux kernel at /linux/fs/ubifs/ubifs-media.h

import struct
from enum import Enum
from functools import total_ordering
from typing import Any, List

from cstruct import LITTLE_ENDIAN, CEnum

from ubift import exception
from ubift.framework import compression
from ubift.framework.structs.structs import MemCStructExt, COMMON_TYPEDEFS
from ubift.logging import ubiftlog


class UBIFS_JOURNAL_HEADS(Enum):
    """
    UBIFS' journal is multiheaded. It consists of three journal heads, which are:
    - garbage collector jhead (gc copies valid data to this journal during its cleaning process)
    - base jhead (contains non-data nodes)
    - data head (contains data nodes)
    """
    UBIFS_GC_HEAD = 0
    UBIFS_BASE_HEAD = 1
    UBIFS_DATA_HEAD = 2


class UBIFS_COMPRESSION_TYPE(CEnum):
    __size__ = 2
    __def__ = """
        enum {
            UBIFS_COMPR_NONE,
            UBIFS_COMPR_LZO,
            UBIFS_COMPR_ZLIB,
            UBIFS_COMPR_ZSTD,
            UBIFS_COMPR_TYPES_CNT,
        };
    """


class UBIFS_INODE_TYPES(CEnum):
    __size__ = 1
    __def__ = """
        enum {
            UBIFS_ITYPE_REG,  /* regular file */
            UBIFS_ITYPE_DIR,  /* directory */
            UBIFS_ITYPE_LNK,  /* soft link */
            UBIFS_ITYPE_BLK,  /* block device node */
            UBIFS_ITYPE_CHR,  /* character device node*/
            UBIFS_ITYPE_FIFO, /* fifo */
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


@total_ordering
class UBIFS_KEY:
    def __init__(self, data: bytes):
        self.inode_num = struct.unpack("<L", data[:4])[0]
        value = struct.unpack("<L", data[4:])[0]
        self.key_type = value >> 29
        self.payload = value & 0x1FFFFFFF

    def __eq__(self, other):
        if not isinstance(other, UBIFS_KEY):
            return NotImplemented
        return (self.inode_num, self.key_type, self.payload) == (other.inode_num, other.key_type, other.payload)

    def __lt__(self, other):
        if not isinstance(other, UBIFS_KEY):
            return NotImplemented
        return (self.inode_num, self.key_type, self.payload) < (other.inode_num, other.key_type, other.payload)

    @classmethod
    def create_key(cls, inum: int, key_type: UBIFS_KEY_TYPES, payload: bytes = 0) -> 'UBIFS_KEY':
        """
        Creates an instance of a UBIFS_KEY with given parameters.
        :param inum: inode number (32bits)
        :param key_type: Type of the key, see 'UBIFS_KEY_TYPES'-Enum for possible types. (3bits)
        :param payload: Payload (last 29bits of key), its meaníng depends on key_type.
        :return: Returns an instance of UBIFS_KEY
        """
        return UBIFS_KEY(struct.pack("<LL", inum, (key_type << 29) | payload))

    @classmethod
    def from_bytearray(cls, bytes_list: List[int]) -> 'UBIFS_KEY':
        """
        Creates an instance of UBIFS_KEY for a given array of bytes (which is the format provided by cstruct)
        :param bytes_list: Array of bytes for the key, i.e. key = [232, 21, ....] (either full length of 16 bytes or 8 bytes)
        :return: Instance of UBIFS_KEY if invalid array of bytes
        """
        if len(bytes_list) > 16 or len(bytes_list) < 8:
            ubiftlog.info(f"[!] Cannot create UBIFS_KEY from bytes, because it has invalid size: {bytes_list}")

        return UBIFS_KEY(bytes(bytes_list[:8]))

    def pack(self) -> bytes:
        return struct.pack("<LL", self.inode_num, (self.key_type << 29) | self.payload)

    def __str__(self):
        return f"UBIFS_KEY(inode_num:{self.inode_num}, key_type:{UBIFS_KEY_TYPES(self.key_type)}, payload:{self.payload})"

    def __repr__(self):
        return f"UBIFS_KEY(inode_num:{self.inode_num}, key_type:{UBIFS_KEY_TYPES(self.key_type)}, payload:{self.payload})"


class UBIFS_CH(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __magic__ = "\x06\x10\x18\x31".encode("utf-8")  # 0x06101831   \x31\x18\x10\x06
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


class UBIFS_REF_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_ref_node {
        struct UBIFS_CH ch;
        __le32 lnum;
        __le32 offs;
        __le32 jhead;
        __u8 padding[28];
    } __packed;
    """


class UBIFS_PAD_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_pad_node {
            struct UBIFS_CH ch;
            __le32 pad_len;
        } __packed;
    """


class UBIFS_CS_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_cs_node {
            struct UBIFS_CH ch;
            __le64 cmt_no;
        } __packed;
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

    def python_key(self) -> UBIFS_KEY:
        """
        :return: Returns the cstruct key as instance of UBIFS_KEY (which can be used for comparisons etc)
        """
        return UBIFS_KEY(bytes(self.key)[:8]) if self.key is not None else None


class UBIFS_DATA_NODE(MemCStructExt):
    def __init__(self, data: bytes, offset: int, *args, **kwargs):
        """
        Creates an instance of a UBIFS_DENT_NODE. Automatically parses its name based on name_len.
        :param data:
        :param offset:
        :param args:
        :param kwargs:
        """
        self.decompr_data = None
        compr_data_len = UBIFS_CH(data, offset).len - UBIFS_DATA_NODE.__size__

        if compr_data_len > 4096:
            raise exception.UBIFTException(
                f"[-] More than 4096 bytes of data found in a data node, which is not possible. {compr_data_len}")

        if compr_data_len is not None and compr_data_len > 0:
            self.set_flexible_array_length(compr_data_len)

        super().__init__(data, offset, *args, **kwargs)

    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_data_node {
            struct UBIFS_CH ch;
            __u8 key[UBIFS_MAX_KEY_LEN];
            __le32 data_size; /* The original name is size, but this is a reserved keyword in cstruct */
            __le16 compr_type;
            __le16 compr_size;
            __u8 data[];
        } __packed;
    """

    @property
    def decompressed_data(self, force_reload: bool = False):
        if self.decompr_data is not None and not force_reload:
            return self.decompr_data
        else:
            self.decompr_data = compression.decompress(bytes(self.data), self.compr_type, self.data_size)
            if len(self.decompr_data) != self.data_size:
                ubiftlog.warn(
                    f"[-] Data node decompressed data does not equal its data size {self.decompr_data} -> {self.data_size}")
            return self.decompr_data


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


class UBIFS_ORPH_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_orph_node {
            struct UBIFS_CH ch;
            __le64 cmt_no;
            __le64 inos[];
        };
    """

    @property
    def orphans(self) -> list[int]:
        """
        :return: Returns the inode numbers that this orphan node references in its flexibel inos[] array
        """
        orphans = (self.ch.len - UBIFS_CH.__size__ - 8) // 8
        self.set_flexible_array_length(orphans)
        if len(self.inos) == 1 and self.inos[0] == 0:
            return []
        else:
            return self.inos

    @property
    def is_last_node_of_commit(self):
        """
        If the top bit is set, it means that it is the last node of the commit
        :return:
        """
        return self.cmt_no >> 63

    @property
    def real_cmt_no(self):
        """
        Sets top bit to 0 and returns the cmt_no
        :return:
        """
        return self.cmt_no & 0x7FFFFFFFFFFFFFFF


class UBIFS_TRUN_NODE(MemCStructExt):
    __byte_order__ = LITTLE_ENDIAN
    __def__ = COMMON_TYPEDEFS + """
        struct ubifs_trun_node {
            struct UBIFS_CH ch;
            __le32 inum;
            __u8 padding[12];
            __le64 old_size;
            __le64 new_size;
        };
    """


class UBIFS_INO_NODE(MemCStructExt):
    def __init__(self, data=None, offset=None, *args, **kwargs):
        """
        Creates an instance of a UBIFS_DENT_NODE. Automatically parses its name based on name_len.
        :param data:
        :param offset:
        :param args:
        :param kwargs:
        """
        data_len_offs = offset + UBIFS_CH.size + 16 + (5 * 8) + (8 * 4)
        data_len = struct.unpack("<I", data[data_len_offs:data_len_offs + 4])[0]
        if data_len is not None and data_len > 0:
            self.set_flexible_array_length(data_len)
        super().__init__(data, offset, *args, **kwargs)

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
        Prints the name of the directory entry by concatenating the hex values and decoding them
        @return:
        """
        formatted_name = [f"{x:x}" for x in list(self.name)] # TODO: Apprently this does not work if the last integer is a "0" ? Causes the hex string to miss a trailing 0
        formatted_name = "".join(formatted_name)
        return bytearray.fromhex(formatted_name).decode(errors="ignore")


# Maps node_type number to a specific class implementing that node type
node_mapping = {
    UBIFS_NODE_TYPES.UBIFS_INO_NODE: UBIFS_INO_NODE,
    UBIFS_NODE_TYPES.UBIFS_DATA_NODE: UBIFS_DATA_NODE,
    UBIFS_NODE_TYPES.UBIFS_DENT_NODE: UBIFS_DENT_NODE,
    # UBIFS_NODE_TYPES.UBIFS.XENT_NODE:
    UBIFS_NODE_TYPES.UBIFS_TRUN_NODE: UBIFS_TRUN_NODE,
    UBIFS_NODE_TYPES.UBIFS_PAD_NODE: UBIFS_PAD_NODE,
    UBIFS_NODE_TYPES.UBIFS_SB_NODE: UBIFS_SB_NODE,
    UBIFS_NODE_TYPES.UBIFS_MST_NODE: UBIFS_MST_NODE,
    UBIFS_NODE_TYPES.UBIFS_REF_NODE: UBIFS_REF_NODE,
    UBIFS_NODE_TYPES.UBIFS_IDX_NODE: UBIFS_IDX_NODE,
    UBIFS_NODE_TYPES.UBIFS_CS_NODE: UBIFS_CS_NODE,
    UBIFS_NODE_TYPES.UBIFS_ORPH_NODE: UBIFS_ORPH_NODE
    # UBIFS_NODE_TYPES.UBIFS_AUTH_NODE:
    # UBIFS_NODE_TYPES.UBIFS_SIG_NODE:
}


def parse_arbitrary_node(data: bytes, offset: int) -> Any:
    """
    Creates a specific node by parsing the common header found at a specific position.
    :param data: Data containing the node
    :param offset: Offset in data where the node starts
    :return: Specific node instance, depending on node_type in the common header
    """
    try:
        ch_hdr = UBIFS_CH(data, offset)
        cls = node_mapping[ch_hdr.node_type]
        node = cls(data, offset)
        return node
    except:
        return None
