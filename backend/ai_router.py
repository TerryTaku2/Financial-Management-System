"""
AI Router — /api/ai/analyse endpoints
Streaming and non-streaming Claude-powered analysis for the City of Harare FMS.
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from database import User
from ai_service import analyse, analyse_stream

router = APIRouter(prefix="/api/ai", tags=["AI Analysis"])


class AnalysisRequest(BaseModel):
    query: str


class AnalysisResponse(BaseModel):
    query:    str
    analysis: str
    model:    str = "claude-sonnet-4-6"


@router.post("/analyse", response_model=AnalysisResponse)
def run_analysis(
    req: AnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Non-streaming analysis — returns full response once complete."""
    try:
        result = analyse(req.query, db)
        return AnalysisResponse(query=req.query, analysis=result)
    except ValueError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")


@router.post("/analyse/stream")
def run_analysis_stream(
    req: AnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Streaming analysis — yields tokens as they arrive from Claude."""
    return StreamingResponse(
        analyse_stream(req.query, db),
        media_type="text/plain",
    )


@router.get("/health")
def ai_health(current_user: User = Depends(get_current_user)):
    """Check AI router reachability and API key status."""
    key_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip()) and \
              os.getenv("ANTHROPIC_API_KEY") != "your-api-key-here"
    return {
        "status":  "ok" if key_set else "missing_api_key",
        "api_key": "configured" if key_set else "NOT SET — add to .env",
        "model":   "claude-sonnet-4-6",
    }
