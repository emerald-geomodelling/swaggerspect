# Swaggerspect

Swaggerspect introspects python classes and functions and generates machine readable descriptions in the [Swagger](https://swagger.io/specification/) and [JSON Schema](https://json-schema.org/) syntaxes.
Yes, this is an intentional misuse of swagger, as swagger is meant to document REST API:s, not python functions, and to a lesser degree, of JSON Schema.

The intended usage is to generate JSON that in turn can be sused to generate a simple user interface for the python functions or classes.
In particular, this works out of the box with the [json-editor](https://github.com/json-editor/json-editor) web based JSON editor. Note that this library does ot provide any framework to serve REST requests executing the functions in any generate JSON; but that is about 10 lines of code in your favourite web app framework (Django, Flask...).

# Usage

To get a swagger specification fragment for a single function or class:
```
print(yaml.dump(swaggerspect.get_api(some_function_or_class)))
```

To get a full swagger definition for the methods of a class:
print(yaml.dump(swaggerspect.get_apis("some_module_name.SomeClassName")))

To get a full swagger definition for a set of functions and classes, either listed in an entry point group, or available in a single module:
```
print(yaml.dump(swaggerspect.get_apis("my.entrypoint.group")))
print(yaml.dump(swaggerspect.get_apis("some_module_name")))
```

The same, but as a JSON schema for a single finction call, or a list of calls (`multi=True`):
```
print(yaml.dump(swaggerspect.swagger_to_json_schema(swaggerspect.get_apis("my.entrypoint.group"), multi=False)))
```

# Notes and caveats:

* The API parameters for a class, are its properties, not the
  parameters to `__init__()`.
* Parameters of unknown types / types with no equivalent in JSON, that
  have default values, are hidden/ignored.
* A more elaborate schema for a parameter can be specified using
  typing.Annotated with an annotation that has a property
  `json_schema` containing a literal JSON Schema fragment.
* Parameters of a class can be grouped into dictionaries in the
  schema, by sharing a common prefix (separated by `__`), and seting
  `group_parameters=True` in the call to `get_apis`.
