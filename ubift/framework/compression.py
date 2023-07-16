# This file provides several compression functions that are needed for UBIFS, since it provides on-the-fly data compression
# See UBIFS_COMPRESSION_TYPE in ubifs_structs.py for possible types
import zlib
import zstandard
import lzo

from ubift import exception
from ubift.framework.structs.ubifs_structs import UBIFS_COMPRESSION_TYPE
from ubift.logging import ubiftlog


def decompress(data: bytes, compr_type: int, size: int = None) -> bytes:
    """
    Decompresses data based on UBIFS_COMPRESSION_TYPE which can be found in UBIFS_DATA_NODE
    :param data: Compressed data
    :param compr_type: Compression type (see ubifs_structs.UBIFS_COMPRESSION_TYPE)
    :param size: Size of buffer length that will fit output, needed by LZO-compression, for other compression methods this value does not matter. Value for this can be found in UBIFS_DATA_NODE
    :return: Uncompressed data
    """
    try:
        if compr_type == 0: # UBIFS_COMPRESSION_TYPE.UBIFS_COMPR_NONE
            return data
        elif compr_type == 1: # UBIFS_COMPRESSION_TYPE.UBIFS_COMPR_LZO
            return lzo.decompress(data, False, size)
        elif compr_type == 2: # UBIFS_COMPRESSION_TYPE.UBIFS_COMPR_ZLIB
            return zlib.decompress(data, -zlib.MAX_WBITS)
        elif compr_type == 3: # UBIFS_COMPRESSION_TYPE.UBIFS_COMPR_ZSTD
            return zstandard.decompress(data, size)
        else:
            raise exception.UBIFTException(f"Data is compressed with unknown type. ({compr_type})")
    except Exception as e:
        ubiftlog.warn(
            f"[-] Error while decompressing data using {UBIFS_COMPRESSION_TYPE(compr_type).name}: {e}")
        return bytes()

