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
        if isinstance(ss, ast.Expr) and isinstance(ss.value, ast.Constant):
            if isinstance(s, ast.Assign):
                for t in s.targets:
                    propdocs[t.id] = ss.value.value
            elif isinstance(s, ast.AnnAssign):
                propdocs[s.target.id] = ss.value.value

    return propdocs

def get_class_api_parameters_comments(cls):
    return [{"name": n, "in": "query", "description": v} for n, v in _get_class_property_comments(cls).items()]

def get_class_api_parameters_inspect(cls):
    return [{"name": n, "in": "query", "schema": {} if v is None else schema_utils.merge(type_schema.make_type_schema(type_schema.typeof(v), hasdefault=v), value_schema.make_value_schema(v))}
            for n, v in inspect.getmembers(cls)
            if (not n.startswith('__')
                and not inspect.ismethod(v)
                and not inspect.isfunction(v)
                and not inspect.isdatadescriptor(v))]
    
def get_class_api_parameters_typing(cls):
    return [{"name": k, "in": "query", "schema": type_schema.make_type_schema(t)} for k, t in typing.get_type_hints(cls, include_extras=True).items()]
    
def get_class_properties_api(cls):
    args = schema_utils.remove_hidden(
        schema_utils.merge(get_class_api_parameters_typing(cls),
              schema_utils.merge(get_class_api_parameters_inspect(cls),
                    get_class_api_parameters_comments(cls))))
    return {
        "operationId": type_schema.get_type_name(cls),
        "description": inspect.getdoc(cls),
        "parameters": args,
        "responses": {"default":
                      {"description": type_schema.get_type_name(cls),
                       "content": {
                           "application/json": {"schema": type_schema.make_type_schema(cls)}}}}}


def get_class_api(cls):
    api = getattr(cls, "api_type", "properties")
    if api == "properties":
        return get_class_properties_api(cls)
    else:
        return get_function_api(cls.__init__, name=type_schema.get_type_name(cls))
