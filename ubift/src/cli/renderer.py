import logging
import sys

from ubift.src.framework.disk_image_layer.mtd import Image
from ubift.src.logging import ubiftlog


def readable_size(num, suffix="B"):
    if num < 0:
        return "-"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def zpad(num: int, len: str) -> int:
    len = "0" + str(len)
    return format(num, len)

def volumelayer_render(image: Image, outfd=sys.stdout) -> None:
    logging.disable(logging.INFO) # TODO: Remove this and add a -verbose parameter to enable logging if needed

    outfd.write(f"MTD Image\n\n")
    outfd.write(f"Size: {readable_size(len(image.data))}\n")
    outfd.write(f"Erase Block Size: {readable_size(image.block_size)}\n")
    outfd.write(f"Page Size: {readable_size(image.page_size)}\n")

    outfd.write(f"Physical Erase Blocks: {len(image.data) // image.block_size}\n")
    outfd.write(f"Pages per Erase Block: {image.block_size // image.page_size}\n")
    outfd.write("\n")

    mtd_parts = image.get_full_partitions()

    outfd.write("\tStart\t\t\tEnd\t\t\tLength\t\t\tDescription\n")
    for i,partition in enumerate(mtd_parts):
        start = zpad(partition.offset // image.block_size, 10)
        end = zpad((partition.offset+partition.len) // image.block_size, 10)
        length = zpad(partition.len // image.block_size, 10)
        outfd.write(f"{zpad(i, 3)}:\t{start}\t\t{end}\t\t{length}\t\t{partition.name}\n")


