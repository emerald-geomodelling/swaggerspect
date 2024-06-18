import inspect
import numpydoc.docscrape
import ast
import typing
import types
import importlib.metadata
import copy
import sys
from . import type_schema
from . import value_schema
from . import schema_utils
from . import class_api
from . import function_api

def get_api(obj, name = None):
    """Generate a swagger specification fragment for a single function
    call or class instantiation."""
    if type(obj) is type:
        return class_api.get_class_api(obj, name=name)
    elif inspect.isfunction(obj):
        return function_api.get_function_api(obj, name=name)
    return None

def get_apis_dict(objs, local_names = False):
    return {
        "anyOf": [v
                  for v in [get_api(v, name = k if local_names else None)
                            for k, v in objs.items()]
                  if v]}

def get_apis_entrypoints(group):
    entrypoints = importlib.metadata.entry_points()
    if group not in entrypoints: return {}
    entrypoints = entrypoints[group]
    docs = get_apis_dict({entry.name: entry.load()
                          for entry in entrypoints}, local_names=True)
    docs["title"] = group
    docs["description"] = group
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
    docs["title"] = module.__name__
    docs["description"] = inspect.getdoc(module) or module.__name__
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
    docs["title"] = type_schema.get_type_name(cls)
    docs["description"] = inspect.getdoc(cls) or cls.__name__
    return docs

def _group_parameters(parameters):
    grouped_by_name = {}
    for name, schema in parameters.items():
        if "__" not in name:
            grouped_by_name[name] = schema
        else:
            schema = dict(schema)
            path = name.split("__")
            if path[0] not in grouped_by_name:
                grouped_by_name[path[0]] = {
                    "type": "object",
                    "title": path[0],
                    "description": path[0],
                    "properties": {},
                    "x-python-type": None
                }
            
            g = grouped_by_name[path[0]]
            for item in path[1:-1]:
                if item not in g["properties"]:
                    g["properties"][item] = {
                        "type": "object",
                        "title": item,
                        "description": item,
                        "properties": {},
                        "x-python-type": None
                    }
                g = g["properties"][item]

            p = dict(schema)
            if "title" not in p: p["title"] = path[-1]
            g["properties"][path[-1]] = p
    return grouped_by_name

def group_apis_parameters(apis):
    apis = copy.deepcopy(apis)
    for api in apis["anyOf"]:
        method = next(iter(api["properties"].values()))
        method["properties"] = _group_parameters(method["properties"])
    return apis

def get_apis(objs, group_parameters = True, multi=False):
    """Generates a swagger specification for module or entry point group.
    If group_parameters is True, then parameter names are treated as
    "__" separated paths in a tree of dictionaries.
    """
    res = schema_utils.merge(schema_utils.merge(get_apis_module(objs), get_apis_entrypoints(objs)), get_apis_class(objs))
    if group_parameters:
        res = group_apis_parameters(res)
    if multi:
        res = {"type": "array",
               "title": res["title"],
               "description": res["description"],
               "items": res}
    return res
    
def swagger_to_json_schema(api, multi = True):
    warnings.warn("swagger_to_json_schema is deprecated; apis are now json_schemas by default", DeprecationWarning)
    if "items" in api:
        if multi:
            return api
        return api["items"]
    else:
        if multi:
            return {"type": "array",
                    "title": api["title"],
                    "description": api["description"],
                    "items": api}
        return api

def _json_schema_to_swagger_parameter(name, schema):
    return {
        "in": "query",
        "name": name,
        "description": schema.get("description", name) if isinstance(schema, dict) else name,
        "schema": schema
    }
        
def _json_schema_to_swagger_endpoint(schema):
    operation_id, params = next(iter(schema["properties"].items()))
    return {
        "/" + operation_id: {
            "get": {
                "description": schema["description"],
                "operationId": operation_id,
                "parameters": [_json_schema_to_swagger_parameter(name, schema)
                               for name, schema in params["properties"].items()]
            }
        }
    }

def json_schema_to_swagger(api):
    if "items" in api: api = api["items"]
    return {
        "info": {
            "description": api["description"],
            "title": api["title"],
            "version": '1.0'
        },
        "openapi": "3.0.3",
        "paths": [_json_schema_to_swagger_endpoint(schema)
                  for schema in api["anyOf"]]
    }

class JsonSchema(object):
    """Type annotation that accepts any type (like typing.Any), but
    outputs the supplied JSON Schema in swaggerspect.
    """    
    def __new__(cls, schema):
        self = object.__new__(cls)
        self.json_schema = schema
        return typing.Annotated[typing.Any, self]
