# Deep Dive: The Feedback Loop — `src/chat/feedback.py` + candidate store

> **Study order:** #18 · **Difficulty:** ★★★☆☆ — three small files
> (`feedback.py`, `candidate_store.py`, the `routes/feedback.py` shim) but
> together they form the project's most important behavioural property: the
> system gets better the more it is used.
>
> **Files:** [`src/chat/feedback.py`](../../src/chat/feedback.py) ·
> [`src/chat/candidate_store.py`](../../src/chat/candidate_store.py) ·
> [`src/routes/feedback.py`](../../src/routes/feedback.py) ·
> **Routes:** [`POST /feedback/`](../architecture-and-design/api-routes/feedback-endpoint-explained.md),
> [`POST /wiki/candidates/{id}/promote`](../architecture-and-design/api-routes/wiki-endpoint-explained.md),
> [`POST /wiki/candidates/{id}/discard`](../architecture-and-design/api-routes/wiki-endpoint-explained.md).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [Two parallel circuits — feedback and candidates](#two-parallel-circuits--feedback-and-candidates)
- [Circuit 1 — `POST /feedback/` (👍 / 👎)](#circuit-1--post-feedback---)
- [Circuit 2 — candidates from `GAP` answers](#circuit-2--candidates-from-gap-answers)
- [Where the data lands and why those formats](#where-the-data-lands-and-why-those-formats)
- [How the loop actually closes](#how-the-loop-actually-closes)
- [Rough metrics worth tracking](#rough-metrics-worth-tracking)
- [🚚 Courier explainer — the trip-debrief desk](#-courier-explainer--the-trip-debrief-desk)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

Every other piece of the knowledge engine is a *read* path — ingest, retrieve,
answer. The feedback loop is the only *write back into the corpus* path. It
turns three live signals into permanent improvements:

1. **👍 on a chat answer** → the Q&A pair lands in `verified-answers.md`,
   which is in the wiki tree, which is scanned by the next ingest.
2. **👎 on a chat answer** → the question lands in
   `scripts/golden-questions.yaml` so future eval runs catch the regression.
3. **Promote on a candidate** (the LLM's off-doc answer to a `GAP` question) →
   same `verified-answers.md` write, same next-ingest pickup.

Without these three writes, gaps stay open forever and the courier never learns
which roads actually need building.

---

## Two parallel circuits — feedback and candidates

The project carefully splits two ideas that look the same but trigger
differently:

| Circuit | Trigger | What gets written | Component |
|---------|---------|-------------------|-----------|
| Feedback | A human clicks 👍/👎 on **any** chat answer (HIGH, PARTIAL, or GAP) | `verified-answers.md` (👍) **or** `golden-questions.yaml` (👎); always the raw JSONL | `FeedbackProcessor` in `src/chat/feedback.py` |
| Candidates | The chat engine produced a `GAP` answer using LLM training knowledge — a candidate is created automatically per gap | `wiki/candidates/pending-review.md` + `candidates.jsonl`; promotion later writes `verified-answers.md` | `CandidateStore` in `src/chat/candidate_store.py` |

Two circuits, one filing cabinet (`wiki/feedback/verified-answers.md`). That
shared sink is what guarantees both paths fold into the next ingest the same
way.

---

## Circuit 1 — `POST /feedback/` (👍 / 👎)

The route shim is three lines:

```python
@router.post("/")
async def submit_feedback(request: Request, body: FeedbackSignal):
    result = await request.app.state.feedback_proc.process(body)
    return result
```

`FeedbackSignal` (see [`src/models.py`](../../src/models.py)) carries
`session_id`, `question`, `answer`, `thumbs_up`, `correction`,
`missing_info`, and `timestamp`. `FeedbackProcessor.process()` then branches:

```python
if feedback.thumbs_up:
    await self._save_verified_qa(feedback)
    result = {"action": "wiki_updated", "message": "Answer saved to wiki as verified Q&A."}
else:
    await self._save_to_eval_set(feedback)
    result = {"action": "eval_set_updated", "message": "Question added to evaluation set for improvement."}

await self._save_raw_feedback(feedback)
```

| Branch | File written | Format | Effect on next run |
|--------|--------------|--------|--------------------|
| `thumbs_up=True` | `wiki/feedback/verified-answers.md` | Markdown section with `## …timestamp… — Verified Answer`, `**Q:**`, `**A:**` | Next `POST /ingest/run` chunks and embeds this Q&A so the same question is answered from docs |
| `thumbs_up=False` | `scripts/golden-questions.yaml` | YAML list entry with `question`, empty `expected_topics`, `correction`, `added_from_feedback: true`, `added_at` | Next `POST /eval/run` includes this question — guaranteeing the regression is measured |
| Both | `wiki/feedback/raw-feedback.jsonl` | One JSON line per `FeedbackSignal` (full payload) | Audit / future analytics; not directly read elsewhere yet |

`session_id` and `timestamp` are kept in the raw JSONL so you can reconstruct
the original chat session later — useful when grading whether a 👎 was the
LLM's fault or a chunking-strategy artefact.

---

## Circuit 2 — candidates from `GAP` answers

The chat engine creates a candidate automatically whenever it routes through
the fallback branch (see the [Chat Engine deep dive](chat-engine-deep-dive.md#step-4--routing-grounded-vs-fallback)):

```python
candidate = await self.candidate_store.save_candidate(
    question=request.question,
    answer=answer_text,
    courier_analogy=_extract_courier(answer_text),
    gap_id=gap.id,
)
```

`CandidateStore.save_candidate()` writes two files in `wiki/candidates/`:

| File | Format | Purpose |
|------|--------|---------|
| `candidates.jsonl` | One JSON line per `WikiCandidate` (`id`, `question`, `answer`, `courier_analogy`, `gap_id`, `status`, timestamps) | Machine-readable; what `list_candidates`, `summary`, and `_find` read |
| `pending-review.md` | Markdown section per candidate with the `🔵 CANDIDATE {id}` heading, the question, the answer, the courier analogy, and explicit `promote` / `discard` URLs | Human review surface — open the file in a markdown viewer, decide, click |

Three terminal states:

| Verb | Route | Effect on JSONL | Effect on `verified-answers.md` |
|------|-------|----------------|-------------------------------|
| `promote` | `POST /wiki/candidates/{id}/promote` | `status: pending → promoted`, `promoted_at` stamped | Appends a `## …timestamp… — Promoted Candidate {id}` section identical in shape to the 👍 entry |
| `discard` | `POST /wiki/candidates/{id}/discard` | `status: pending → discarded` | None — the gap stays open |
| (Pending) | n/a | n/a | n/a — sits on the supervisor's clipboard until reviewed |

Because promotion writes to **the same file** as 👍 feedback, the next ingest
treats both the same way — the candidate's answer becomes part of the corpus
and the matching gap can finally close after one re-ingest.

---

## Where the data lands and why those formats

```text
wiki-output/
├── feedback/
│   ├── verified-answers.md   ← 👍 + promoted candidates  (markdown, scanned by ingest)
│   └── raw-feedback.jsonl    ← every FeedbackSignal      (jsonl, audit only)
└── candidates/
    ├── pending-review.md     ← human review surface       (markdown)
    └── candidates.jsonl      ← machine-readable rows      (jsonl, queries + status updates)

scripts/
└── golden-questions.yaml     ← 👎 questions appended      (yaml, eval input)
```

Two formats, two reasons:

| Format | Why used | 🚚 Courier |
|--------|----------|-----------|
| Markdown for `verified-answers.md`, `pending-review.md`, `unanswered.md` | The ingestion scanner already chunks markdown — using markdown means the next ingest indexes them with zero special-case code | The supervisor's wall posters and the ingestion clerk both read the same handwriting; no translation needed |
| JSONL for `raw-feedback.jsonl`, `candidates.jsonl`, `gaps.jsonl` | Append-friendly, one record per line, easy to stream-update without parsing the whole file (used by `_update_status` to flip a single row) | The auditor's filing cabinet — easy to drop a new card on the pile without rewriting the whole drawer |

`scripts/golden-questions.yaml` is YAML because the evaluator expects
`questions:` to be a YAML list — see
[`src/evaluation/evaluator.py`](../../src/evaluation/evaluator.py)`.load_golden_questions()`.

---

## How the loop actually closes

The shortest possible round trip from a bad answer to a good one looks like:

```text
t0  user asks "what is GraphRAG?"             → confidence=GAP
                                              → answer from LLM training (with ⚠️ banner)
                                              → candidate {id=ab12cd34, gap_id=ef56gh78}
                                              → wiki/candidates/pending-review.md ← row appended
                                              → wiki/gaps/unanswered.md          ← 🔴 row appended

t1  reviewer reads the candidate, agrees      → POST /wiki/candidates/ab12cd34/promote
                                              → wiki/feedback/verified-answers.md ← Q&A appended
                                              → candidates.jsonl status flipped to "promoted"

t2  operator runs                              → POST /ingest/run
                                              → verified-answers.md is one of the scanned files
                                              → its Q&A gets chunked + embedded + topic-extracted

t3  next user asks "what is GraphRAG?"        → vector search now hits the verified Q&A
                                              → confidence=HIGH, answer_source=docs
                                              → DELETE /wiki/gaps/ef56gh78  (close the ticket)
```

The same shape applies to the 👍 path — the only difference is that the entry
in `verified-answers.md` is created at the moment of the 👍 click instead of
at promotion time.

The 👎 path is asymmetric: it does **not** add a verified answer — it adds
a *failing test* to `golden-questions.yaml`. The next `POST /eval/run` then
proves the system is still wrong; once a doc is added or a candidate is
promoted, the evaluator records the metric improvement.

---

## Rough metrics worth tracking

These are not implemented as dashboards yet; they are the things you would
watch if you wired one up. All three derive from files this module writes.

| Metric | Computed from | Why it matters | 🚚 Courier |
|--------|---------------|---------------|-----------|
| Gap-resolution rate | `gap_summary()`'s `resolved / total` over time | Are users actually closing gaps, or just letting them pile up? | Are red flags being taken off the wall faster than new ones go up? |
| Candidate-promotion ratio | `summary()` from `CandidateStore` — `promoted / (promoted + discarded)` | High = LLM training knowledge was usually right; low = tighten the strict prompt or lower the GAP threshold | What fraction of off-road inventions does the supervisor approve as actual roads? |
| Feedback skew | Lines in `raw-feedback.jsonl` with `thumbs_up=true` vs `false` over time | Trend — quality should improve as the corpus grows; a flat or declining ratio means the loop is not closing | Is the trip-debrief desk getting more high-fives than thumbs-down each week? |

---

## 🚚 Courier explainer — the trip-debrief desk

The feedback loop is the trip-debrief desk in the corner of the depot. After
every delivery the supervisor can give the courier a 👍 or a 👎. A 👍 means
"frame this shipping manifest and pin it to the wall" — the framed note goes into
the verified-answers drawer of the wiki cabinet, and on the next pre-sort the
ingestion clerk re-files it alongside the original delivery docs so the next
courier starts with it in the parcel. A 👎 means "this delivery was wrong
even though the courier thought it was right" — the question goes onto next
month's training-run sheet so the auditor has to re-grade it after every
change.

The candidate desk is a parallel stand for the off-road trips. When the
auditor red-stamps a delivery, the courier is allowed to write something from
memory but the note is clipped onto the supervisor's clipboard with a 🔵
sticker. The supervisor reviews each clipped note, promotes the good ones
(they get framed in the same wall-poster drawer the 👍 trips go into), and
discards the bad ones (the red flag stays up on the wall and the next courier
inherits the same gap).

Both desks empty into the same drawer. That single shared drawer is what
makes the whole system get smarter — every approved trip, no matter which desk
it came from, is in the parcel the next courier loads.

---

## Self-test questions

1. The 👍 branch and the candidate-promotion branch both write to
   `verified-answers.md`. Why is that intentional rather than a duplication
   bug?
2. The 👎 branch does NOT write to `verified-answers.md`. What does it write
   to, and why is that the right place?
3. Trace the data path from `POST /feedback/` with `thumbs_up=true` all the
   way to the next chat that benefits from it. How many disk writes, and how
   many user actions, are required?
4. `CandidateStore._update_status` rewrites `candidates.jsonl` in place rather
   than appending a status-change record. What trade-off is being made there?
5. If you wanted to add a "feedback skew per provider" dashboard, which file
   would you read, and which fields would you group by?

---

## What to read next

- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the only writer that
  creates candidates.
- [Gap Detector Deep Dive](gap-detector-deep-dive.md) — produces the `gap_id`
  every candidate links back to.
- [Wiki Endpoint](../architecture-and-design/api-routes/wiki-endpoint-explained.md) —
  the promote / discard / list-candidates routes.
- [Feedback Endpoint](../architecture-and-design/api-routes/feedback-endpoint-explained.md) —
  the `POST /feedback/` route in full.
- [Evaluation Framework Deep Dive](evaluation-framework-deep-dive.md) — picks
  up the 👎 questions on the next eval run.
