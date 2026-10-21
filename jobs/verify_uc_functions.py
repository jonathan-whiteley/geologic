# jobs/verify_uc_functions.py
import itertools
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
except NameError:
    sys.path.insert(0, "../src")
from geologic import jobargs; jobargs.apply()
from pyspark.sql import SparkSession
from geologic.config import settings as S
from geologic.tiering import assign_tier

spark = SparkSession.builder.getOrCreate()
bad = []
ASSETS = ["jsonld", "owned_patch", "answer_page", "moment_page", "association", "correction_email", "community_reply", "mystery"]
for asset, n, ok in itertools.product(ASSETS, [0, 1], [0, 1]):
    sql = spark.sql(f"SELECT {S.fq('assign_tier')}('{asset}', {bool(n)}, {bool(ok)}) t").first()["t"]
    py = assign_tier(asset, names_person=bool(n), checks_ok=bool(ok))
    if sql != py:
        bad.append((asset, n, ok, sql, py))
# The governance beat: the @sidelinebets sportsbook repost is quarantined by EX-03 (gambling). Jared Goff is never excluded.
assert spark.sql(f"SELECT {S.fq('check_exclusions')}('Same-game parlay boost. Gambling problem? Call 1-800-GAMBLER.', NULL) r").first()["r"] == "EX-03"
assert spark.sql(f"SELECT {S.fq('check_exclusions')}('arrest report', NULL) r").first()["r"] == "EX-07"
assert spark.sql(f"SELECT {S.fq('check_exclusions')}('Crazy Puffs', 'p_goff') r").first()["r"] is None
assert spark.sql(f"SELECT {S.fq('check_facts')}('It costs $6.49 or $5') r").first()["r"] == '[5.0]'
assert spark.sql(f"""SELECT {S.fq('validate_jsonld')}('{{"@type":"MenuItem","offers":{{"priceCurrency":"EUR"}}}}') r""").first()["r"] == '["priceCurrency must be USD"]'
assert not bad, bad
print("UC functions match Python")
