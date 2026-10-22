"""Row value helpers kept free of connector imports so they test locally."""
import json

_COMPLEX = ("array", "map", "struct")


def plain(v):
    """The connector returns ARRAY/STRUCT columns as numpy arrays and dicts; convert to plain Python."""
    if hasattr(v, "tolist") and not isinstance(v, (str, bytes)):
        v = v.tolist()
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    return v


def plain_typed(v, type_code=None):
    """plain(), plus: without Arrow results the connector returns ARRAY/MAP/STRUCT columns as JSON text. Decode those
    (by the cursor's column type, never by guessing from the value); text that is not JSON is left as it is."""
    if isinstance(v, str) and str(type_code or "").lower() in _COMPLEX:
        try:
            return plain(json.loads(v))
        except ValueError:
            return v
    return plain(v)
