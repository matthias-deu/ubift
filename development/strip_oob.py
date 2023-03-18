# https://github.com/Hitsxx/NandTool/blob/master/Nand-dump-tool.py

import sys

UBI_IMG_PATH = r"D:\2023-03-16 Parrot_ANAFI_TC58BVG1S3HBAI6_ARBEITSKOPIE_17.3.2023.bin"
OUTPUT_PATH = r"D:\2023-03-16 Parrot_ANAFI_TC58BVG1S3HBAI6_ARBEITSKOPIE_17.3.2023_stripped.bin"

if __name__ == '__main__':
    orig_dump = open(UBI_IMG_PATH, 'rb')
    out_dump = open(OUTPUT_PATH, 'wb')
    PAGE, OOB = 2048, 64
    PAGESIZE = (PAGE + OOB)
    for block in range(2048):
        orig_dump.seek(block * 64 * PAGESIZE)
        for page in range(64):
            out_dump.write(orig_dump.read(PAGE))
            orig_dump.seek(OOB, 1)
    out_dump.close()
    orig_dump.close()