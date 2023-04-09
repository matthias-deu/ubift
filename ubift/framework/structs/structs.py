import cstruct as cstruct

from typing import Dict, Any

from cstruct import BIG_ENDIAN

COMMON_TYPEDEFS = """
    #define UBIFS_MAX_KEY_LEN 16

    typedef uint8 __u8;

    typedef uint16 __le16;
    typedef uint32 __le32;
    typedef uint64 __le64;

    typedef uint16 __be16;
    typedef uint32 __be32;
    typedef uint64 __be64;

 """


class MemCStructExt(cstruct.MemCStruct):
    def __init__(self, data=None, offset=None, **kargs: Dict[str, Any]):
        buffer = data[offset:offset + self.size] if data is not None and offset is not None else None
        super().__init__(buffer=buffer, kargs=kargs)

    def validate_magic(self) -> bool:
        if hasattr(self, "__magic__") and hasattr(self, "magic"):
            # TODO: This is probably not right but it works somehow
            if self.__byte_order__ == BIG_ENDIAN:
                return self.__magic__.hex().strip('0') == hex(self.magic)[2:]
            else:
                return self.__magic__.hex().strip('0') == hex(self.magic)[2:]
        elif not hasattr(self, "magic"):
            print(f"[-] Cannot validate {type(self)} because 'magic' property missing.")
            return False
        else:
            return True

    def parse(self, data, offset):
        self.unpack(data[offset:offset + self.size])


class FDT_HEADER(MemCStructExt):
    """
    Header of a flattened device tree.
    See https://devicetree-specification.readthedocs.io/en/v0.3/flattened-format.html
    """
    __byte_order__ = BIG_ENDIAN
    __magic__ = b'\xd0\r\xfe\xed'
    __def__ = COMMON_TYPEDEFS + """
        struct fdt_header {
            uint32_t magic;
            uint32_t totalsize;
            uint32_t off_dt_struct;
            uint32_t off_dt_strings;
            uint32_t off_mem_rsvmap;
            uint32_t version;
            uint32_t last_comp_version;
            uint32_t boot_cpuid_phys;
            uint32_t size_dt_strings;
            uint32_t size_dt_struct;
        };
    """
