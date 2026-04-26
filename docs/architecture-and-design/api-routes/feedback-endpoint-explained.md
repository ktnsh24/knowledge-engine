# Endpoint Deep Dive: `POST /feedback/` — the trip-debrief window

> **Study order:** #23 · **Source:** [`src/routes/feedback.py`](../../../src/routes/feedback.py)
> · **Component:** [Feedback Loop](../../ai-engineering/feedback-loop-deep-dive.md)
> · **Model:** `FeedbackSignal` in [`src/models.py`](../../../src/models.py).

---

## Table of Contents

- [Endpoint summary](#endpoint-summary)
- [Request schema — `FeedbackSignal`](#request-schema--feedbacksignal)
- [Response schema](#response-schema)
- [Internal flow](#internal-flow)
- [`curl` examples](#curl-examples)
- [Error cases](#error-cases)
- [🚚 Courier explainer — the trip-debrief window](#-courier-explainer--the-trip-debrief-window)

---

## Endpoint summary

| Method | Path | Auth | Purpose | 🚚 Courier |
|--------|------|------|---------|-----------|
| POST | `/feedback/` | none | Record a 👍/👎 verdict on a chat answer; 👍 appends the Q&A to `wiki/feedback/verified-answers.md` (re-ingested on the next run), 👎 appends the question to `scripts/golden-questions.yaml` (graded on the next eval) | The trip-debrief window — supervisors hand in good/bad verdicts on yesterday's deliveries and the next pre-sort or next inspection acts on them |

Mounted at `/feedback` with tag `feedback` in `src/main.py`.

---

## Request schema — `FeedbackSignal`

```python
class FeedbackSignal(BaseModel):
    session_id:   str
    question:     str
    answer:       str
    thumbs_up:    bool                      # True = good, False = bad
    correction:   str = ""                  # optional user correction
    missing_info: str = ""                  # what was missing from the answer
    timestamp:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `session_id` | string | yes | Free-form session identifier — used to reconstruct chat context later from the raw JSONL audit log |
| `question` | string | yes | The exact question the user asked (echoed by the UI from the chat response) |
| `answer` | string | yes | The exact answer the chat engine returned; on 👍 it is written verbatim to the verified file |
| `thumbs_up` | boolean | yes | `true` → 👍 path; `false` → 👎 path |
| `correction` | string | no | Free-form user correction; logged on 👎 as part of the YAML entry; logged in the raw JSONL on 👍 too |
| `missing_info` | string | no | Free-form note about what was missing; only logged in the raw JSONL today |
| `timestamp` | ISO8601 | no | Defaults to "now" UTC if omitted |

---

## Response schema

```json
{ "action": "wiki_updated",     "message": "Answer saved to wiki as verified Q&A." }
```

or

```json
{ "action": "eval_set_updated", "message": "Question added to evaluation set for improvement." }
```

| Field | Values | When |
|-------|--------|------|
| `action` | `wiki_updated` \| `eval_set_updated` \| `none` | `wiki_updated` on 👍, `eval_set_updated` on 👎; `none` is a defensive default |
| `message` | human-readable string | Safe to surface to the UI as a toast |

---

## Internal flow

```text
client
  │  POST /feedback/
  │  body: FeedbackSignal (validated by Pydantic)
  ▼
FastAPI middleware (CORS)
  │
  ▼
src/routes/feedback.py:submit_feedback(request, body)
  │
  └── app.state.feedback_proc.process(body)         ← FeedbackProcessor
        │
        ├── if body.thumbs_up:                       ── 👍 path ──
        │     await _save_verified_qa(body)          → wiki/feedback/verified-answers.md
        │     result = {"action": "wiki_updated", ...}
        │
        ├── else:                                    ── 👎 path ──
        │     await _save_to_eval_set(body)          → scripts/golden-questions.yaml (append)
        │     result = {"action": "eval_set_updated", ...}
        │
        └── await _save_raw_feedback(body)           → wiki/feedback/raw-feedback.jsonl
              return result
```

Two important properties of this flow:

1. **Always-on raw audit.** Every request lands in `raw-feedback.jsonl`,
   regardless of branch. That file is the source of truth for "what feedback
   did we actually receive?"
2. **One file is the corpus, the other is the test set.** 👍 writes to a file
   the *ingestion* pipeline picks up; 👎 writes to a file the *evaluator*
   picks up. The wiring is what closes the self-improving loop — see the
   [Feedback Loop deep dive](../../ai-engineering/feedback-loop-deep-dive.md#how-the-loop-actually-closes).

---

## `curl` examples

```bash
# 👍 — promote the answer into the corpus (effective on next /ingest/run)
curl -X POST http://localhost:8200/feedback/ \
  -H 'Content-Type: application/json' \
  -d '{
        "session_id": "demo-1",
        "question":   "What is GraphRAG?",
        "answer":     "GraphRAG is RAG with an explicit knowledge graph...",
        "thumbs_up":  true
      }'

# 👎 — add to the failing-test set with a correction
curl -X POST http://localhost:8200/feedback/ \
  -H 'Content-Type: application/json' \
  -d '{
        "session_id":   "demo-1",
        "question":     "What is the cost of a 100-topic wiki rebuild on AWS?",
        "answer":       "Around $0.50",
        "thumbs_up":    false,
        "correction":   "Closer to $0.17 — see Wiki Generator deep dive cost table.",
        "missing_info": "Per-page cost breakdown"
      }'
```

---

## Error cases

| Trigger | Response | 🚚 Courier |
|---------|----------|-----------|
| Missing required field (e.g. no `thumbs_up`) | `422 Unprocessable Entity` from FastAPI's Pydantic validation | The trip-debrief form was submitted blank; the window operator hands it back |
| `wiki/feedback/` directory missing | The processor creates it on init (`mkdir(parents=True, exist_ok=True)`); first request after a fresh checkout still works | Trip-debrief drawer is built the first time someone files a verdict |
| Disk full when appending to `verified-answers.md` or `golden-questions.yaml` | `IOError` bubbles up as a `500` | Trip-debrief desk runs out of paper; window operator returns a hard error |
| Same Q&A submitted twice with `thumbs_up=true` | Both entries are appended verbatim to `verified-answers.md`; the next ingest will create duplicate chunks unless the chunker dedupes | Two framed copies of the same trip on the wall — the warehouse will end up with two copies of the GPS-stamp |
| 👎 with empty `correction` | Accepted; the YAML entry has `correction: ""` | Supervisor flags a trip as bad without saying why; the inspection set still grows but the per-row hint column is blank |
| Chat engine never produced this `(question, answer)` pair (faked by the caller) | Accepted; nothing in the route validates the pair existed | The trip-debrief window does not check delivery records; it trusts the supervisor's verdict and files it |

---

## 🚚 Courier explainer — the trip-debrief window

The feedback window is where supervisors finish each delivery. They look at
the courier's shipping manifest, decide if it was a good trip, and drop a small
form through the slot. Every form goes into the bottom drawer of the cabinet
(the raw audit log) regardless of verdict — that drawer never lies about what
the supervisors actually said. On a 👍, the window operator also walks the
form to the wiki cabinet's verified drawer where the next pre-sort will
re-shelve the Q&A as part of the corpus, so the next courier starts that
delivery with the answer already in the parcel. On a 👎, the operator
instead walks the form to the inspector's binder so that question becomes
a permanent test delivery — and any future change to the courier or the
warehouse has to pass it before going out the door.
