import binascii

from src.exception import UBIFTException
from src.framework.volume_layer.ubi import find_signature, ubiftlog
from src.framework.volume_layer.ubi_structs import UBI_EC_HDR, UBI_VID_HDR


class Image:
    def __init__(self, data: bytes, block_size: int = -1, page_size: int = -1, oob_size: int = -1):
        self.oob_size = oob_size
        self.page_size = page_size if page_size > 0 else self._guess_page_size(data)
        self.block_size = block_size if block_size > 0 else self._guess_block_size(data)
        self.data = data if oob_size < 0 else Image.strip_oob(data, self.block_size, self.page_size, oob_size)

        ubiftlog.info(f"[!] Initialized Image (block_size:{self.block_size}, page_size:{self.page_size}, oob_size:{self.oob_size}, data_len:{len(self.data)})")

    def _guess_block_size(self, data: bytes) -> int:
        ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
        if ec_hdr_offset < 0:
            raise UBIFTException("Block size not specified, cannot guess size neither because no UBI_EC_HDR signatures found.")
        possible_block_sizes = [i*self.page_size if self.oob_size < 0 else (i*self.page_size+i*self.oob_size) for i in range(1, 128)]
        for i,block_size in enumerate(possible_block_sizes):
            if data[ec_hdr_offset+block_size:ec_hdr_offset+block_size+4] == UBI_EC_HDR.__magic__:
                guessed_size = (self.page_size * (i+1))
                ubiftlog.info(f"[+] Guessed block_size: {guessed_size} ({guessed_size // 1024}KiB)")
                return guessed_size

        ubiftlog.info(f"[-] Block size not specified, cannot guess size neither.")
        raise UBIFTException("Block size not specified, cannot guess size neither.")

    def _guess_page_size(self, data: bytes) -> int:
        """
        Tries to guess the page size by calculating the space between an ubi_ec_hdr and a ubi_vid_hdr
        NOTE: This will fail if the flash allows sub-paging because UBI will use that feature to fit both headers inside one page
        :return:
        """
        ec_hdr_offset = find_signature(data, UBI_EC_HDR.__magic__)
        if ec_hdr_offset < 0:
            raise UBIFTException(
                "Page size not specified, cannot guess size neither because no UBI_EC_HDR signatures found.")
        ec_hdr = UBI_EC_HDR()
        ec_hdr.parse(data, ec_hdr_offset)
        if ec_hdr.vid_hdr_offset > 0:
            self.page_size = ec_hdr.vid_hdr_offset
            ubiftlog.info(f"[+] Guessed page_size: {ec_hdr.vid_hdr_offset} ({ec_hdr.vid_hdr_offset // 1024}KiB)")
            return ec_hdr.vid_hdr_offset

        ubiftlog.info(f"[-] Page size not specified, cannot guess size neither.")
        raise UBIFTException("Page size not specified, cannot guess page neither.")

    @classmethod
    def strip_oob(cls, data: bytes, block_size: int, page_size: int, oob_size: int) -> bytes:
        """
        Strips OOB data out of binary data. This assumes that the OOB is located at the end of every page.
        TODO: OOB can also be located as a group in some flashes
        """

        ubiftlog.info(f"[!] Stripping OOB with size {oob_size} from every page.")

        ptr = 0
        pages = block_size // page_size
        block_size = block_size + pages * oob_size
        blocks = len(data) // block_size

        stripped_data = bytearray()
        for block in range(blocks):
            ptr = block * 64 * page_size
            for page in range(pages):
                stripped_data += data[ptr:ptr+page_size]
                ptr += oob_size

        return stripped_data

class Partition:
    def __init__(self, img: Image, offset: int, len: int, name: str):
        pass