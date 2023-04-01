from typing import List

from ubift import exception
from ubift.framework.structs.ubifs_structs import UBIFS_SB_NODE, UBIFS_MST_NODE, UBIFS_NODE_TYPES, UBIFS_CH, \
    UBIFS_IDX_NODE, UBIFS_BRANCH
from ubift.framework.ubi import UBIVolume, LEB
from ubift.framework.util import crc32
from ubift.logging import ubiftlog

# Which master node is used (there are two identical ones)
UBIFS_MASTERNODE_INDEX = 0
# Size of a key in KiB
UBIFS_KEY_SIZE = 8


class UBIFS:
    """
    Represents an UBIFS instance which resides within an UBI volume.

    LEB 0 -> Superblock node
    LEB 1 and 2 -> Master node (two identical copies)
    """

    def __init__(self, ubi_volume: UBIVolume):
        self._ubi_volume = ubi_volume

        self.superblock = UBIFS_SB_NODE(self.ubi_volume.lebs[0].data, 0)
        self.masternodes = [UBIFS_MST_NODE(self.ubi_volume.lebs[1].data, 0),
                            UBIFS_MST_NODE(self.ubi_volume.lebs[2].data, 0)]
        self._root_idx_node = self._parse_root_idx_node(self.masternodes[UBIFS_MASTERNODE_INDEX])
        print(self._root_idx_node)

        if not self._validate():
            raise exception.UBIFTException("[-] Invalid UBIFS instance for UBI volume {self._ubi_volume}")

        ubiftlog.info(f"[!] Initialized UBIFS instance for UBI volume {self._ubi_volume}")

    def _parse_root_idx_node(self, masternode: UBIFS_MST_NODE) -> UBIFS_IDX_NODE:
        """
        :masternode: An instance of a UBIFS_MST_NODE that is used to determine the position of the root node
        :return: Returns the root node of the B-Tree as an instance of a UBIFS_IDX_NODE
        """
        root_lnum = masternode.root_lnum
        root_offset = masternode.root_offs

        root_idx = UBIFS_IDX_NODE(self.ubi_volume.lebs[root_lnum].data, root_offset)

        # Parse it again with the 'cstruct.set_flexible_array_length' parameter set, which will parse the UBIFS_BRANCH instances.
        root_idx.set_flexible_array_length(root_idx.child_cnt)
        root_idx.parse(self.ubi_volume.lebs[root_lnum].data, root_offset)

        # Deprecated, instead 'cstruct.set_flexible_array_length' is used.
        # root_idx.branches = self._parse_branches(root_idx.child_cnt, self.ubi_volume.lebs[root_lnum], root_offset + UBIFS_IDX_NODE.size)

        return root_idx

    def _parse_branches(self, branch_cnt: int, leb: LEB, offset: int) -> List[UBIFS_BRANCH]:
        """
        This function parses and creates UBIFS_BRANCH instances that are a flexible member of a UBIFS_IDX_NODE.
        :param branch_cnt: How many braches there are. This is defined in an instance of UBIFS_IDX_NODE.child_cnt
        :param leb: LEB that contains the UBIFS_IDX_NODE
        :param offset: Offset where the branches start
        :return: List of UBIFS_BRANCH instances
        """
        branches: List[UBIFS_BRANCH] = []
        cur = offset
        for off in range(branch_cnt):
            branch = UBIFS_BRANCH(leb.data, cur)
            cur += UBIFS_BRANCH.size

            branch.key = leb.data[cur:cur + UBIFS_KEY_SIZE]
            cur += UBIFS_KEY_SIZE

            branches.append(branch)

        return branches

    def _validate(self) -> bool:
        """
        Performs various validity checks for the UBIFS instance.
        Warnings are shown but they still lead to a return value of 'True'.
        :return:
        """
        if self.superblock is None:
            ubiftlog.error("[-] There is no superblock node.")
            return False

        if len(self.masternodes) == 0:
            ubiftlog.error("[-] There is no master node.")
            return False
        elif len(self.masternodes) == 1:
            ubiftlog.warn("[-] There is only one master node (expected: 2).")
        elif len(self.masternodes) == 2:
            # Add an additional 8 to their offsets to skip the '__le64 sqnum', because both masternodes have different sequence numbers.
            if crc32(self.masternodes[0].pack()[8 + 8:]) != crc32(self.masternodes[1].pack()[8 + 8:]):
                ubiftlog.warn(
                    "[-] Master nodes have different CRC32, this should never happen under normal circumstances. It might be possible that one master node is corrupted.")

        for masternode in self.masternodes:
            if masternode.ch.crc != crc32(masternode.pack()[8:]):
                ubiftlog.warn("[-] Master nodes have invalid CRC32.")

        return True

    @property
    def ubi_volume(self) -> UBIVolume:
        return self._ubi_volume
