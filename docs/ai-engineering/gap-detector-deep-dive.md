# Deep Dive: The Gap Detector — `src/chat/gap_detector.py`

> **Study order:** #17 · **Difficulty:** ★★☆☆☆ — small, deterministic file but
> it is the piece that turns "the LLM might be hallucinating" into a tracked,
> closeable ticket.
>
> **File:** [`src/chat/gap_detector.py`](../../src/chat/gap_detector.py) ·
> **Used by:** [Chat Engine](chat-engine-deep-dive.md) · **Surfaced via:**
> [`GET /wiki/gaps`](../architecture-and-design/api-routes/wiki-endpoint-explained.md)
> and the [Feedback Loop](feedback-loop-deep-dive.md).

---

## Table of Contents

- [Why this file matters](#why-this-file-matters)
- [The three confidence levels](#the-three-confidence-levels)
- [How `assess_confidence` decides](#how-assess_confidence-decides)
- [Where gaps are persisted](#where-gaps-are-persisted)
- [Resolving a gap](#resolving-a-gap)
- [The summary panel](#the-summary-panel)
- [Tuning the thresholds](#tuning-the-thresholds)
- [🚚 Courier explainer — the auditor with the red marker](#-courier-explainer--the-auditor-with-the-red-marker)
- [Self-test questions](#self-test-questions)
- [What to read next](#what-to-read-next)

---

## Why this file matters

In plain RAG the LLM either has good context and answers well, or has poor
context and silently hallucinates — and you only find out when the user
complains. The gap detector replaces that silence with a stamp: every chat
response carries a `HIGH` / `PARTIAL` / `GAP` label, and every non-`HIGH`
answer leaves a row in `wiki/gaps/unanswered.md` for human review.

That single design move is what enables the rest of the self-improving loop —
without ticketed gaps, you have nothing to promote, nothing to backfill, and
nothing to brag about on a "regression-rate" dashboard.

---

## The three confidence levels

```python
HIGH_CONFIDENCE_THRESHOLD = 0.70
PARTIAL_CONFIDENCE_THRESHOLD = 0.40
```

| Level | Trigger | Saved to disk? | Chat engine routing | 🚚 Courier |
|-------|---------|----------------|---------------------|-----------|
| `HIGH` | `top_score ≥ 0.70` AND `chunk_count ≥ 2` | No — `save_gap()` short-circuits | Strict prompt + chunks + neighbour topics | Auditor green-stamps the trip; nothing goes in the red drawer |
| `PARTIAL` | `top_score ≥ 0.40` OR `chunk_count ≥ 1` | Yes — `🟡 PARTIAL` row in `unanswered.md` and a JSONL line | Strict prompt + chunks + an inline `[NOTE: Coverage is partial...]` notice | Auditor yellow-flags the trip and notes the half-empty parcel so the supervisor knows where to add pages |
| `GAP` | Neither threshold met | Yes — `🔴 GAP` row plus a candidate via the chat engine | Fallback prompt with empty context | Auditor red-flags the trip; the made-up route is filed on the supervisor's clipboard for promotion or rejection |

Confidence is decided by **score *and* count**, not score alone — one good
chunk on its own gets demoted to `PARTIAL`, and many low-scoring chunks still
fall to `GAP`. That two-signal rule guards against both "lucky single hit" and
"noisy retrieval looks busy but is wrong."

---

## How `assess_confidence` decides

```python
def assess_confidence(self, question, top_retrieval_score, chunk_count, topic_count):
    gap_id = str(uuid.uuid4())[:8]

    if top_retrieval_score >= HIGH_CONFIDENCE_THRESHOLD and chunk_count >= 2:
        confidence = ConfidenceLevel.HIGH
        reason = f"Good coverage — top score {top_retrieval_score:.2f}, {chunk_count} chunks found"
        suggestion = ""

    elif top_retrieval_score >= PARTIAL_CONFIDENCE_THRESHOLD or chunk_count >= 1:
        confidence = ConfidenceLevel.PARTIAL
        reason = f"Partial coverage — top score {top_retrieval_score:.2f}, {chunk_count} chunk(s) found, {topic_count} connected topic(s)..."
        suggestion = "Add more documentation about this topic and re-run ingestion. Or verify this answer with 👍..."

    else:
        confidence = ConfidenceLevel.GAP
        reason = f"No meaningful coverage — top score {top_retrieval_score:.2f}, only {chunk_count} chunk(s) found..."
        suggestion = "This topic is missing from your knowledge base. Write a doc about it..."

    return KnowledgeGap(id=gap_id, question=question, confidence=confidence,
                        retrieval_score=top_retrieval_score, chunk_count=chunk_count,
                        topic_count=topic_count, reason=reason, suggestion=suggestion)
```

A few details worth pausing on:

| Detail | Why it matters | 🚚 Courier |
|--------|---------------|-----------|
| `gap_id = uuid.uuid4()[:8]` | Short hex id is easier to reference in chat responses, URLs, and the markdown ledger | A short ticket number the supervisor can read aloud without spelling out 36 characters |
| `assess_confidence` does NOT save the gap | Pure function, easy to unit test; chat engine decides whether to persist | The auditor scores every trip but only files the paperwork when the dispatcher tells them to |
| `reason` and `suggestion` are human-readable strings | They land verbatim in `unanswered.md` and in the `ChatResponse`; no extra formatter needed | The red flag and the recommended fix are written in plain English so the supervisor doesn't need a glossary |
| `topic_count` is *passed in* but only logged in the reason text — not used in the threshold | Future-proofing: the engine already collects it from the graph expansion, so adding a third signal later is a one-liner | The cartographer's neighbour count is on the audit form already; the auditor just hasn't started weighting it yet |

---

## Where gaps are persisted

```python
self.gaps_path = Path(settings.wiki_output_path) / "gaps"
self.gaps_file = self.gaps_path / "unanswered.md"
self.gaps_jsonl = self.gaps_path / "gaps.jsonl"
```

| File | Format | Read by | 🚚 Courier |
|------|--------|---------|-----------|
| `wiki/gaps/unanswered.md` | Append-only markdown — one section per gap with `🟡 PARTIAL` or `🔴 GAP` heading, the question, the score, the reason, and the suggestion | Humans (open in any markdown viewer) | The wall poster of every flagged trip — the supervisor reads it over coffee and decides which roads to build first |
| `wiki/gaps/gaps.jsonl` | One JSON object per line; full `KnowledgeGap` schema | `list_gaps()`, `gap_summary()`, `resolve_gap()`, the `GET /wiki/gaps` route | The auditor's filing cabinet — same data as the wall poster but shaped for queries and bulk updates |

Both files live inside `wiki_output_path`, which is also the root the
ingestion pipeline scans — meaning your gap log is itself searchable from the
chat once it has been ingested. That is intentional: questions like "what
gaps do you currently have?" can be answered with the same vector path as any
other question.

---

## Resolving a gap

```python
def resolve_gap(self, gap_id: str) -> bool:
    # Read all rows, mark the matching one as resolved + stamp resolved_at,
    # rewrite the JSONL file in place. Returns True if found, False otherwise.
```

The chat engine never calls `resolve_gap` itself — it is invoked by:

- `DELETE /wiki/gaps/{gap_id}` (manual close after you have added docs and
  re-run ingest), and indirectly by
- the operator promoting a candidate via `POST /wiki/candidates/{id}/promote`
  *plus* a follow-up `POST /ingest/run` (the candidate's answer becomes a real
  doc; the next chat for the same question gets `HIGH` and the operator can
  close the ticket).

The function intentionally **does not** delete the gap — it flips
`status: open → resolved` and stamps `resolved_at`. That preserves the
audit trail used by `gap_summary()`.

---

## The summary panel

```python
def gap_summary(self) -> dict:
    all_gaps = self.list_gaps()
    open_gaps = [g for g in all_gaps if g.status == "open"]
    return {
        "total":            len(all_gaps),
        "open":             len(open_gaps),
        "red_gaps":         sum(1 for g in open_gaps if g.confidence == ConfidenceLevel.GAP),
        "yellow_partials":  sum(1 for g in open_gaps if g.confidence == ConfidenceLevel.PARTIAL),
        "resolved":         len(all_gaps) - len(open_gaps),
    }
```

This dict is what `GET /wiki/gaps` returns under `summary`; a UI status panel
or a CI smoke test can compare two snapshots to prove the loop is working
("yesterday: 12 red / 7 yellow; today: 3 red / 4 yellow → progress").

| Field | Meaning | 🚚 Courier |
|-------|---------|-----------|
| `total` | All gaps ever detected (open + resolved) | Lifetime count of red and yellow flags the auditor has ever filed |
| `open` | Currently unresolved gaps | Tickets still pinned to the wall waiting for a road to be built |
| `red_gaps` | Open gaps with `confidence=GAP` (no docs at all) | Trips the courier had to invent — top of the priority list |
| `yellow_partials` | Open gaps with `confidence=PARTIAL` (some docs but thin) | Trips that mostly worked but need a bigger parcel |
| `resolved` | Gaps that were closed (docs added, re-ingested, or candidate promoted + re-ingested) | Tickets the supervisor has crossed off after building the missing road |

---

## Tuning the thresholds

`HIGH_CONFIDENCE_THRESHOLD` and `PARTIAL_CONFIDENCE_THRESHOLD` are module-level
constants, **not** environment variables. Why:

- Different embedding models produce different score distributions; baking the
  values into code keeps the threshold change a code-reviewed event, not an
  `.env` typo.
- The right thresholds depend on how your vector store reports scores — see the
  caveat in the [Chat Engine deep dive](chat-engine-deep-dive.md#step-1--vector-search)
  about `chunks[0].embedding[0]` being a placeholder.

When you swap embedding models (Tier-1 Lab 6) plan on re-tuning these two
constants and writing down your reasoning in the lab notes — same thresholds
across two different embedding spaces is the most common cause of "suddenly
everything is a `GAP`" or "suddenly nothing is a `GAP`."

---

## 🚚 Courier explainer — the auditor with the red marker

The gap detector is the honest auditor sitting at the loading dock. After the
dispatcher hands the courier a parcel, the auditor weighs it: how bright is
the brightest GPS coordinate, how many pages did the courier actually carry,
how many neighbour towns did the cartographer flag? If the brightest hit is
clear and there are at least two pages, green stamp — go deliver, no
paperwork. If the brightest hit is dim or there is only one page, yellow flag,
file a yellow note in the wall drawer and tell the courier to be honest in the
shipping manifest about what's missing. If neither check passes, red flag, file a
red note, and let the supervisor know the courier will be writing this one
from memory — clip a copy of whatever the courier writes onto the supervisor's
clipboard so they can choose to promote it (build the road for real) or
reject it (the courier's invention was wrong).

---

## Self-test questions

1. Why does `assess_confidence` require BOTH `top_score ≥ 0.70` AND
   `chunk_count ≥ 2` for a `HIGH` stamp, instead of just one of the two?
2. Where does `topic_count` get used in the current implementation? Where
   *could* it be used if you wanted a third signal?
3. The function is split into `assess_confidence` (pure) and `save_gap`
   (side-effecting). What testing pattern does that split enable?
4. If you swap from `nomic-embed-text` to `text-embedding-3-small`, which
   constants in this file should you re-tune, and how would you choose the new
   values?
5. Two callers can close a gap: `DELETE /wiki/gaps/{id}` and a candidate
   promotion. What still has to happen between a candidate promotion and the
   next `HIGH` answer for that question?

---

## What to read next

- [Chat Engine Deep Dive](chat-engine-deep-dive.md) — the only caller that
  decides when to persist a gap.
- [Feedback Loop Deep Dive](feedback-loop-deep-dive.md) — how the candidate
  store and verified answers eventually close gaps for good.
- [Wiki Endpoint](../architecture-and-design/api-routes/wiki-endpoint-explained.md) —
  the `GET /wiki/gaps` and `DELETE /wiki/gaps/{id}` routes.
- [Evaluation Framework Deep Dive](evaluation-framework-deep-dive.md) — uses
  the same retrieval signals to compute the report-card metrics.
