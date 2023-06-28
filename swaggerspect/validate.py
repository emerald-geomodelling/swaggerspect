"""Validation tools"""

import jsonschema

__all__ = ["GroupMergingValidator"]

validate_properties = jsonschema.Draft202012Validator.VALIDATORS["properties"]

def _merge_groups(validator, properties, instance, schema):
    for error in validate_properties(validator, properties, instance, schema):
        yield error

    for property, subschema in properties.items():
        if subschema.get("x-python-type", True) is None:
            for key, value in instance.pop(property).items():
                instance[property + "__" + key] = value

GroupMergingValidator = jsonschema.validators.extend(
    jsonschema.Draft202012Validator, {"properties" : _merge_groups})

GroupMergingValidator.__doc__ = """jsonchema subclass that validates
data against a schema, but also transforms your data ungrouping any
parameters grouped by `get_apis(objs, group_parameters = True)`.
"""
