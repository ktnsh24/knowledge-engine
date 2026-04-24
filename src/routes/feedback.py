"""API routes — feedback."""
from fastapi import APIRouter, Request
from src.models import FeedbackSignal

router = APIRouter()


@router.post("/")
async def submit_feedback(request: Request, body: FeedbackSignal):
    result = await request.app.state.feedback_proc.process(body)
    return result
