def merge(a, b):
    if a is None: return b
    if b is None: return a
    if type(a) is not type(b): return a
    if isinstance(a, dict):
        return {k: merge(a.get(k), b.get(k))
                for k in set(a.keys()).union(b.keys())}
    return a

def remove_empty(obj):
    if not isinstance(obj, dict): return obj
    return {k: v for
            k, v in [(k, remove_empty(v))
                     for k, v in obj.items()]
            if v != {}}

def remove_hidden(api):
    api = dict(api)
    api["properties"] = {
        key: value
        for key, value in api["properties"].items()
        if not value.get("hide", False)}
    return api
