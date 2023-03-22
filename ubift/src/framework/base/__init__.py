from typing import List

from ubift.src.logging import ubiftlog

def find_signatures(data: bytes, signature: bytes) -> List[int]:
    """
    Scans arbitrary binary data for a specific signature.
    :param data:
    :param signature:
    :return: Returns all found hits
    """
    all_hits = []
    ubiftlog.debug(f"[!] Scanning for Signature {signature}")

    hit = data.find(signature, 0)

    while hit >= 0:
        all_hits.append(hit)
        ubiftlog.debug(f"[+] Found Signature {signature} at offset {hit}")
        hit = data.find(signature, hit + 1)

    return all_hits

def find_signature(data: bytes, signature: bytes, offset: int = 0) -> int:
    """
    Scans arbitrary binary data for a specific signature.
    :param data:
    :param signature:
    :return: Returns first hit or -1 if not found
    """
    hit = data.find(signature, offset)
    if hit >= 0:
        ubiftlog.debug(f"[+] Found Signature {signature} at offset {hit}")
    return hit