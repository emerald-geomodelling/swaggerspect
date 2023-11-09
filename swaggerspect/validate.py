"""Validation tools"""


import jsonschema

__all__ = ["GroupMergingValidator"]

validate_properties = jsonschema.Draft202012Validator.VALIDATORS["properties"]


class GroupMergingValidator(object):
    """jsonchema validator class that validates
data against a schema, but also transforms your data ungrouping any
parameters grouped by `get_apis(objs, group_parameters = True)`.
"""
    def __init__(self, *arg, **kw):
        self.renames = []
        self.cls = jsonschema.validators.extend(
            jsonschema.Draft202012Validator, {"properties" : self._merge_groups}) 
        self.inst = self.cls(*arg, **kw)

    def _merge_groups(self, validator, properties, instance, schema):   
        for error in validate_properties(validator, properties, instance, schema):
            yield error

        for property, subschema in properties.items():
            if subschema.get("x-python-type", True) is None:
                self.renames.append((instance, property))

    def __getattr__(self, name):
        return getattr(self.inst, name)

    def validate(self, data):
        self.renames = []
        self.inst.validate(data)       
        for instance, prop in self.renames:                                
            for key, value in instance.pop(prop).items():
                instance[prop + "__" + key] = value
