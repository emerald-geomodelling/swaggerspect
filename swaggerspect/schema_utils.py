def _merge_list(a, b):
    akeys = [p["name"] for p in a]
    bkeys = [p["name"] for p in b]
    params = merge({p["name"]: p for p in a}, {p["name"]: p for p in b})
    
    return ([params[key] for key in akeys]
            + [params[key] for key in bkeys if key not in akeys])

def merge(a, b):
    if a is None: return b
    if b is None: return a
    if type(a) is not type(b): return a
    if isinstance(a, dict):
        return {k: merge(a.get(k), b.get(k))
                for k in set(a.keys()).union(b.keys())}
    if isinstance(a, list):
        if (a and "name" in a[0]) or (b and "name" in b[0]):
            return _merge_list(a, b)
    return a

def remove_empty(obj):
    if not isinstance(obj, dict): return obj
    return {k: v for
            k, v in [(k, remove_empty(v))
                     for k, v in obj.items()]
            if v}

def remove_hidden(api):
    return [param for param in api
            if not param.get("schema", {}).get("hide", False)]
