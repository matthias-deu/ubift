import logging
from abc import ABC, abstractmethod
from typing import List

from ubift.framework.mtd import Partition, Image
from ubift.framework.structs.ubi_structs import UBI_EC_HDR
from ubift.framework.ubi import UBI
from ubift.framework.util import find_signature

ubiftlog = logging.getLogger(__name__)

# When the UBIPartitioner is used, this constant will be used as Description of the Partition to mark it as an UBI instance
UBIPARTITIONER_UBI_DESCRIPTION = "UBI"
# When the UBIPartitioner is used, this constant will be used as Description of Partitions that do not contain UBI instances
UBIPARTITIONER_UNALLOCATED = "Unallocated"

class Partitioner(ABC):
    """
    A Partitoner partitions a raw Image. Sub-classes do this based
    on various methods, such as magic-bytes or information that may be present in bootloaders etc.
    """
    def __init__(self):
        pass

    @abstractmethod
    def partition(self, image: Image) -> List[Partition]:
        pass


class UBIPartitioner(Partitioner):
    """
    Partitions a raw Image by looking for UBI magic bytes. All parts that
    do not belong to UBI instances are treated as unallocated partitions by this Partitioner.
    """
    def __init__(self):
        super().__init__()

    def partition(self, image: Image) -> List[Partition]:
        """
        Partitions the Image based on UBI instances. Will try to create one Partition per UBI instance.
        """
        if image is None:
            ubiftlog.error(f"[-] Not a valid Image, cannot partition.")
        ubiftlog.info(f"[!] Trying to partition the Image based on UBI instances.")

        partitions = []

        partition = self._create_partition(image, 0)
        while partition is not None:
            partitions.append(partition)
            partition = self._create_partition(image, partition.end+1)

        return partitions


    def _create_partition(self, image: Image, start: int) -> Partition:
        """
        This function tries to create a Partition starting from a position based on continous UBI headers it finds.
        """
        start = find_signature(image.data, UBI_EC_HDR.__magic__, start)
        if start < 0:
            return None

        current = start
        while image.data[current:current+4] == UBI_EC_HDR.__magic__:
            current += image.block_size
        end = current-1

        partition = Partition(image, start, end, UBIPARTITIONER_UBI_DESCRIPTION)

        return partition

