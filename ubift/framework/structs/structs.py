import cstruct as cstruct

from typing import Dict, Any

COMMON_TYPEDEFS = """

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

    def validate_magic(self):
        if hasattr(self, "__magic__") and hasattr(self, "magic"):
            return self.__magic__.hex() == hex(self.magic)[2:]
        else:
            print(f"[-] Cannot validate {type(self)} because either missing '__magic__' or 'magic' property.")
            return False

    def parse(self, data, offset):
        self.unpack(data[offset:offset + self.size])
