from typing import Dict, Any

import cstruct as cstruct

class MemCStructExt(cstruct.MemCStruct):
    def __init__(self, data=None, offset=None, **kargs: Dict[str, Any]):
        buffer = data[offset:offset + self.size] if data is not None and offset is not None else None
        super().__init__(buffer=buffer, kargs=kargs)

    def parse(self, data, offset):
        self.unpack(data[offset:offset + self.size])
