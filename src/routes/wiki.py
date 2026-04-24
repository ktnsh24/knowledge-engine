"""API routes — wiki."""
from fastapi import APIRouter, Request, HTTPException
from src.models import WikiPage
from src.chat.gap_detector import GapDetector

router = APIRouter()
_gap_detector = GapDetector()


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


@router.get("/gaps")
async def list_gaps(status: str | None = None):
    """
    List all detected knowledge gaps.

    - status=open   → only unresolved gaps
    - status=resolved → only resolved gaps
    - (no filter)   → all gaps

    🫏 These are the broken roads on the map — questions the donkey
    couldn't answer from your docs. Fix them by adding documentation.
    """
    gaps = _gap_detector.list_gaps(status_filter=status)
    summary = _gap_detector.gap_summary()
    return {
        "summary": summary,
        "gaps": [g.model_dump(mode="json") for g in gaps],
    }


@router.delete("/gaps/{gap_id}")
async def resolve_gap(gap_id: str):
    """
    Mark a gap as resolved.
    Call this after you've added docs covering the gap and re-run ingestion.
    """
    found = _gap_detector.resolve_gap(gap_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Gap '{gap_id}' not found")
    return {"status": "resolved", "gap_id": gap_id}
