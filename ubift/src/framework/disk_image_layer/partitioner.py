from abc import ABC, abstractmethod
from typing import List

from ubift.src.framework.base import find_signature
from ubift.src.framework.disk_image_layer.mtd import Image, Partition
from ubift.src.framework.volume_layer.ubi_structs import UBI_EC_HDR
from ubift.src.logging import ubiftlog

class Partitioner(ABC):
    """
    A Partitoner partitions a raw Image. Sub-classes do this based
    on various methods, such as magic-bytes or information that may be present in bootloaders etc.
    """
    def __init__(self, image: Image):
        self._image = image
        self._partitions = self._partition()

    @abstractmethod
    def _partition(self) -> List[Partition]:
        pass

    @property
    def partitions(self):
        return self._partitions

    @property
    def image(self):
        return self._image

class UBIPartitioner(Partitioner):
    """
    Partitions a raw Image by looking for UBI magic bytes. All parts that
    do not belong to UBI instances are marked treated as unallocated partitions.
    """
    def __init__(self, image: Image):
        super().__init__(image)

    def _partition(self) -> List[Partition]:
        """
        Partitions the Image based on UBI instances. Will try to create one Partition per UBI instance.
        """
        if self.image is None:
            ubiftlog.error(f"[-] Not a valid Image, cannot partition.")
        ubiftlog.info(f"[!] Trying to partition the Image based on UBI instances.")

        partitions = []

        partition = self._create_partition(0)
        while partition is not None:
            partitions.append(partition)
            partition = self._create_partition(partition.offset+partition.len+1)


    def _create_partition(self, start: int) -> Partition:
        """
        This function tries to create a Partition starting from a position based on continous UBI headers it finds.
        """
        start = find_signature(self.image.data, UBI_EC_HDR.__magic__, start)
        if start < 0:
            return None

        current = start
        while self.image.data[current:current+4] == UBI_EC_HDR.__magic__:
            current += self.image.block_size
        end = current

        ubiftlog.info(f"[+] Found UBI partition at offset {start} to {end} (len: {end-start}, PEBs: {(end-start) // self.image.block_size})")

        return Partition(self.image, start, end-start, "UBI")

