"""API routes — wiki, gaps, and candidates."""
from fastapi import APIRouter, Request, HTTPException
from src.models import WikiPage
from src.chat.gap_detector import GapDetector
from src.chat.candidate_store import CandidateStore

router = APIRouter()
_gap_detector = GapDetector()
_candidate_store = CandidateStore()


@router.post("/rebuild")
async def rebuild_wiki(request: Request):
    try:
        pages = await request.app.state.wiki_gen.generate_all()
        return {"status": "ok", "pages_generated": len(pages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topics")
async def list_topics(request: Request):
    topics = await request.app.state.graph_store.get_all_topics()
    return {"topics": [t.model_dump() for t in topics]}


@router.get("/graph")
async def get_graph(request: Request):
    graph = await request.app.state.graph_store.get_full_graph()
    return graph.model_dump()


# ── Gaps ──────────────────────────────────────────────────────────────────────

@router.get("/gaps")
async def list_gaps(status: str | None = None):
    """
    List all detected knowledge gaps.
    ?status=open|resolved — optional filter.

    🚚 These are the broken roads — questions the courier couldn't answer from your docs.
    """
    gaps = _gap_detector.list_gaps(status_filter=status)
    summary = _gap_detector.gap_summary()
    return {
        "summary": summary,
        "gaps": [g.model_dump(mode="json") for g in gaps],
    }


@router.delete("/gaps/{gap_id}")
async def resolve_gap(gap_id: str):
    """Mark a gap as resolved after adding docs and re-ingesting."""
    found = _gap_detector.resolve_gap(gap_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Gap '{gap_id}' not found")
    return {"status": "resolved", "gap_id": gap_id}


# ── Candidates ────────────────────────────────────────────────────────────────

@router.get("/candidates")
async def list_candidates(status: str | None = "pending"):
    """
    List LLM-generated candidate answers awaiting human review.

    These are answers to GAP questions — generated from LLM training knowledge,
    NOT from your docs. Review each one:
      POST /wiki/candidates/{id}/promote  → adds to verified-answers.md → next ingest = grounded
      POST /wiki/candidates/{id}/discard  → removes, gap stays open

    🚚 These are the courier's off-road notes: 'I found a path through the wilderness.
    Check if it's safe before we make it an official road.'
    """
    candidates = _candidate_store.list_candidates(status_filter=status)
    summary = _candidate_store.summary()
    return {
        "summary": summary,
        "candidates": [c.model_dump(mode="json") for c in candidates],
    }


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: str):
    """
    Promote a candidate answer to verified knowledge.

    Writes Q&A to wiki/feedback/verified-answers.md.
    Next time POST /ingest/run is called, this becomes part of the knowledge base.
    Future identical questions will be answered from your docs (not LLM training).
    """
    candidate = await _candidate_store.promote(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found or not pending"
        )
    return {
        "status": "promoted",
        "candidate_id": candidate_id,
        "next_step": "Run POST /ingest/run to absorb this answer into the knowledge base",
    }


@router.post("/candidates/{candidate_id}/discard")
async def discard_candidate(candidate_id: str):
    """Discard a candidate answer — it was wrong. Gap stays open."""
    candidate = await _candidate_store.discard(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found or not pending"
        )
    return {"status": "discarded", "candidate_id": candidate_id}
