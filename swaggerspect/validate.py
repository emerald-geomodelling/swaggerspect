"""Validation tools"""


import jsonschema

__all__ = ["GroupMergingValidator"]

validate_properties = jsonschema.Draft202012Validator.VALIDATORS["properties"]

def _merge_groups(validator, properties, instance, schema):
    for error in validate_properties(validator, properties, instance, schema):
        yield error

    for property, subschema in properties.items():
        if subschema.get("x-python-type", True) is None:
            validator.renames.append((instance, property))


class GroupMergingValidator(jsonschema.validators.extend(
    jsonschema.Draft202012Validator, {"properties" : _merge_groups})):
    """jsonchema subclass that validates
data against a schema, but also transforms your data ungrouping any
parameters grouped by `get_apis(objs, group_parameters = True)`.
"""
    
    def evolve(self, **changes):
        res = super(GroupMergingValidator, self).evolve(**changes)
        res.renames = self.renames
        return res
        
    def validate(self, data):
        self.renames = []
        super(GroupMergingValidator, self).validate(data)
        for instance, prop in self.renames:
            for key, value in instance.pop(prop).items():
                instance[prop + "__" + key] = value
