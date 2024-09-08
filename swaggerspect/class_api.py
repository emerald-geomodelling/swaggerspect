import inspect
import numpydoc.docscrape
import ast
import typing
import types
import importlib.metadata
import copy
import sys
import collections
from . import type_schema
from . import value_schema
from . import schema_utils
from . import function_api

def _get_class_property_comments(cls):
    propdocs = collections.OrderedDict()
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
    propdocs = _get_class_property_comments(cls)
    if not len(propdocs):
        return {}
    return {
        "propertyOrder": [n for n, v in propdocs.items()],
        "properties": {
            n: {"description": v}
            for n, v in propdocs.items()}}
        
def get_class_api_parameters_inspect(cls):
    # NOTE: Parameters that do not have a default value will not be included here
    members = inspect.getmembers(cls)
    if not len(members):
        return {}
    return {
        "propertyOrder": [n for n, v in members],
        "properties":
        {n: ({} if v is None
             else schema_utils.merge(
                     type_schema.make_type_schema(
                         type_schema.typeof(v), hasdefault=v),
                     value_schema.make_value_schema(v)))
         for n, v in members
         if (not n.startswith('__')
             and not inspect.ismethod(v)
             and not inspect.isfunction(v)
             and not inspect.isdatadescriptor(v))}}

def get_class_api_parameters_typing(cls):
    # NOTE: Typing hints aren't ordered, so we can't generate a propertyOrder here
    return {"properties":
            {k: type_schema.make_type_schema(t)
             for k, t in typing.get_type_hints(
                     cls, include_extras=True).items()}}
    
def get_class_properties_api(cls, name=None):
    args = schema_utils.remove_hidden(
        schema_utils.merge(
            {"type": "object",
             "additionalProperties": False},
            schema_utils.merge(get_class_api_parameters_typing(cls),
                               schema_utils.merge(get_class_api_parameters_inspect(cls),
                                                  get_class_api_parameters_comments(cls)))))
    
    operation_id = type_schema.get_type_name(cls)
    description = inspect.getdoc(cls)
    operation_id = name or operation_id
    title = operation_id.split(".")[-1]
    
    return schema_utils.remove_empty(
        {
            "type": "object",
            "title": title,
            "description": description,
            "required": [operation_id],
            "additionalProperties": False,
            "properties": {operation_id: args},
            "x-returntype": schema_utils.merge(
                {"description": type_schema.get_type_name(cls)},
                type_schema.make_type_schema(cls))
        })

def get_class_api(cls, name=None):
    api = getattr(cls, "api_type", "properties")
    if api == "properties":
        return get_class_properties_api(cls, name=name)
    else:
        return function_api.get_function_api(cls.__init__, name=name or type_schema.get_type_name(cls))
