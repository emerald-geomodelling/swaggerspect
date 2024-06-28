import inspect

def make_value_schema(*values):
    for value in values:
        if value is inspect._empty:
            continue
        if value is None:
            continue
        if isinstance(value, (int, str, float, dict, list, bool)):
            return {"default": value}
    return {}
