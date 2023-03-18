import cstruct as cstruct


class MemCStructExt(cstruct.MemCStruct):
    def parse(self, data, offset):
        self.unpack(data[offset:offset+self.size])