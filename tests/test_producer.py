import random
from datetime import datetime, timezone
from geologic.producer import SignalProducer, to_record

class ListSink:
    def __init__(self): self.records, self.closed = [], False
    def send(self, r): self.records.append(r)
    def close(self): self.closed = True

NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)

def test_to_record_micros():
    r = to_record({"signal_id": "a", "ingested_at": NOW, "payload": "{}"})
    assert r["ingested_at"] == int(NOW.timestamp() * 1_000_000)

def test_emit_and_inject():
    sink = ListSink()
    p = SignalProducer(sink, random.Random(1), clock=lambda: NOW)
    assert p.emit_background(5) == 5
    sid = p.inject("S3_kittle")
    assert len(sink.records) == 6 and sink.records[-1]["signal_id"] == sid
    assert sink.records[-1]["producer"] == "seeded"
