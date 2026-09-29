from geologic.probe.plan import chunk, is_current


def test_chunk_even_and_remainder():
    ps = [{"prompt_id": f"q{i}"} for i in range(10)]
    parts = chunk(ps, 3)
    assert [len(p) for p in parts] == [4, 3, 3] and sum(parts, []) == ps
    assert chunk([], 4) == []


def test_epoch_guard():  # Review Focus 4
    assert is_current(3, 3) and not is_current(2, 3)
