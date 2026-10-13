"""Ask Genie: one Genie space, start-then-poll (ported from rev-chat-genie). Rows are returned as soon as the
SQL finishes, while Genie is still writing its summary (partial=True), so the table renders before the text."""
import re
from geologic.agents.strategist import _clean  # house-style dash cleanup ("3-4" stays a range)

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}
QUERYING = {"SUBMITTED", "FILTERING_CONTEXT", "EXECUTING_QUERY", "PENDING_WAREHOUSE", "FETCHING_METADATA"}
MAX_ROWS = 500
MAX_CONTEXT = 300
CACHE_MAX = 200
_TABLE = re.compile(r"\b(?:FROM|JOIN)\s+((?:`?\w+`?\.){0,2}`?(\w+)`?)", re.I)


def with_context(question, context):
    if not context:
        return question
    return f"Context: the user is on {context[:MAX_CONTEXT]}. Use it only if relevant.\n\nQuestion: {question}"


def source_of(sql):
    if not sql:
        return None
    names = []
    for m in _TABLE.finditer(sql):
        if m.group(2) not in names:
            names.append(m.group(2))
    return f"Genie · {', '.join(names)}" if names else "Genie"


def _val(x):
    return getattr(x, "value", x) if x is not None else None


class GenieService:
    def __init__(self, w, space_id):
        self.w, self.space_id = w, space_id
        self._results = {}  # (message, attachment, statement) -> result; polled every 1.5s, fetched once

    def ask(self, question, conversation_id=None, context=None):
        content = with_context(question, context)
        g = self.w.genie
        if conversation_id:
            try:
                r = g.create_message(space_id=self.space_id, conversation_id=conversation_id, content=content).response
                return {"conversation_id": r.conversation_id, "message_id": r.message_id or r.id}
            except Exception as e:  # expired or unknown conversation: start fresh, the panel carries on
                print(f"genie follow-up on {conversation_id} failed, starting fresh: {type(e).__name__}: {e}")
        r = g.start_conversation(space_id=self.space_id, content=content).response
        return {"conversation_id": r.conversation_id, "message_id": r.message_id or r.id}

    def _fetch(self, conversation_id, message_id, att):
        key = (message_id, att.attachment_id, getattr(att.query, "statement_id", None))
        if key in self._results:
            return self._results[key]
        res = self.w.genie.get_message_attachment_query_result(space_id=self.space_id, conversation_id=conversation_id,
                                                               message_id=message_id, attachment_id=att.attachment_id).statement_response
        if not res or not res.manifest or not res.manifest.schema or not res.result:
            return None  # SQL not finished yet
        rows = res.result.data_array or []
        out = {"columns": [{"name": c.name, "type": str(_val(c.type_name))} for c in res.manifest.schema.columns or []],
               "row_count": res.manifest.total_row_count or len(rows),
               "truncated": bool(res.manifest.truncated) or len(rows) > MAX_ROWS, "rows": [list(r) for r in rows[:MAX_ROWS]]}
        if len(self._results) >= CACHE_MAX:
            self._results.pop(next(iter(self._results)))
        self._results[key] = out
        return out

    def get_message(self, conversation_id, message_id):
        m = self.w.genie.get_message(space_id=self.space_id, conversation_id=conversation_id, message_id=message_id)
        status = str(_val(m.status))
        out = {"status": status, "partial": status not in TERMINAL, "text": "", "sql": "", "description": "", "columns": [],
               "rows": [], "row_count": 0, "truncated": False, "suggested_questions": [], "source": None, "error": None}
        if m.error and status in TERMINAL:
            out["error"] = getattr(m.error, "error", None) or str(m.error)
        texts, query_att = [], None
        for a in m.attachments or []:
            text, query, sq = getattr(a, "text", None), getattr(a, "query", None), getattr(a, "suggested_questions", None)
            if text and getattr(text, "content", None):
                texts.append(text.content)
            if query and query_att is None:
                query_att = a
            if sq and getattr(sq, "questions", None):
                out["suggested_questions"] = list(sq.questions)
        if status in TERMINAL:
            out["text"] = _clean("\n\n".join(texts))
        if query_att:
            q = query_att.query
            out["sql"], out["description"] = q.query or "", q.description or ""
            out["source"] = source_of(out["sql"])
            if status in TERMINAL and not out["text"] and q.description:
                out["text"] = _clean(q.description)
            if status == "COMPLETED" or (status not in TERMINAL and status not in QUERYING):
                try:
                    res = self._fetch(conversation_id, message_id, query_att)
                    if res:
                        out.update(res)
                except Exception as e:
                    if status == "COMPLETED":
                        print(f"genie result fetch: {type(e).__name__}: {e}")
                        out["error"] = out["error"] or "Could not fetch the query result."
        return out
