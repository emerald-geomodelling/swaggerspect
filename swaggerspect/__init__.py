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
        return class_api.get_class_api(obj)
    elif inspect.isfunction(obj):
        return function_api.get_function_api(obj, name=name)
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
    for path, api in docs["paths"].items():
        api["get"]["operationId"] = path[1:] # Remove the /
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
    docs["info"] = {"title": type_schema.get_type_name(cls),
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
                        "title": path[0],
                        "description": path[0],
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
                        "title": item,
                        "description": item,
                        "properties": {},
                        "x-python-type": None
                    }
                g = g["properties"][item]

            p = dict(param["schema"])
            if "description" in param: p["description"] = param["description"]
            if "title" not in p: p["title"] = path[-1]
            g["properties"][path[-1]] = p
    return grouped

def group_apis_parameters(apis):
    apis = copy.deepcopy(apis)
    for path, methods in apis["paths"].items():
        for method, api in methods.items():
            api["parameters"] = _group_parameters(api["parameters"])
    return apis


def get_apis(objs, group_parameters = True):
    """Generates a swagger specification for module or entry point group.
    If group_parameters is True, then parameter names are treated as
    "__" separated paths in a tree of dictionaries.
    """
    res = schema_utils.merge(schema_utils.merge(get_apis_module(objs), get_apis_entrypoints(objs)), get_apis_class(objs))
    if group_parameters:
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
            schema_utils.remove_empty(
                {
                    "type": "object",
                    "title": step["operationId"].split(".")[-1],
                    "description": step.get("description"),
                    "required": [step["operationId"]],
                    "additionalProperties": False,
                    "properties": {
                        step["operationId"]: {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                parameter["name"]: schema_utils.merge(
                                    parameter.get("schema", {}),
                                    schema_utils.remove_empty({"description": parameter.get("description"),
                                                  "default": parameter.get("default")
                                                  }))
                                for parameter in step["parameters"]
                            }
                        }
                    }
                }
            )
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
