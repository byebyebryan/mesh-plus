"""Private prototype for two owned Mesh JSON copies; no validation is removed."""

import copy


def owned_copy(value):
    active, checked = set(), set()

    def plain(item):
        kind = type(item)
        if kind not in (dict, list):
            return kind in (str, int, float, bool, type(None))
        identity = id(item)
        if identity in active:
            return False
        if identity in checked:
            return True
        active.add(identity)
        if kind is dict:
            valid = all(type(key) is str and plain(child) for key, child in item.items())
        else:
            valid = all(plain(child) for child in item)
        active.remove(identity)
        checked.add(identity)
        return valid

    try:
        # Reader.compose copies its internal (host metadata, rows) pair.
        pair = type(value) is tuple and len(value) == 2 and type(value[0]) is dict and type(value[1]) is list
        supported = all(plain(item) for item in value) if pair else plain(value)
    except RecursionError:
        supported = False
    if not supported:
        return copy.deepcopy(value)
    memo = {}

    def clone(item):
        kind = type(item)
        if kind not in (dict, list):
            return item
        identity = id(item)
        if identity in memo:
            return memo[identity]
        result = {} if kind is dict else []
        memo[identity] = result
        if kind is dict:
            result.update((key, clone(child)) for key, child in item.items())
        else:
            result.extend(clone(child) for child in item)
        return result
    return tuple(clone(item) for item in value) if pair else clone(value)
