# NOTE!
# This code is based on the implementation from the Linux kernel at /linux/fs/ubifs/key.h

def key_r5_hash(path: str) -> int:
    """
    r5 hashing function.
    The code is based on the implementation from the Linux kernel at /linux/fs/ubifs/key.h
    The original function's signature is 'static inline uint32_t key_r5_hash(const char *s, int len)'

    In keys of type UBIFS_DENT_KEY, the path hash is saved in the last 29-Bits of the key, therefore
    this function returns only the last 29-Bits of the r5 hash.

    :param path: Path that will be hashed
    :return: 29-Bits hash value of the path name
    """
    hash = 0
    for letter in path:
        char_val = ord(letter)
        hash += char_val << 4
        hash += char_val >> 4
        # original type in linux code is uint32_t, so cut everything else away after operations that change size
        hash &= 0xFFFFFFFF
        hash *= 11
        hash &= 0xFFFFFFFF

    # Values %0 and %1 are reserved for "." and "..", %2 is reserved for "end of readdir" marker
    # See key_mask_hash(uint32_t hash) in /linux/fs/ubifs/key.h
    if hash <= 2:
        hash += 3

    # Only 29-Bits are used for the hash value in the key
    return hash & 0x1FFFFFFF
