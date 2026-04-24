"""API routes — chat."""
from fastapi import APIRouter, Request, HTTPException
from src.models import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    try:
        return await request.app.state.chat_engine.answer(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
