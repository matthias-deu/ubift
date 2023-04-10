import struct
import uuid
from typing import List, Callable, Any

import lzo

from ubift import exception
from ubift.framework import compression
from ubift.framework.structs.ubifs_structs import UBIFS_SB_NODE, UBIFS_MST_NODE, UBIFS_NODE_TYPES, UBIFS_CH, \
    UBIFS_IDX_NODE, UBIFS_BRANCH, UBIFS_KEY, UBIFS_DENT_NODE, UBIFS_INO_NODE, UBIFS_INODE_TYPES, \
    UBIFS_PAD_NODE, UBIFS_CS_NODE, UBIFS_REF_NODE, parse_arbitrary_node, UBIFS_KEY_TYPES, UBIFS_DATA_NODE
from ubift.framework.ubi import UBIVolume, LEB
from ubift.framework.util import crc32, find_signature
from ubift.logging import ubiftlog

# From which LEB is the master node taken (0 refers to LEB 1, 1 to LEB 2)
UBIFS_MASTERNODE_INDEX = 0
# Size of a key in KiB
UBIFS_KEY_SIZE = 8


class UBIFS:
    """
    Represents an UBIFS instance which resides within an UBI volume.

    LEB 0 -> Superblock node
    LEB 1 and 2 -> Master node (two identical copies)
    """

    def __init__(self, ubi_volume: UBIVolume, masternode_index: int = -1):
        self._ubi_volume = ubi_volume

        self.superblock = UBIFS_SB_NODE(self.ubi_volume.lebs[0].data, 0)
        self.masternodes = [self._parse_master_nodes(1),
                            self._parse_master_nodes(2)]

        if masternode_index is None or masternode_index < 0:
            masternode_index = 0
        if masternode_index >= len(self.masternodes[0]):
            raise exception.UBIFTException(f"[-] Invalid master node index ({masternode_index}). There are only {len(self.masternodes[0])} master nodes in UBIFS instance for UBI volume {self._ubi_volume}")

        self._used_masternode = self.masternodes[0][masternode_index]
        self._root_idx_node = self._parse_root_idx_node(self._used_masternode)

        if not self._validate():
            raise exception.UBIFTException(f"[-] Invalid UBIFS instance for UBI volume {self._ubi_volume}")

        ubiftlog.info(f"[!] Initialized UBIFS instance for UBI volume {self._ubi_volume}")

        # self._parse_journal(self.masternodes[UBIFS_MASTERNODE_INDEX])

        # self._traverse(self._root_idx_node, self._test_visitor)

        # print(dents[239].formatted_name())
        # print(self._unroll_path(dents[239], dents, inodes))
        # for dent in dents.values():
        #    print(dent.inum)

        # key = UBIFS_KEY.create_key(363, 2, key_r5_hash("0914_2023-03-01T114645+0100_6EE37D_000C.pud"))
        # node = self._find(self._root_idx_node, key)
        # print(node.formatted_name())

        # key = UBIFS_KEY.create_key(255, UBIFS_KEY_TYPES.UBIFS_INO_KEY)
        # print(bytearray(key.pack()).hex(sep=","))

        # node = self._find(self._root_idx_node, key)
        # print(bytearray(node.key).hex(sep=","))
        # print(node)

    def _parse_master_nodes(self, leb_num: LEB) -> List[UBIFS_MST_NODE]:
        """
        Parses all nodes of type UBIFS_MST_NODE in a LEB. This is needed because new master nodes are successivly written, i.e., the newest is at the end.
        :param leb_num:
        :return: List of all found master nodes in a given LEB, sorted by sequence number (highest number first)
        """
        mst_nodes = []
        leb_data = self.ubi_volume.lebs[leb_num].data
        ch_hdr_sig = "\x31\x18\x10\x06".encode("utf-8")

        index = find_signature(leb_data, ch_hdr_sig, 0)
        while 0 <= index:
            try:
                ch_hdr = UBIFS_CH(leb_data, index)
                if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_MST_NODE:
                    mst_nodes.append(UBIFS_MST_NODE(leb_data, index))
            except:
                ubiftlog.warn(f"[-] Encountered error while parsing master node in LEB {leb_num}.")

            index = find_signature(leb_data, ch_hdr_sig, index + 1)

        # sort them based on sequence number
        mst_nodes.sort(key=lambda mst_node: mst_node.ch.sqnum, reverse=True)

        ubiftlog.info(f"[+] Found {len(mst_nodes)} master nodes in LEB {leb_num}.")

        return mst_nodes

    def _scan(self, traversal_function: Callable[[UBIFS_CH, int, int, ...], None], **kwargs) -> None:
        """
        Scans the UBI instance for UBIFS_CH signatures. This will naturally find a lot more than using _traverse, for instance nodes that are obsolete.
        :param traversal_function: Function that will be called for every found signature
        :param kwargs:
        :return:
        """
        ubi = self._ubi_volume.ubi
        partition = self._ubi_volume.ubi.partition
        if len(ubi.volumes) > 1:
            # TODO: maybe this is not true because they have not been erased, so compare their vid_hdr with ubi volume index
            ubiftlog.warn(
                "[-] The UBI instance has more than one volume, therefore it wont be clear to which volume the parsed nodes belong to. LEB information cannot be used because it cannot be assured that a vid header is written to the LEB (only EC).")

        start_offset = ubi.partition.offset
        stop_offset = ubi.partition.end
        index = find_signature(partition.image.data, "\x31\x18\x10\x06".encode("utf-8"),
                               start_offset)  # TODO: __magic__ is BIG_ENDIAN but UBIFS_CH are LITTLE_ENDIAN
        while 0 <= index < stop_offset:
            try:
                ch_hdr = UBIFS_CH(partition.image.data, index)
                peb = index // partition.image.block_size
                peb_offset = index - (peb * partition.image.block_size)
                traversal_function(ch_hdr, peb, peb_offset,
                                   **kwargs)  # Traversal function is called with PEB num and offset
            except:
                ubiftlog.warn(f"[-] Possibly invalid UBIFS_CH at PEB {peb} offset {peb_offset}.")

            index = find_signature(partition.image.data, "\x31\x18\x10\x06".encode("utf-8"), index + 1)

    def _dent_scan_visitor(self, ch_hdr: UBIFS_CH, peb_num: int, peb_offs: int, dents: List[UBIFS_DENT_NODE],
                           **kwargs) -> None:
        if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
            block_size = self.ubi_volume.ubi.partition.image.block_size
            dent_node = UBIFS_DENT_NODE(self.ubi_volume.ubi.partition.image.data, peb_num * block_size + peb_offs)
            dents.append(dent_node)

    def _unroll_path(self, dent: UBIFS_DENT_NODE, dents: dict[int, UBIFS_DENT_NODE]) -> str:
        """
        Fetches the complete path of an UBIFS_DENT_NODE up to the root.
        UBIFS_DENT_NODE have 2 inode numbers, one (inside the key[] has the inode number of the parent] and dent.inum is its own inode number)
        Unroll will fetch the UBIFS_DENT_NODE of the parent recursivly until the dent.inum==0(root-directory) has been reached.
        :param dent: The directory  ntry that will have its path unrolled up to the root
        :param dents: All available directory entry nodes
        :return:
        """
        # The parent-inode of the directory entry is saved in the first 32-Bits of its key
        key = UBIFS_KEY(bytes(dent.key[:8]))
        parent_inum = key.inode_num

        cur = dent.formatted_name()
        # Root reached?
        if parent_inum == 0:
            return cur
        # Otherwise go up the hierarchy recursivly
        else:
            if parent_inum in dents:
                return self._unroll_path(dents[parent_inum], dents) + "/" + cur
            else:
                return cur

    def _parse_journal(self, masternode: UBIFS_MST_NODE):
        # WiP
        print(masternode)
        log_lnum = masternode.log_lnum
        cur_offs = 0

        for log_lnum in range(0, 150):
            try:
                index = find_signature(self.ubi_volume.lebs[log_lnum].data, "\x31\x18\x10\x06".encode("utf-8"))
                while index >= 0:
                    index = find_signature(self.ubi_volume.lebs[log_lnum].data, "\x31\x18\x10\x06".encode("utf-8"),
                                           index + 1)
                    if UBIFS_CH(self.ubi_volume.lebs[log_lnum].data,
                                index).node_type == UBIFS_NODE_TYPES.UBIFS_REF_NODE:
                        print("ref at :" + str(index))
            except:
                pass
        exit()

        ch_hdr = UBIFS_CH(self.ubi_volume.lebs[log_lnum].data, cur_offs)
        print(ch_hdr)
        while ch_hdr.validate_magic():
            if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_PAD_NODE:
                pad_node = UBIFS_PAD_NODE(self.ubi_volume.lebs[log_lnum].data, cur_offs)
                cur_offs += UBIFS_PAD_NODE.size + pad_node.pad_len
            elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_CS_NODE:
                cur_offs += UBIFS_CS_NODE.size
            elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_REF_NODE:
                ref_node = UBIFS_REF_NODE(self.ubi_volume.lebs[log_lnum].data, cur_offs)
                print(ref_node)
                cur_offs += UBIFS_REF_NODE.size
            else:
                print(f"Unknown node type {ch_hdr.node_type}")
                cur_offs += UBIFS_CH.size

            ch_hdr = UBIFS_CH(self.ubi_volume.lebs[log_lnum].data, cur_offs)
            # print(ch_hdr)

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

    def _find_range(self, node: Any, min_key: UBIFS_KEY, max_key: UBIFS_KEY, _result: List[Any] = []) -> List[Any]:
        """
        Searches for nodes that have a key of min_key <= key < max_key
        :param node:
        :param min_key:
        :param max_key:
        :param _result: Private list that is passed to recursive calls
        :return:
        """
        # Fix because if there is only one UBIFS_BRANCH, it will not be in a List for some reason
        if isinstance(node.branches, UBIFS_BRANCH):
            node.branches = [node.branches]

        if _result is None:
            _result = []

        # At level 0, select all leafs that are within [min, max)
        if node.level == 0:
            for i, branch in enumerate(node.branches):
                if min_key <= branch.python_key() < max_key:
                    target_node = parse_arbitrary_node(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
                    if target_node is not None:
                        _result.append(target_node)
            return _result

        # Select all branches that are within [min, max)
        start_index = None
        end_index = None
        for i, branch in enumerate(node.branches):
            branch_key = branch.python_key()
            if branch_key > min_key and start_index is None:
                if i == 0:
                    start_index = 0
                else:
                    start_index = i - 1
            elif branch_key > max_key and end_index is None:
                if i == len(node.branches) - 1:
                    end_index = len(node.branches) - 1
                    if start_index is None:
                        start_index = end_index
                    break
                else:
                    end_index = i - 1
                    if start_index is None:
                        start_index = end_index
                    break
            if end_index is None and i == len(node.branches) - 1:
                end_index = len(node.branches) - 1
                if start_index is None:
                    start_index = end_index
                break

        # Recursivly call this function for all selected branches
        for i in range(start_index, end_index + 1):
            branch = node.branches[i]
            target_node = parse_arbitrary_node(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
            if isinstance(target_node, UBIFS_IDX_NODE):
                _result += self._find_range(target_node, min_key, max_key, [])
            else:
                ubiftlog.error("[-] Encountering non-index node while traversing B-Tree.")

        return _result

    def _find(self, node: Any, key: UBIFS_KEY) -> Any:
        """
        Searches for a specific UBIFS_KEY key within the B-Tree with a given root.
        :param node: Current node that will be searched
        :param key: Key that will be searched
        :return: Node if the key was found, otherwise None
        """
        # Fix because if there is only one UBIFS_BRANCH, it will not be in a List for some reason
        if isinstance(node.branches, UBIFS_BRANCH):
            node.branches = [node.branches]

        sel_branch = None
        for i, branch in enumerate(node.branches):
            branch_key = branch.python_key()
            if key < branch_key:
                if i == 0:
                    sel_branch = branch
                    break
                else:
                    sel_branch = node.branches[i - 1]
                    break
            elif key == branch_key:
                if node.level == 0:
                    return parse_arbitrary_node(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
                else:
                    sel_branch = branch
        # Greater than last branch, so use last branch.
        if sel_branch is None:
            sel_branch = node.branches[-1]

        target_node = parse_arbitrary_node(self.ubi_volume.lebs[sel_branch.lnum].data, sel_branch.offs)
        if isinstance(target_node, UBIFS_IDX_NODE):
            return self._find(target_node, key)

    def _traverse(self, node: UBIFS_IDX_NODE, traversal_function: Callable[[UBIFS_CH, int, int, ...], None],
                  **kwargs) -> None:
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

    def _inode_dent_collector_visitor(self, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, inodes: dict, dents: dict,
                                      **kwargs) -> None:
        """
        A Visitor that collects all nodes of types UBIFS_DENT_NODE and UBIFS_INO_NODE and stores them in the dicts 'inodes' and 'dents'
        :param ch_hdr: Will be provided by _traverse-function
        :param leb_num: Will be provided by _traverse-function
        :param leb_offs: Will be provided by _traverse-function
        :param inodes: Collected nodes of type UBIFS_INO_NODE
        :param dents: Collected nodes of type UBIFS_DENT_NODE
        :param kwargs:
        :return:
        """
        if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
            dent_node = UBIFS_DENT_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
            dents[dent_node.inum] = dent_node
        elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
            inode_node = UBIFS_INO_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
            key = UBIFS_KEY(bytes(inode_node.key[:8]))
            inodes[key.inode_num] = inode_node

    def _test_visitor(self, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, list=[], **kwargs) -> None:
        if not ch_hdr.validate_magic():
            return

        if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DATA_NODE:
            target_node = UBIFS_DATA_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
            key = UBIFS_KEY(bytes(target_node.key[:8]))
            if key.inode_num == 2864:
                list.append(target_node)
        # if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        #     target_node = UBIFS_INO_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
        #     print(f"{UBIFS_KEY(bytes(target_node.key)[:8])} -> {target_node.key}")
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
            ubiftlog.warn(
                f"[!] Encountered an invalid node at LEB {branch.lnum} at offset {branch.offs}. (ch_hdr magic does not match)")
            return None
        if target_node.node_type == UBIFS_NODE_TYPES.UBIFS_IDX_NODE:
            target_node = UBIFS_IDX_NODE(self.ubi_volume.lebs[branch.lnum].data, branch.offs)
            return target_node
        else:
            return None

    # DEPRECATED
    # Branches are directly parsed in ubifs_struct.py in UBIFS_IDX_NODE
    # def _parse_branches(self, branch_cnt: int, leb: LEB, offset: int) -> List[UBIFS_BRANCH]:
    #     """
    #     This function parses and creates UBIFS_BRANCH instances that are a flexible member of a UBIFS_IDX_NODE.
    #     :param branch_cnt: How many braches there are. This is defined in an instance of UBIFS_IDX_NODE.child_cnt
    #     :param leb: LEB that contains the UBIFS_IDX_NODE
    #     :param offset: Offset where the branches start
    #     :return: List of UBIFS_BRANCH instances
    #     """
    #     branches: List[UBIFS_BRANCH] = []
    #     cur = offset
    #     for off in range(branch_cnt):
    #         branch = UBIFS_BRANCH(leb.data, cur)
    #         cur += UBIFS_BRANCH.size
    #
    #         branch.key = leb.data[cur:cur + UBIFS_KEY_SIZE]
    #         cur += UBIFS_KEY_SIZE
    #
    #         branches.append(branch)
    #
    #     return branches

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
            ubiftlog.warn("[-] There is only one list with master nodes, so one LEB could not be parsed correctly.")
        elif len(self.masternodes) == 2:
            # Add an additional 8 to their offsets to skip the '__le64 sqnum', because both masternodes have different sequence numbers.
            if crc32(self.masternodes[0][0].pack()[8 + 8:]) != crc32(self.masternodes[1][0].pack()[8 + 8:]):
                ubiftlog.warn(
                    "[-] Most recent master nodes have different CRC32, this should never happen under normal circumstances. It might be possible that one master node is corrupted.")

        if self._used_masternode.ch.crc != crc32(self._used_masternode.pack()[8:]):
            ubiftlog.warn("[-] Most recent master node has invalid CRC32.")

        return True

    @property
    def ubi_volume(self) -> UBIVolume:
        return self._ubi_volume
