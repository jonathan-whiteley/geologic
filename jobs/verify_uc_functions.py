# jobs/verify_uc_functions.py
import itertools
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
except NameError:
    sys.path.insert(0, "../src")
from pyspark.sql import SparkSession
from geologic.tiering import assign_tier

spark = SparkSession.builder.getOrCreate()
bad = []
for asset, p, v, e, j, c in itertools.product(["jsonld", "alt_text", "faq", "description", "mystery"], [0, 1], [0, 1], [0, 1], [0, 1], [0.5, 0.9]):
    sql = spark.sql(f"SELECT jdub_demo.geologic.assign_tier('{asset}', {bool(p)}, {bool(v)}, {bool(e)}, {bool(j)}, {c}) t").first()["t"]
    py = assign_tier(asset, touches_persona=bool(p), visual_sourced=bool(v), exclusion_hit=bool(e), jsonld_valid=bool(j), resolution_confidence=c)
    if sql != py:
        bad.append((asset, p, v, e, j, c, sql, py))
assert spark.sql("SELECT jdub_demo.geologic.check_exclusions('Dax news', 'p_fictional_dax') r").first()["r"] == "EX-01"
assert spark.sql("SELECT jdub_demo.geologic.check_exclusions('arrest report', NULL) r").first()["r"] == "EX-07"
assert spark.sql("SELECT jdub_demo.geologic.check_exclusions('Crazy Puffs', 'p_kittle') r").first()["r"] is None
assert spark.sql("SELECT jdub_demo.geologic.check_facts('It costs $6.49 or $5') r").first()["r"] == '[5.0]'
assert spark.sql("""SELECT jdub_demo.geologic.validate_jsonld('{"@type":"MenuItem","offers":{"priceCurrency":"EUR"}}') r""").first()["r"] == '["priceCurrency must be USD"]'
assert not bad, bad
print("UC functions match Python")
