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
    
def get_function_api_parameters_inspect(fn):
    return schema_utils.remove_empty(
        {
            "properties": {
                k: schema_utils.merge(
                    type_schema.make_type_schema(
                        v.annotation,
                        type_schema.typeof(v.default),
                        hasdefault = v.default),
                    value_schema.make_value_schema(v.default))
                for k, v in inspect.signature(fn).parameters.items()
            }
        }
    )

def get_function_api_parameters_comments(fn):
    docs = inspect.getdoc(fn)
    if docs is None: return []
    docast = numpydoc.docscrape.NumpyDocString(docs)
    
    return {"properties":
            {p.name: schema_utils.merge(
                {"description": "\n".join(p.desc)},
                type_schema.make_type_schema(p.type))
             for p in docast["Parameters"]}}
    
def get_function_api(fn, name = None):
    args = schema_utils.remove_hidden(
        schema_utils.merge(
            {"type": "object",
             "additionalProperties": False},
            schema_utils.merge(get_function_api_parameters_inspect(fn),
                               get_function_api_parameters_comments(fn))))

    docs = inspect.getdoc(fn)
    description = type_schema.get_type_name(fn)
    if docs is not None:
        docast = numpydoc.docscrape.NumpyDocString(docs)
        description = "\n".join(docast["Summary"] + docast["Extended Summary"])

    returntype = inspect.signature(fn).return_annotation

    operation_id = name or type_schema.get_type_name(fn)
    return schema_utils.remove_empty(
        {
            "type": "object",
            "title": operation_id.split(".")[-1],
            "description": description,
            "required": [operation_id],
            "additionalProperties": False,
            "properties": {operation_id: args},
            "x-returntype": type_schema.make_type_schema(returntype)
        })
