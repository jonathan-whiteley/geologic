"""Row value helpers kept free of connector imports so they test locally."""
def plain(v):
    """The connector returns ARRAY/STRUCT columns as numpy arrays and dicts; convert to plain Python."""
    if hasattr(v, "tolist") and not isinstance(v, (str, bytes)):
        v = v.tolist()
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    return v
