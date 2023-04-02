import struct
from typing import List, Callable

from ubift import exception
from ubift.framework.structs.ubifs_structs import UBIFS_SB_NODE, UBIFS_MST_NODE, UBIFS_NODE_TYPES, UBIFS_CH, \
    UBIFS_IDX_NODE, UBIFS_BRANCH, UBIFS_KEY, UBIFS_DENT_NODE, UBIFS_INO_NODE, UBIFS_INODE_TYPES, UBIFS_KEY_TYPES
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

        if not self._validate():
            raise exception.UBIFTException(f"[-] Invalid UBIFS instance for UBI volume {self._ubi_volume}")

        ubiftlog.info(f"[!] Initialized UBIFS instance for UBI volume {self._ubi_volume}")

        #self._traverse(self._root_idx_node, self._test_visitor)
        key = UBIFS_KEY.create_key(1, UBIFS_KEY_TYPES.UBIFS_INO_KEY)
        self._find(self._root_idx_node, None)

    def _parse_root_idx_node(self, masternode: UBIFS_MST_NODE) -> UBIFS_IDX_NODE:
        """
        Fetches the root node from a given master node
        :masternode: An instance of a UBIFS_MST_NODE that is used to determine the position of the root node
        :return: Returns the root node of the B-Tree as an instance of a UBIFS_IDX_NODE
        """
        root_lnum = masternode.root_lnum
        root_offset = masternode.root_offs

        root_idx = UBIFS_IDX_NODE(self.ubi_volume.lebs[root_lnum].data, root_offset)

        return root_idx

    def _find(self, root: UBIFS_IDX_NODE, key: UBIFS_KEY) -> UBIFS_CH:
        """
        Searches for a specific UBIFS_KEY key within the B-Tree with a given root. Will return the common header of the found node.
        :param root: The root of the B-Tree that will be searched
        :param key: Key that will be searched
        :return: Instance of UBIFS_CH if the key was found, otherwise None
        """
        pass

    def _traverse(self, node: UBIFS_IDX_NODE, traversal_function: Callable[[UBIFS_CH, int, int, ...], None], **kwargs) -> None:
        """
        Performs an inorder-traversal of the B-Tree, applying 'traversal_function' to every node (visitor-pattern).
        :param node: Starting node, e.g., root-node if the whole B-Tree should be traversed
        :param traversal_function: Visitor function that will be applied to all nodes
        :return:
        """
        # Fix because if there is only one UBIFS_BRANCH, it will not be in a List for some reason
        if isinstance(node.branches, UBIFS_BRANCH):
            node.branches = [node.branches]

        for i, branch in enumerate(node.branches):
            if i == len(node.branches) - 1:
                break
            idx_node = self._create_idx_node(branch)
            if idx_node is not None:
                self._traverse(idx_node, traversal_function, **kwargs)

            ch_hdr = UBIFS_CH(self.ubi_volume.lebs[branch.lnum].data, branch.offs) if idx_node is None else idx_node.ch
            if ch_hdr is not None:
                traversal_function(ch_hdr, branch.lnum, branch.offs, **kwargs)

        last_branch = node.branches[-1]
        idx_node = self._create_idx_node(last_branch)
        if idx_node is not None:
            self._traverse(idx_node, traversal_function, **kwargs)

    def _test_visitor(self, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, **kwargs) -> None:
        if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
            target_node = UBIFS_DENT_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
            print(f"{target_node.formatted_name()} -> {target_node.inum} ({UBIFS_INODE_TYPES(target_node.type).name})")
        # if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        #     target_node = UBIFS_INO_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
        #     print(target_node)

    def _create_idx_node(self, branch: UBIFS_BRANCH) -> UBIFS_IDX_NODE:
        """
        Creates an instance of a UBIFS_IDX_NODE from a UBIFS_BRANCH. If the target_node of the UBIFS_BRANCH is not an
        instance of a UBIFS_IDX_NODE, it will return None.
        :param branch: Instance of a UBIFS_BRANCH whose target_node will be returned as UBIFS_IDX_NODE if possible
        :return: Instance of UBIFS_IDX_NODE or None if the target_node of the UBIFS_BRANCH is not an index node.
        """
        if branch.lnum not in self.ubi_volume.lebs:
            ubiftlog.warn(f"[-] Invalid LEB num in an UBIFS_BRANCH. ({branch})")
            return None
        target_node = UBIFS_CH(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
        if not target_node.validate_magic():
            ubiftlog.warn(f"[-] Encountered an invalid node at LEB {branch.lnum} at offset {branch.offs}. (ch_hdr magic does not match)")
            return None
        if target_node.node_type == UBIFS_NODE_TYPES.UBIFS_IDX_NODE:
            target_node = UBIFS_IDX_NODE(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
            return target_node
        else:
            return None

    # DEPRECATED
    # Branches are directly parsed in ubifs_struct.py in UBIFS_IDX_NODE
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
        :return: True, if no problem occurred during validation, otherwise False
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
