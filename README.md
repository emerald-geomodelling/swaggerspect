# Swaggerspect

Swaggerspect introspects python classes and functions and generates machine readable descriptions in the syntax used by [Swagger](https://swagger.io/specification/)
(this is an intentional slight misuse of swagger, as swagger is meant to document REST API:s, not python functions).

The intended usage is to generate JSON that can be sused to generate a simple user interface for the python functions or classes. In particular, this could be a web based user interface,
and as such, care is taken that the introspection data is serializable using JSON or YAML.
