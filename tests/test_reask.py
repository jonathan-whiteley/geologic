import json, re
from datetime import date, datetime, timezone
from geologic.datagen.reference import brand_facts
from geologic.probe.engine import EngineAnswer
from geologic.reask import answer_map, make_context, reask

NOW = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)
P = {"prompt_id": "q201", "prompt_text": "What should I order for a Super Bowl party for 12 people?"}


class Always:
    def __init__(self, name): self.name = name
    def answer(self, prompt): return EngineAnswer("Party Pack is $29.99 [lce_pg_deals_game_day].", ["lce_pg_deals_game_day"],
                                                  ["lce_pg_deals_game_day"])


class Judge:
    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        return json.dumps({"lce_mentioned": True, "lce_rank": 1, "brands_mentioned": ["Little Caesars"], "sentiment": "neutral",
                           "claims": [{"text": "Party Pack is $29.99.", "subject": "party_pack", "attribute": "price",
                                       "stated_value": "$29.99"}]})


def test_targeted_reask_run_row_and_answers():
    ctx = make_context(Judge(), "judge", brand_facts(), {"lce_pg_deals_game_day"}, date(2026, 10, 21))
    run, answers, claims = reask([P], [Always("Claude"), Always("Gemini")], ctx, epoch=3, trigger="approve", clock=lambda: NOW)
    assert run["run_type"] == "targeted" and run["trigger"] == "approve" and run["epoch"] == 3 and run["prompt_ids"] == ["q201"]
    assert re.fullmatch(r"run_\d{8}_\d{6}_[0-9a-f]{6}", run["run_id"]) and run["status"] == "ok"
    assert {a["run_id"] for a in answers} == {run["run_id"]} and {a["engine"] for a in answers} == {"Claude", "Gemini"}
    m = answer_map(answers, claims, {"q201": P["prompt_text"]})
    assert m[("q201", "Claude")]["answer"]["prompt_text"] == P["prompt_text"]
    assert [c["tag"] for c in m[("q201", "Claude")]["claims"]] == ["Correct"]
