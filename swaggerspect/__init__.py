import inspect
import numpydoc.docscrape
import ast
import typing

def _get_name(obj):
    if obj is None: return None
    return obj.__module__ + "." + obj.__name__

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

def get_class_api(cls):
    props = {n:v for n, v in inspect.getmembers(cls)
             if (not n.startswith('__')
                 and not inspect.ismethod(v)
                 and not inspect.isfunction(v)
                 and not inspect.isdatadescriptor(v))}
    types = {k: _get_name(t) for k, t in typing.get_type_hints(cls).items()}

    propdocs = _get_class_property_comments(cls)
    
    args = {k: (types.get(k, _get_name(type(props.get(k)))), props.get(k), propdocs.get(k))
            for k in set(props.keys()).union(types.keys())}
    
    return {
        "name": _get_name(cls),
        "description": inspect.getdoc(cls),
        "properties": args
    }

def get_function_api(fn):
    s = inspect.signature(fn)
    defaults = {k: None if v.default is inspect._empty else v.default for k, v in s.parameters.items()}
    
    types = {k: _get_name((None
                      if v.default is inspect._empty
                      else type(v.default))
                     if v.annotation is inspect._empty
                     else v.annotation) for k, v in s.parameters.items()}
    
    docs = inspect.getdoc(fn)
    docast = numpydoc.docscrape.NumpyDocString(docs)
    docargs = {p.name: "\n".join(p.desc) for p in docast["Parameters"]}
    docargtypes = {p.name: p.type for p in docast["Parameters"]}
    
    args = {k: (types.get(k) or docargtypes.get(k), defaults.get(k), docargs.get(k))
            for k in set(types.keys()).union(docargs.keys())}
    
    return {
            "name": _get_name(fn),
            "description": "\n".join(docast["Summary"] + docast["Extended Summary"]),
            "properties": args}
