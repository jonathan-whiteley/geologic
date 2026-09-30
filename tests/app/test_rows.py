import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
class Arr:
    """Stands in for the numpy arrays the SQL connector returns."""
    def __init__(self, xs): self.xs = xs
    def tolist(self): return list(self.xs)
    def __bool__(self): raise ValueError("ambiguous")

from backend.rows import plain as _plain

def test_plain_converts_numpy_arrays_and_structs():
    v = _plain(Arr([{"item": "a", "tags": Arr(["x", "y"])}]))
    assert v == [{"item": "a", "tags": ["x", "y"]}]
    assert _plain(Arr([])) == [] and not _plain(Arr([]))

def test_plain_leaves_scalars():
    assert _plain("abc") == "abc" and _plain(3) == 3 and _plain(None) is None
