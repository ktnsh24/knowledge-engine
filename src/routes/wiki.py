"""API routes — wiki."""
from fastapi import APIRouter, Request, HTTPException
from src.models import WikiPage

router = APIRouter()


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
