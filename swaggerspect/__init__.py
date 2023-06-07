import inspect
import numpydoc.docscrape
import ast
import typing
import importlib.metadata

def _get_name(obj):
    if obj is None: return None
    return obj.__module__ + "." + obj.__name__

typemap = {
    'builtins.str': 'string',
    'builtins.int': 'integer',
    'builtins.float': 'number',
    'builtins.bool': 'boolean',
    'builtins.list': 'array',
    'builtins.tuple': 'array'
}

def make_type_schema(*typenames):
    for typename in typenames:
        if typename is inspect._empty:
            continue
        if typename is None:
            continue
        if not isinstance(typename, str):
            if not isinstance(typename, type):
                typename = type(typename)
            typename = _get_name(typename)
        return {"type": typemap.get(typename, "object"),
                "x-python-type": typename}
    return {}

def make_value_schema(*values):
    for value in values:
        if value is inspect._empty:
            continue
        if value is None:
            continue
        if isinstance(value, (int, str, dict, list, bool)):
            return {"default": value}
    return {}

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
    except (TypeError, OSError):
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
    return [{"name": n, "in": "query", "description": v} for n, v in _get_class_property_comments(cls).items()]

def get_class_api_parameters_inspect(cls):
    return [{"name": n, "in": "query", "schema": {} if v is None else merge(make_type_schema(v), make_value_schema(v))}
            for n, v in inspect.getmembers(cls)
            if (not n.startswith('__')
                and not inspect.ismethod(v)
                and not inspect.isfunction(v)
                and not inspect.isdatadescriptor(v))]
    
def get_class_api_parameters_typing(cls):
    return [{"name": k, "in": "query", "schema": make_type_schema(t)} for k, t in typing.get_type_hints(cls).items()]

def get_class_api(cls):
    args = merge(get_class_api_parameters_typing(cls),
                 merge(get_class_api_parameters_inspect(cls),
                       get_class_api_parameters_comments(cls)))
    return {
        "operationId": _get_name(cls),
        "description": inspect.getdoc(cls),
        "parameters": args,
        "responses": {"default":
                      {"description": _get_name(cls),
                       "content": {
                           "application/json": {"schema": make_type_schema(cls)}}}}}


def get_function_api_parameters_inspect(fn):
    return [remove_empty({"name": k,
                          "in": "query",
                          "schema": merge(
                              make_type_schema(v.default, v.annotation),
                              make_value_schema(v.default))})
             for k, v in inspect.signature(fn).parameters.items()]

def get_function_api_parameters_comments(fn):
    docs = inspect.getdoc(fn)
    if docs is None: return []
    docast = numpydoc.docscrape.NumpyDocString(docs)
    
    return [{"name": p.name,
             "in": "query",
             "description": "\n".join(p.desc),
             "schema": make_type_schema(p.type)}
            for p in docast["Parameters"]]
    
def get_function_api(fn):
    args = merge(get_function_api_parameters_inspect(fn),
                 get_function_api_parameters_comments(fn)) 

    docs = inspect.getdoc(fn)
    description = _get_name(fn)
    if docs is not None:
        docast = numpydoc.docscrape.NumpyDocString(docs)
        description = "\n".join(docast["Summary"] + docast["Extended Summary"])

    returntype = inspect.signature(fn).return_annotation
        
    return {
        "operationId": _get_name(fn),
        "description": description,
        "parameters": args,
        "responses": {"default":
                      {"description": _get_name(fn),
                       "content": {
                           "application/json": remove_empty({
                               "schema": make_type_schema(returntype)})}}}}

def get_api(obj):
    if type(obj) is type:
        return get_class_api(obj)
    elif inspect.isfunction(obj):
        return get_function_api(obj)
    return None

def get_apis_dict(objs):
    return {
        "openapi": '3.0.3',
        "info": {"title": "unknown",
                 "version": "1.0",
                 "description": "unknown"},
        "paths": {
            "/" + k: {"get": v}
            for k, v in
            [(k, get_api(v))
             for k, v in objs.items()]
            if v
        }}

def get_apis_entrypoints(group):
    entrypoints = importlib.metadata.entry_points()
    if group not in entrypoints: return {}
    entrypoints = entrypoints[group]
    docs = get_apis_dict({entry.name: entry.load()
                          for entry in entrypoints})
    docs["info"] = {"title": group,
                    "version": "1.0",
                    "description": group}
    return docs
    
def get_apis_module(module):
    if isinstance(module, str):
        try:
            module = importlib.import_module(module)
        except:
            return {}
    docs = get_apis_dict({name: getattr(module, name)
                         for name in dir(module)
                         if not name.startswith("__")})
    docs["info"] = {"title": module.__name__,
                    "version": "1.0",
                    "description": inspect.getdoc(module) or module.__name__}
    return docs

def get_apis(objs):
    return merge(get_apis_module(objs), get_apis_entrypoints(objs))
