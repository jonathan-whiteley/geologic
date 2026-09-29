"""One-off or recurring signal producer: streams synthetic signals to bronze_signals via Zerobus."""
import argparse
import random
import sys
import os
import time

# Serverless spark_python_task exec does not set __file__; cwd is the script workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.producer import SignalProducer, ZerobusSink

try:
    from databricks.sdk.runtime import dbutils
except ImportError:
    dbutils = WorkspaceClient().dbutils

ap = argparse.ArgumentParser()
ap.add_argument("--rate-per-min", type=int, default=14)
ap.add_argument("--minutes", type=int, default=15)
ap.add_argument("--inject", default="")
a = ap.parse_args()

sink = ZerobusSink.from_secrets(dbutils, S.fq("bronze_signals"), WorkspaceClient().config.host)
p = SignalProducer(sink, random.Random())
try:
    for t in filter(None, a.inject.split(",")):
        print("injected", t, p.inject(t))
    for _ in range(a.minutes * 6):          # 10-second ticks
        p.emit_background(max(1, round(a.rate_per_min / 6)))
        time.sleep(10)
finally:
    sink.close()
