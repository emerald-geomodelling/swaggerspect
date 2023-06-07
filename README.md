# Swaggerspect

Swaggerspect introspects python classes and functions and generates machine readable descriptions in the syntax used by [Swagger](https://swagger.io/specification/)
(this is an intentional slight misuse of swagger, as swagger is meant to document REST API:s, not python functions).

The intended usage is to generate JSON that can be sused to generate a simple user interface for the python functions or classes. In particular, this could be a web based user interface,
and as such, care is taken that the introspection data is serializable using JSON or YAML.

# Usage

To get a swagger specification fragment for a single function or class:
```
print(yaml.dump(swaggerspect.get_api(some_function_or_class)))
```

To get a full swagger definition for a set of functions and classes, either listed in an entry point group, or available in a single module:
```
print(yaml.dump(swaggerspect.get_apis("my.entrypoint.group")))
print(yaml.dump(swaggerspect.get_apis("some_module_name")))
```

The same, but as a JSON schema for a single finction call, or a list of calls (`multi=True`):
```
print(yaml.dump(swaggerspect.swagger_to_json_schema(swaggerspect.get_apis("my.entrypoint.group"), multi=False)))
```
