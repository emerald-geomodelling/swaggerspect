import inspect
import numpydoc.docscrape
import ast
import typing

def _get_name(obj):
    if obj is None: return None
    return obj.__module__ + "." + obj.__name__

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

def _get_class_property_comments(cls):
    propdocs = {}
    for base in cls.__bases__:
        if base is not object:
            propdocs.update(_get_class_property_comments(base))
    
    try:
        src = inspect.getsource(cls)
    except TypeError:
        return propdocs
    
    body = ast.parse(src).body[0]

    for idx in range(len(body.body) - 1):
        s = body.body[idx]
        ss = body.body[idx+1]
        if isinstance(s, ast.Assign) and isinstance(ss, ast.Expr) and isinstance(ss.value, ast.Constant):
            for t in s.targets:
                propdocs[t.id] = ss.value.value

    return propdocs

def get_class_api_parameters_comments(cls):
    return [{"name": n, "summary": v} for n, v in _get_class_property_comments(cls).items()]

def get_class_api_parameters_inspect(cls):
    return [{"name": n, "schema": {} if v is None else {"default": v, "type": _get_name(type(v))}}
            for n, v in inspect.getmembers(cls)
            if (not n.startswith('__')
                and not inspect.ismethod(v)
                and not inspect.isfunction(v)
                and not inspect.isdatadescriptor(v))]
    
def get_class_api_parameters_typing(cls):
    return [{"name": k, "schema": {"type": _get_name(t)}} for k, t in typing.get_type_hints(cls).items()]

def get_class_api(cls):
    args = merge(get_class_api_parameters_typing(cls),
                 merge(get_class_api_parameters_inspect(cls),
                       get_class_api_parameters_comments(cls)))
    return {
        "operationId": _get_name(cls),
        "description": inspect.getdoc(cls),
        "parameters": args
    }


def get_function_api_parameters_inspect(fn):
    return [remove_empty({"name": k,
                          "schema": {"default": None if v.default is inspect._empty else v.default,
                                     "type": _get_name(
                                         (None
                                          if v.default is inspect._empty
                                          else type(v.default))
                                         if v.annotation is inspect._empty
                                         else v.annotation)}})
             for k, v in inspect.signature(fn).parameters.items()]

def get_function_api_parameters_comments(fn):
    docs = inspect.getdoc(fn)
    docast = numpydoc.docscrape.NumpyDocString(docs)
    
    return [{"name": p.name,
             "description": "\n".join(p.desc),
             "schema": {"type": p.type}}
            for p in docast["Parameters"]]
    
def get_function_api(fn):
    args = merge(get_function_api_parameters_inspect(fn),
                 get_function_api_parameters_comments(fn)) 

    docs = inspect.getdoc(fn)
    docast = numpydoc.docscrape.NumpyDocString(docs)
    description = "\n".join(docast["Summary"] + docast["Extended Summary"])
    
    return {
        "operationId": _get_name(fn),
        "description": description,
        "parameters": args
    }

