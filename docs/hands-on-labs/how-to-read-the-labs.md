# How to Read the Hands-On Labs

> **Read this BEFORE opening Phase 1 or any other lab file.** It's the missing intro that explains why every knowledge-engine lab seems to talk about the same handful of metrics. Without this mental model the labs feel repetitive; with it, they click in two minutes each.

---

## Table of Contents

- [The thing nobody tells you upfront](#the-thing-nobody-tells-you-upfront)
- [The yardstick: 4 quality metrics + 2 operational](#the-yardstick-4-quality-metrics--2-operational)
- [The 5-question method for reading any lab](#the-5-question-method-for-reading-any-lab)
- [Suggested study order (not phase order)](#suggested-study-order-not-phase-order)
- [Worked example: reading config-tuning Lab 1 (chunk size)](#worked-example-reading-config-tuning-lab-1-chunk-size)
- [Which knob does each lab turn?](#which-knob-does-each-lab-turn)
- [What NOT to do when reading the labs](#what-not-to-do-when-reading-the-labs)

---

## The thing nobody tells you upfront

The 30-odd labs in this repo are **NOT 30 different metrics**. They are **30 different things you change in the system**, all measured against **the same small set of metrics**.

```
                    ┌────────────────────────────────────────┐
                    │   THE YARDSTICK (4 quality + 2 ops)    │
                    │   • graph_completeness                 │
                    │   • retrieval / context_recall         │
                    │   • faithfulness                       │
                    │   • hallucination_rate                 │
                    │   • latency  • cost                    │
                    └────────────────────────────────────────┘
                                     ▲
                                     │  every lab measures against this
                                     │
   ┌────────────┬─────────────┬──────┴──────┬────────────────┬────────────┐
   │ Config L1  │ Config L7   │ Phase-1 L2  │ Phase-2 L7     │ Phase-3 L11│
   │ chunk_size │ reranker    │ graph hops  │ hallucination  │ multi-     │
   │ knob       │ on/off      │ depth       │ rate sweep     │ provider   │
   └────────────┴─────────────┴─────────────┴────────────────┴────────────┘
```

So when Phase-1 Lab 2 reports `graph_completeness=0.78, faithfulness=0.91`, those numbers exist because that's how we tell whether **changing the graph traversal depth from 1 to 2** made the system better or worse than the Phase-1 Lab 1 baseline. **The yardstick doesn't change between labs — only the knob you're turning does.**

🚚 **Courier lens:** the report card always grades the same six subjects — each lab is a different lesson plan for those subjects.

---

## The yardstick: 4 quality metrics + 2 operational

Every lab in this repo reports against these 6 numbers. Memorise them once and the labs halve in size.

| Metric | Range | Higher / Lower better | What it answers | Where it's defined |
| --- | --- | --- | --- | --- |
| **graph_completeness** | 0.0 – 1.0 | higher = better | Did the graph contain enough connected topics to answer? | `src/evaluation/evaluator.py` |
| **retrieval / context_recall** | 0.0 – 1.0 | higher = better | Did the vector + graph retrieve the chunks that contain the ground-truth answer? | `src/evaluation/evaluator.py` |
| **faithfulness** | 0.0 – 1.0 | higher = better | Did the answer use ONLY the retrieved chunks, no invention? | `src/evaluation/evaluator.py` (LLM-as-Judge in Phase 2) |
| **hallucination_rate** | 0.0 – 1.0 | lower = better | Fraction of answers that contain at least one unsupported claim | `src/evaluation/evaluator.py` |
| **latency** | ms | lower = better | End-to-end round-trip per query (includes graph hop + LLM) | logged on every `/chat/` call |
| **cost** | € or $/1k queries | lower = better | LLM + embedding token cost per 1k queries | logged from token counts |

There is also a composite **overall_pass_rate** = fraction of golden questions that score ≥ threshold across the 4 quality metrics. Pass threshold defaults to **0.65** (looser than rag-chatbot because the graph step adds variance).

🚚 **Courier lens:** these six metrics together grade the courier's whole trip — was the map good, the right parcels grabbed, the answer faithful, no invented packages, and how long and costly the round-trip was.

---

## The 5-question method for reading any lab

For every lab in every phase, ask these 5 questions in order. Two minutes per lab.

1. **What knob are we turning?** — `RAG_CHUNK_SIZE`, graph traversal depth, gap-detector threshold, provider, etc. The knob is the entire point of the lab.
2. **What's the hypothesis?** — A one-sentence prediction: "deeper graph traversal should improve completeness but hurt latency." If the lab doesn't state it, write it down before reading the result.
3. **What's the baseline?** — Almost always the previous lab's result OR Phase-1 Lab 1's defaults. The lab is meaningful only as a *delta* against the baseline.
4. **What did the same yardstick measure?** — Check the 6 metrics above. Same metrics every lab. If a lab introduces a new metric (e.g. Phase-2 Lab 7 adds `hallucination_rate`), that's a *replacement* metric for that knob's effect, not a new yardstick.
5. **What's the takeaway?** — When would I turn this knob in production? What would force me to turn it back? That's the answer the lab is really teaching.

If you can answer those 5 in 2 minutes, you understood the lab. If not, re-read steps 1 and 3 — confusion almost always lives there.

---

## Suggested study order (not phase order)

Phase order (config-tuning → 1 → 2 → 3) is fine for reference. For *learning*, this order builds intuition fastest:

| Step | Lab | Why this order |
| --- | --- | --- |
| 1 | **config-tuning Lab 1** Chunk Size | Cheapest knob, biggest first-time-aha — see retrieval move with no other change |
| 2 | **config-tuning Lab 3** top_k | Second simplest knob, same yardstick, builds the "delta vs baseline" reflex |
| 3 | **Phase 1 Lab 1** Vector Search | Lock in the vector-only baseline (no graph yet) |
| 4 | **Phase 1 Lab 2** Graph Traversal | Adds the graph — see completeness move while retrieval stays similar |
| 5 | **Phase 1 Lab 3** GraphRAG Combined | Joins steps 3+4 — proves 1+1 > 2 (or doesn't, that's also a result) |
| 6 | **Phase 2 Lab 4** LLM-as-Judge Faithfulness | Replace heuristic faithfulness with judge model — see how the score shifts |
| 7 | **Phase 2 Lab 7** Hallucination Rate | The honest mirror — pairs with the gap-detector design |
| 8 | **config-tuning Lab 5** System Prompt | Biggest single quality lever — confirms it works on this corpus too |
| 9 | **Phase 3 Lab 9** Feedback Loops | Watch the yardstick *improve over time* as 👍 answers re-enter the corpus |
| 10 | **Phase 3 Lab 11** Multi-Provider | Same yardstick across local / AWS / Azure — provider differences become measurable |
| 11 | **config-tuning Labs 11–13** HNSW sweeps | Operational labs — yardstick shifts to latency vs recall trade-off |
| 12 | **Phase 3 Lab 12** CI/CD Eval Gate | Closes the loop — yardstick *blocks* regressions automatically |

After steps 1–4, **every other lab is "what happens to those 6 numbers when I change X?"** That's the entire game.

---

## Worked example: reading config-tuning Lab 1 (chunk size)

Applying the 5-question method to one of the simplest labs:

| # | Question | Answer for config-tuning Lab 1 |
| --- | --- | --- |
| 1 | What knob? | `RAG_CHUNK_SIZE` swept across 200 / 500 / 1000 characters |
| 2 | Hypothesis? | "Smaller chunks should raise retrieval precision (the right chunk is more focused) but hurt completeness on multi-paragraph answers." |
| 3 | Baseline? | The repo default (`RAG_CHUNK_SIZE=500`). Compare 200 and 1000 against it. |
| 4 | Yardstick? | The same 6 metrics. Look for: retrieval up at 200, completeness up at 1000, latency roughly flat, cost slightly up at 200 (more chunks per ingest). |
| 5 | Takeaway? | Use 200 when answers are short and self-contained (FAQ corpora). Use 1000 when answers span paragraphs (architecture docs). 500 is the sane default that hurts neither. |

When you then read a results row like `chunk_size=200 → retrieval=0.81, completeness=0.62`, those numbers tell you: ✅ the hypothesis held — precision went up, completeness fell. The takeaway writes itself.

🚚 **Courier lens:** small parcel compartments (200) hold one tight idea but multi-step answers need 3 pockets; big pockets (1000) carry the full story but pull in irrelevant text alongside.

---

## Which knob does each lab turn?

The single-sentence summary of every lab. Bookmark this table.

| Phase / Lab | Knob | Yardstick metrics primarily affected | 🚚 Courier |
| --- | --- | --- | --- |
| config-tuning L1 | `RAG_CHUNK_SIZE` (200 / 500 / 1000) | retrieval, completeness | How big each parcel compartment is |
| config-tuning L2 | `RAG_CHUNK_OVERLAP` (0 / 100 / 200) | completeness on cross-section answers | Whether neighbouring pockets share the same paragraph at the seam |
| config-tuning L3 | `RAG_TOP_K` (1 / 3 / 5 / 10) | retrieval, latency, cost | How many parcels the courier carries on each trip |
| config-tuning L4 | `LLM_TEMPERATURE` (0.0 / 0.3 / 0.7) | faithfulness, hallucination_rate | How creative the courier is allowed to be when copying from the parcels |
| config-tuning L5 | `SYSTEM_PROMPT` (strict vs lax) | faithfulness, hallucination_rate | The standing order on the shipping manifest — "ONLY use the parcels" vs "use parcels plus your own judgement" |
| config-tuning L6 | `EMBEDDING_MODEL` (384d / 768d / 1024d) | retrieval, ingestion cost | Resolution of the GPS coordinates — bigger numbers = more precise pickups |
| config-tuning L7 | reranker on/off | retrieval (precision↑), latency (slight↑) | A second-pass quality check at the warehouse before the courier leaves |
| config-tuning L8 | hybrid search on/off (vector + BM25) | retrieval on exact-string queries | GPS plus an old-school keyword radio — useful when the shipping manifest has codes |
| config-tuning L9 | `LLM_MAX_TOKENS` | answer completeness, cost | How much parcels the reply truck can carry back |
| config-tuning L10 | distance metric (cosine / dot / L2) | retrieval | Which ruler measures GPS-closeness |
| config-tuning L11–13 | HNSW M, ef_construction, ef_search | retrieval, latency trade-off | How dense the warehouse's stadium-sign network is, and how many signs the courier checks per trip |
| config-tuning L14 | query rewriting on/off | retrieval | Whether the dispatcher rewrites vague shipping manifests before sending the courier |
| config-tuning L15 | multi-query (n rephrasings) | retrieval, cost | Asking the question N different ways and merging the results |
| config-tuning L16 | metadata filtering | retrieval precision | Pre-sorting the warehouse aisle before the courier enters |
| config-tuning L17 | chunk strategy (recursive / semantic / fixed) | retrieval, completeness | How the post office decides where to cut long letters |
| config-tuning L18 | eval thresholds | overall_pass_rate | How strict the report card's pass mark is |
| config-tuning L19 | LLM-as-Judge model (cheap vs strong) | faithfulness measurement noise | Which examiner grades the report card |
| Phase 1 L1 | vector search baseline (no graph) | retrieval, latency | Courier using GPS only, no paper map |
| Phase 1 L2 | graph traversal depth (1 / 2 hops) | graph_completeness, latency | How many neighbouring towns the courier visits per trip |
| Phase 1 L3 | GraphRAG combined (vector + graph) | retrieval + completeness | GPS plus paper map — the full GraphRAG run |
| Phase 2 L4 | LLM-as-Judge faithfulness | faithfulness measurement quality | A second courier grading the first courier's report card |
| Phase 2 L5 | answer correctness vs ground truth | answer_correctness | Did the parcel actually match the order, not just the address? |
| Phase 2 L6 | completeness scoring | completeness | Did the courier deliver every item on the order, or just some? |
| Phase 2 L7 | hallucination rate sweep | hallucination_rate | How often the courier invents packages |
| Phase 2 L8 | cost per query | $/query | fuel-and-toll cost per delivery, normalised per 1k trips |
| Phase 3 L9 | feedback loops (👍 → wiki, 👎 → eval) | all metrics over time | The trip-debrief desk turning yesterday's lessons into tomorrow's training |
| Phase 3 L10 | graph traversal quality | graph_completeness | Which paper-map roads were actually useful vs decorative |
| Phase 3 L11 | provider sweep (local / AWS / Azure) | all metrics × 3 | Same race, three different depots — who wins on which subject |
| Phase 3 L12 | CI/CD eval gate | regression detection | The robot depot hand refusing to ship a slower or less faithful courier |

---

## What NOT to do when reading the labs

1. **Don't read the labs in isolation.** Every lab is a *delta vs a baseline*. Without the baseline (usually the previous lab or Phase-1 Lab 1), the numbers mean nothing.
2. **Don't compare absolute numbers across providers without checking the same lab number.** Local Phase-1 Lab 2 vs AWS Phase-2 Lab 7 is a meaningless comparison — different knobs, different metrics.
3. **Don't treat the yardstick as the answer.** A lab that shows `retrieval=0.92` is only "good" if the baseline was `0.85`. Always look at the delta.
4. **Don't skip the hypothesis.** If you read the result before forming a prediction, you'll just nod at whatever number you see and learn nothing. Always do step 2 before step 4.
5. **Don't memorise the lab numbers.** Memorise the yardstick + the knob list. The numbers will change next time you re-run; the structure won't.

🚚 **Final courier wisdom:** every lab is one of these two questions, dressed up differently:

- "I changed knob X. Is the report card better or worse?" (Phase 1 L1–L3, Phase 2 L4–L7, config-tuning L1–L10)
- "I changed knob X. Did the courier now refuse / crash / answer slower / spend more?" (config-tuning L11–L17, Phase 3 L11–L12)

Once you see that, the labs stop feeling repetitive and start feeling like the controlled experiments they actually are — which is the entire point of doing them.
