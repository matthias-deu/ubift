import logging
from abc import ABC, abstractmethod
from typing import List

from ubift.framework.mtd import Partition, Image
from ubift.framework.structs.ubi_structs import UBI_EC_HDR
from ubift.framework.util import find_signature

ubiftlog = logging.getLogger(__name__)

# When the UBIPartitioner is used, this constant will be used as Description of the Partition to mark it as an UBI instance
UBIPARTITIONER_UBI_DESCRIPTION = "UBI"
# When the UBIPartitioner is used, this constant will be used as Description of Partitions that do not contain UBI instances
UBIPARTITIONER_UNALLOCATED_DESCRIPTION = "Unallocated"

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

    @classmethod
    def _fill_partitions(cls, image: Image, partitions: List[Partition]) -> List[Partition]:
        """
        'Fills' the partitions created by the Partitioner so that the full size of the Image is covered. If a certain space is
        not covered by a specific Partition in the Image, a temporary Partition is created to mark 'unallocated' space.

        Example:  [free space] [UBI] [UBI] [free space] will be filled to [UNALLOCATED] [UBI] [UBI] [UNALLOCATED]
        """

        filled_partitions = partitions.copy()
        filled_partitions.sort(key=lambda _partition: _partition.offset)

        for i, partition in enumerate(partitions):
            if i+1 >= len(partitions):
                # Add 'unallocated' Partition at the end if necessary
                if partition.end != len(image.data) - 1:
                    end_partition = Partition(image, partition.end + 1, len(image.data) - 1, UBIPARTITIONER_UNALLOCATED_DESCRIPTION)
                    filled_partitions.append(end_partition)
                break
            # Add 'unallocated' Partition at the start if necessary
            if i == 0 and (partition.offset != 0):
                start_partition = Partition(image, 0, partitions[i].offset - 1, UBIPARTITIONER_UNALLOCATED_DESCRIPTION)
                filled_partitions.insert(0, start_partition)
            # Add 'unallocated' Partitions in between Partitions if necessary
            if partition.end + 1 != partitions[i+1].offset:
                start = partition.end + 1
                end = partitions[i+1].offset - 1
                between_partition = Partition(image, start, end, UBIPARTITIONER_UNALLOCATED_DESCRIPTION)
                filled_partitions.insert(filled_partitions.index(partition)+1, between_partition)

        return filled_partitions


class UBIPartitioner(Partitioner):
    """
    Partitions a raw Image by looking for UBI magic bytes. All parts that
    do not belong to UBI instances are treated as unallocated partitions by this Partitioner.
    """
    def __init__(self):
        super().__init__()

    def partition(self, image: Image, fill_partitions: bool = True) -> List[Partition]:
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

        if fill_partitions:
            partitions = Partitioner._fill_partitions(image, partitions)

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

