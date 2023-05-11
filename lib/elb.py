from util import md5

PRIORITY_CACHE = []


def _priority_hash_fn(s: str) -> int:
    pass


def _priority_hash(s: str, range_start: int = 1000, range_end: int = 47999) -> int:
    ret = int(md5(s), 16) % (range_end - range_start) + range_start
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def host_only_priority_hash(s: str) -> int:
    return _priority_hash(s, 48000, 48999)


def host_path_priority_hash(s: str) -> int:
    return _priority_hash(s, 1000, 47999)
