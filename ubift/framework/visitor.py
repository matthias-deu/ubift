from ubift.framework.structs.ubifs_structs import UBIFS_CH, UBIFS_NODE_TYPES, UBIFS_DENT_NODE, UBIFS_INO_NODE, \
    UBIFS_KEY, UBIFS_DATA_NODE
from ubift.framework.ubifs import UBIFS
from ubift.logging import ubiftlog


def _dent_scan_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, peb_num: int, peb_offs: int, dents: dict[int, list[UBIFS_DENT_NODE]],
                       **kwargs) -> None:
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        block_size = ubifs.ubi_volume.ubi.partition.image.block_size
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.ubi.partition.image.data, peb_num * block_size + peb_offs)
        if dent_node.inum in dents:
            dents[dent_node.inum].append(dent_node)
        else:
            dents[dent_node.inum] = [dent_node]


def _dent_scan_leb_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int,
                           dents: dict[int, list[UBIFS_DENT_NODE]], **kwargs):
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if dent_node.inum in dents:
            dents[dent_node.inum].append(dent_node)
        else:
            dents[dent_node.inum] = [dent_node]

def _dent_xent_scan_leb_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int,
                           dents: dict[int, list[UBIFS_DENT_NODE]], xentries: dict[int, list[UBIFS_DENT_NODE]], **kwargs):
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_XENT_NODE:
        xent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        xentries.setdefault(xent_node.inum, []).append(xent_node)
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        dents.setdefault(dent_node.inum, []).append(dent_node)

def _all_collector_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, inodes: dict,
                                  dents: dict[int, list], datanodes: dict[int, list], **kwargs) -> None:
    """
    Same as "_inode_dent_collector_visitor" but also collects data nodes.
    """
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if dent_node.inum in dents:
            dents[dent_node.inum].append(dent_node)
        else:
            dents[dent_node.inum] = [dent_node]
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        inode_node = UBIFS_INO_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(inode_node.key[:8]))
        inodes[key.inode_num] = inode_node
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DATA_NODE:
        data_node = UBIFS_DATA_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(data_node.key[:8]))
        if key.inode_num in datanodes:
            datanodes[key.inode_num].append(data_node)
        else:
            datanodes[key.inode_num] = [data_node]

def _inode_dent_collector_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, inodes: dict,
                                  dents: dict[int, list],
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
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if dent_node.inum in dents:
            dents[dent_node.inum].append(dent_node)
        else:
            dents[dent_node.inum] = [dent_node]
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        inode_node = UBIFS_INO_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(inode_node.key[:8]))
        inodes[key.inode_num] = inode_node

def _inode_dent_xent_collector_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, inodes: dict,
                                  dents: dict[int, list], xentries: dict[int, list],
                                  **kwargs) -> None:
    """
    A Visitor that collects all nodes of types UBIFS_DENT_NODE, UBIFS_XENT_NODE and UBIFS_INO_NODE and stores them in the dicts 'inodes' and 'dents'
    :param ch_hdr: Will be provided by _traverse-function
    :param leb_num: Will be provided by _traverse-function
    :param leb_offs: Will be provided by _traverse-function
    :param inodes: Collected nodes of type UBIFS_INO_NODE
    :param dents: Collected nodes of type UBIFS_DENT_NODE
    :param dents: Collected nodes of type UBIFS_XENT_NODE
    :param kwargs:
    :return:
    """
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_XENT_NODE:
        xent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if xent_node.inum in xentries:
            xentries[xent_node.inum].append(xent_node)
        else:
            xentries[xent_node.inum] = [xent_node]
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if dent_node.inum in dents:
            dents[dent_node.inum].append(dent_node)
        else:
            dents[dent_node.inum] = [dent_node]
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        inode_node = UBIFS_INO_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(inode_node.key[:8]))
        inodes[key.inode_num] = inode_node

def _inode_dent_data_collector_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, inodes: dict[int, UBIFS_INO_NODE],
                                       dents: dict[int, list], data: dict[int, list], **kwargs) -> None:
    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
        dent_node = UBIFS_DENT_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        if dent_node.inum not in dents:
            dents[dent_node.inum] = [dent_node]
        else:
            dents[dent_node.inum].append(dent_node)
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
        inode_node = UBIFS_INO_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(inode_node.key[:8]))
        inodes[key.inode_num] = inode_node
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DATA_NODE:
        data_node = UBIFS_DATA_NODE(ubifs.ubi_volume.lebs[leb_num].data, leb_offs)
        key = UBIFS_KEY(bytes(data_node.key[:8]))
        if key.inode_num not in data:
            data[key.inode_num] = [data_node]
        else:
            data[key.inode_num].append(data_node)


def _test_visitor(ubifs: UBIFS, ch_hdr: UBIFS_CH, leb_num: int, leb_offs: int, **kwargs) -> None:
    if not ch_hdr.validate_magic():
        return

    if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_CS_NODE:
        print(f"cs node at {leb_num} {leb_offs}")
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_REF_NODE:
        print(f"ref node at {leb_num} {leb_offs}")
    elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_TRUN_NODE:
        print(f"truncation node at {leb_num} {leb_offs}")

    # if ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_INO_NODE:
    #     target_node = UBIFS_INO_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
    #     inum = UBIFS_KEY(bytes(target_node.key)[:8]).inode_num
    #     if inum <= 0:
    #         print("ja")
    #
    # elif ch_hdr.node_type == UBIFS_NODE_TYPES.UBIFS_DENT_NODE:
    #     target_node = UBIFS_DENT_NODE(self.ubi_volume.lebs[leb_num].data, leb_offs)
    #     if target_node.inum <= 0:
    #         print(f"ja dent ({target_node.formatted_name()})")
