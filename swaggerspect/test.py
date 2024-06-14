import typing

class JsonSchema(object):
    def __new__(cls, schema):
        self = object.__new__(cls)
        self.json_schema = schema
        return typing.Annotated[typing.Any, self]

def foo(fie : JsonSchema({
        "properties": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"}
        }
    })): pass


foo({"hello": 1})
