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
    return [schema_utils.remove_empty({"name": k,
                          "in": "query",
                          "schema": schema_utils.merge(
                              type_schema.make_type_schema(v.annotation, type_schema.typeof(v.default), hasdefault=v.default),
                              value_schema.make_value_schema(v.default))})
            for k, v in inspect.signature(fn).parameters.items()]

def get_function_api_parameters_comments(fn):
    docs = inspect.getdoc(fn)
    if docs is None: return []
    docast = numpydoc.docscrape.NumpyDocString(docs)
    
    return [{"name": p.name,
             "in": "query",
             "description": "\n".join(p.desc),
             "schema": type_schema.make_type_schema(p.type)}
            for p in docast["Parameters"]]
    
def get_function_api(fn, name = None):
    args = schema_utils.remove_hidden(
        schema_utils.merge(get_function_api_parameters_inspect(fn),
              get_function_api_parameters_comments(fn)))

    docs = inspect.getdoc(fn)
    description = type_schema.get_type_name(fn)
    if docs is not None:
        docast = numpydoc.docscrape.NumpyDocString(docs)
        description = "\n".join(docast["Summary"] + docast["Extended Summary"])

    returntype = inspect.signature(fn).return_annotation
        
    return {
        "operationId": name or type_schema.get_type_name(fn),
        "description": description,
        "parameters": args,
        "responses": {"default":
                      {"description": name or type_schema.get_type_name(fn),
                       "content": {
                           "application/json": schema_utils.remove_empty({
                               "schema": type_schema.make_type_schema(returntype)})}}}}
