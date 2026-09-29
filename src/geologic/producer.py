"""Streams synthetic signals to bronze_signals through Zerobus."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Protocol
from geologic.datagen.signals import background_signal, seeded_signal


class Sink(Protocol):
    def send(self, record: dict) -> None: ...
    def close(self) -> None: ...


def to_record(row: dict) -> dict:
    """Convert a signal row to a Zerobus-ready dict.

    Converts ingested_at datetime to integer epoch microseconds.
    All other fields pass through unchanged.
    """
    out = dict(row)
    if isinstance(out.get("ingested_at"), datetime):
        out["ingested_at"] = int(out["ingested_at"].timestamp() * 1_000_000)
    return out


class SignalProducer:
    def __init__(self, sink: Sink, rng, clock=lambda: datetime.now(timezone.utc)):
        self.sink, self.rng, self.clock = sink, rng, clock

    def emit_background(self, n: int) -> int:
        for _ in range(n):
            self.sink.send(to_record(background_signal(self.rng, self.clock())))
        return n

    def inject(self, truth_id: str) -> str:
        row = seeded_signal(truth_id, self.clock())
        self.sink.send(to_record(row))
        return row["signal_id"]


class ZerobusSink:
    """JSON-record Zerobus stream into an existing Delta table.

    Deviation from brief: send() uses ingest_record_nowait(record) with a
    plain dict (not the deprecated ingest_record(json.dumps(record)) call).
    The SDK serializes the dict to JSON for JSON-mode streams automatically.
    flush() + close() are called in close() as in the brief.
    """

    def __init__(self, stream):
        self._s = stream

    @classmethod
    def from_secrets(cls, dbutils, table: str, workspace_url: str):
        from zerobus.sdk.sync import ZerobusSdk
        from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties
        get = lambda k: dbutils.secrets.get("geologic", k)
        sdk = ZerobusSdk(get("zb_endpoint"), workspace_url)
        stream = sdk.create_stream(
            get("zb_client_id"),
            get("zb_client_secret"),
            TableProperties(table),
            StreamConfigurationOptions(record_type=RecordType.JSON),
        )
        return cls(stream)

    def send(self, record: dict) -> None:
        # ingest_record() is deprecated since SDK v0.3.0; use ingest_record_nowait()
        # Pass the dict directly; the SDK serializes it for JSON streams.
        self._s.ingest_record_nowait(record)

    def close(self) -> None:
        self._s.flush()
        self._s.close()
