import inspect
import numpydoc.docscrape
import ast
import typing
import types
import importlib.metadata
import copy

def _get_name(obj):
    if obj is None: return None
    if obj is typing.Any: return 'typing.Any'
    return obj.__module__ + "." + obj.__name__

typemap = {
    'builtins.str': {'type':'string'},
    'builtins.int': {'type':'integer'},
    'builtins.float': {'type':'number'},
    'builtins.bool': {'type':'boolean'},
    'builtins.list': {'type':'array'},
    'builtins.dict': {'type':'object'},
    'typing.Any': {},
    'tuple': {'type':'array'},
    'str': {'type':'string'},
    'int': {'type':'integer'},
    'float': {'type':'number'},
    'bool': {'type':'boolean'},
    'list': {'type':'array'},
    'tuple': {'type':'array'},
    'dict': {'type':'object'},
    'pydantic_core._pydantic_core.Url': {"type": "string", "format": "url"}
}

def typeof(v):
    if v is None: return None
    if v is inspect._empty: return None
    return type(v)

def make_type_schema(*typenames, hasdefault=None):
    for typename in typenames:
        if typename is inspect._empty:
            continue
        if typename is None:
            continue

        orig = repr(typename)
        schema = {}
        args = None
        metadatas = None
        if not isinstance(typename, str):
            if isinstance(typename, typing._AnnotatedAlias):
                metadatas = typename.__metadata__
                typename = typename.__args__[0]
            if isinstance(typename, typing._LiteralGenericAlias):
                schema["enum"] = list(typing.get_args(typename))
                typename = _get_name(type(schema["enum"][0]))
            else:
                if hasattr(typename, "json_schema"):
                    metadatas = [typename]
                args = typing.get_args(typename)
                typename = _get_name(typename)

        pytypename = typename
        schema.update(typemap.get(typename))

        if schema.get("type", None) is None:
            schema["type"] = "object"
            if typeof(hasdefault) is not None:
                schema["hide"] = True
        
        schema["x-python-type"] = pytypename
        #schema["x-python-orig"] = orig
        if schema["type"] == "array" and args:
            schema["items"] = make_type_schema(args[0])
        elif schema["type"] == "object" and args:
            schema["propertyNames"] = make_type_schema(args[0])
            schema["patternProperties"] = make_type_schema(args[1])

        if metadatas:
            for metadata in metadatas:
                if isinstance(metadata, dict):
                    schema.update({key[len("swaggerspect_"):]: value
                                   for key, value in metadata.items()
                                   if key.startswith("swaggerspect_")})
                    if "json_schema" in metadata:
                        schema.update(metadata["json_schema"])
                else:
                    schema.update({key[len("swaggerspect_"):]: getattr(metadata, key)
                                   for key in dir(metadata)
                                   if key.startswith("swaggerspect_")})
                    if hasattr(metadata, "json_schema"):
                        schema.update(metadata.json_schema)
        return schema
    return {}

def make_value_schema(*values):
    for value in values:
        if value is inspect._empty:
            continue
        if value is None:
            continue
        if isinstance(value, (int, str, float, dict, list, bool)):
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
    return [{"name": n, "in": "query", "schema": {} if v is None else merge(make_type_schema(typeof(v), hasdefault=v), make_value_schema(v))}
            for n, v in inspect.getmembers(cls)
            if (not n.startswith('__')
                and not inspect.ismethod(v)
                and not inspect.isfunction(v)
                and not inspect.isdatadescriptor(v))]
    
def get_class_api_parameters_typing(cls):
    return [{"name": k, "in": "query", "schema": make_type_schema(t)} for k, t in typing.get_type_hints(cls).items()]

def get_class_api(cls):
    api = getattr(cls, "api_type", "properties")
    if api == "properties":
        return get_class_properties_api(cls)
    else:
        return get_api(cls.__init__)
    
def get_class_properties_api(cls):
    args = remove_hidden(
        merge(get_class_api_parameters_typing(cls),
              merge(get_class_api_parameters_inspect(cls),
                    get_class_api_parameters_comments(cls))))
    return {
        "operationId": _get_name(cls),
        "description": inspect.getdoc(cls),
        "parameters": args,
        "responses": {"default":
                      {"description": _get_name(cls),
                       "content": {
                           "application/json": {"schema": make_type_schema(cls)}}}}}

def remove_hidden(api):
    return [param for param in api
            if not param.get("schema", {}).get("hide", False)]
    
