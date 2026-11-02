"""App tests run without the databricks SDK/connector installed: stub the warehouse module they would import."""
import sys, pathlib, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))

try:
    import databricks.sql  # noqa: F401
except ImportError:
    stub = types.ModuleType("backend.warehouse")
    stub.query = lambda statement, params=None: (_ for _ in ()).throw(RuntimeError("warehouse not available in unit tests"))
    sys.modules["backend.warehouse"] = stub