def get_function_api_parameters_inspect(fn):
    return [remove_empty({"name": k,
                          "in": "query",
                          "schema": merge(
                              make_type_schema(v.annotation, typeof(v.default), hasdefault=v.default),
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
    
def get_function_api(fn, name = None):
    args = remove_hidden(
        merge(get_function_api_parameters_inspect(fn),
              get_function_api_parameters_comments(fn)))

    docs = inspect.getdoc(fn)
    description = _get_name(fn)
    if docs is not None:
        docast = numpydoc.docscrape.NumpyDocString(docs)
        description = "\n".join(docast["Summary"] + docast["Extended Summary"])

    returntype = inspect.signature(fn).return_annotation
        
    return {
        "operationId": name or _get_name(fn),
        "description": description,
        "parameters": args,
        "responses": {"default":
                      {"description": name or _get_name(fn),
                       "content": {
                           "application/json": remove_empty({
                               "schema": make_type_schema(returntype)})}}}}

def get_api(obj, name = None):
    """Generate a swagger specification fragment for a single function
    call or class instantiation."""
    if type(obj) is type:
        return get_class_api(obj)
    elif inspect.isfunction(obj):
        return get_function_api(obj, name=name)
    return None

def get_apis_dict(objs, local_names = False):
    return {
        "openapi": '3.0.3',
        "info": {"title": "unknown",
                 "version": "1.0",
                 "description": "unknown"},
        "paths": {
            "/" + k: {"get": v}
            for k, v in
            [(k, get_api(v, name = k if local_names else None))
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
    if not isinstance(module, types.ModuleType):
        return {}
    docs = get_apis_dict({name: getattr(module, name)
                         for name in dir(module)
                         if not name.startswith("__")})
    docs["info"] = {"title": module.__name__,
                    "version": "1.0",
                    "description": inspect.getdoc(module) or module.__name__}
    return docs

def get_apis_class(cls):
    if isinstance(cls, str):
        try:
            module, name = cls.rsplit(".", 1)
            cls = getattr(importlib.import_module(module), name)
        except:
            return {}
    if not isinstance(cls, type):
        return {}
    docs = get_apis_dict({name: getattr(cls, name)
                          for name in dir(cls)
                          if not name.startswith("__")},
                         local_names=True)
    docs["info"] = {"title": _get_name(cls),
                    "version": "1.0",
                    "description": inspect.getdoc(cls) or cls.__name__}
    return docs

def _group_parameters(parameters):
    grouped = []
    grouped_by_name = {}
    for param in parameters:
        if "__" not in param["name"]:
            grouped.append(param)
            grouped_by_name[param["name"]] = param
        else:
            param = dict(param)
            path = param["name"].split("__")
            if path[0] not in grouped_by_name:
                grouped_by_name[path[0]] = {
                    "in": param["in"],
                    "name": path[0],
                    "schema": {
                        "type": "object",
                        "properties": {},
                        "x-python-type": None
                    }
                }
                grouped.append(grouped_by_name[path[0]])
            
            g = grouped_by_name[path[0]]["schema"]
            for item in path[1:-1]:
                if item not in g["properties"]:
                    g["properties"][item] = {
                        "type": "object",
                        "properties": {},
                        "x-python-type": None
                    }
                g = g["properties"][item]
            
            g["properties"][path[-1]] = param["schema"]
    return grouped

def group_apis_parameters(apis):
    apis = copy.deepcopy(apis)
    for path, methods in apis["paths"].items():
        for method, api in methods.items():
            api["parameters"] = _group_parameters(api["parameters"])
    return apis


def get_apis(objs, group_parameters = False):
    """Generates a swagger specification for module or entry point group.
    If group_parameters is True, then parameter names are treated as
    "__" separated paths in a tree of dictionaries.
    """
    res = merge(merge(get_apis_module(objs), get_apis_entrypoints(objs)), get_apis_class(objs))
    if merge:
        res = group_apis_parameters(res)
    return res
    
def swagger_to_json_schema(api, multi = True):
    """Converts a swagger specification into a JSON schema for either
    a single function call serialized as

    {"function.name": {"argname1": "value1", ... "argnameN": "valueN"}}

    or if multi is True (the default), a list of function calls each
    serialized as above.
    """
    if not api: return {}
    schema = {
        "anyOf": [
            {
                "type": "object",
                "title": step["operationId"].split(".")[-1],
                "required": [step["operationId"]],
                "additionalProperties": False,
                "properties": {
                    step["operationId"]: {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            parameter["name"]: merge(
                                parameter.get("schema", {}),
                                remove_empty({"description": parameter.get("description"),
                                              "default": parameter.get("default")
                                }))
                            for parameter in step["parameters"]
                        }
                    }
                }
            }
            for step in [path["get"] for path in api["paths"].values()]
        ]
    }
    if multi:
        schema = {"type": "array", "items": schema}
    schema["description"] = api["info"]["description"]
    return schema

class JsonSchema(object):
    """Type annotation that accepts any type (like typing.Any), but
    outputs the supplied JSON Schema in swaggerspect.
    """    
    def __new__(cls, schema):
        self = object.__new__(cls)
        self.json_schema = schema
        return typing.Annotated[typing.Any, self]
