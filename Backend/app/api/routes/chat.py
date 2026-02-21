import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from groq import Groq

from app.models.schemas import ChatRequest, ChatResponse
from app.models.domain import UserProfile, RiskTolerance, InvestmentHorizon, InvestmentGoal
from app.services.chat_service import get_chat_service
from app.agents.investment_agent import run_agent, run_agent_stream
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])
settings = get_settings()


def _create_user_profile_from_request(request: ChatRequest) -> Optional[UserProfile]:
    """Create a UserProfile from the chat request if profile data is provided."""
    if not request.user_profile:
        return None
    
    return UserProfile(
        user_id="temp_" + (request.session_id or "anonymous"),
        name=request.user_profile.name,
        age=request.user_profile.age,
        risk_tolerance=request.user_profile.risk_tolerance,
        investment_horizon=request.user_profile.investment_horizon,
        investment_goals=request.user_profile.investment_goals,
        monthly_investment_capacity=request.user_profile.monthly_investment_capacity,
    )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the investment advisor chatbot.
    
    This endpoint processes the user's query using AI-powered analysis
    and returns a structured response with data-backed insights.
    
    Optionally include a user_profile for personalized recommendations based on:
    - Risk tolerance (conservative/moderate/aggressive)
    - Investment horizon (short/medium/long term)
    - Investment goals (wealth creation, retirement, tax saving, etc.)
    
    Args:
        request: Chat request containing the message, optional session_id, and optional user_profile
    
    Returns:
        Structured response with explanation, data points, sources, and disclaimer
    """
    logger.info(f"Chat request: {request.message[:100]}...")
    
    try:
        chat_service = get_chat_service()
        user_profile = _create_user_profile_from_request(request)
        
        if user_profile:
            logger.info(f"User profile: {user_profile.risk_tolerance.value}, {user_profile.investment_horizon.value}")
        
        async def agent_runner(message: str, history: list[dict], profile: Optional[UserProfile] = None):
            return await run_agent(message, history, profile)
        
        response = await chat_service.process_message(request, agent_runner, user_profile)
        return response
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again."
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Send a message and receive a streaming response.
    
    This endpoint uses Server-Sent Events (SSE) to stream the response
    token by token for a better user experience.
    
    Args:
        request: Chat request containing the message and optional session_id
    
    Returns:
        SSE stream with tokens and final structured response
    """
    logger.info(f"Chat stream request: {request.message[:100]}...")
    
    try:
        chat_service = get_chat_service()
        
        async def stream_generator():
            async for chunk in chat_service.process_message_stream(
                request,
                run_agent_stream
            ):
                yield chunk
        
        return EventSourceResponse(
            stream_generator(),
            media_type="text/event-stream",
        )
    
    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request."
        )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str) -> dict:
    """
    Clear a conversation session.
    
    Args:
        session_id: The session ID to clear
    
    Returns:
        Confirmation of session clearance
    """
    logger.info(f"Clearing session: {session_id}")
    
    try:
        chat_service = get_chat_service()
        chat_service.clear_session(session_id)
        
        return {
            "status": "success",
            "message": f"Session {session_id} cleared",
        }
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error clearing session"
        )


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str) -> dict:
    """
    Get conversation history for a session.
    
    Args:
        session_id: The session ID
    
    Returns:
        List of messages in the conversation
    """
    logger.info(f"Getting history for session: {session_id}")
    
    try:
        chat_service = get_chat_service()
        history = chat_service.get_conversation_history(session_id)
        
        return {
            "session_id": session_id,
            "messages": history,
            "total": len(history),
        }
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching session history"
        )


@router.get("/test-groq")
async def test_groq_api() -> dict:
    """
    Test endpoint to directly call Groq API and measure response time.
    Tests each model individually.
    """
    results = {}
    
    try:
        client = Groq(api_key=settings.groq_api_key)
        
        models_to_test = [
            ("llama-3.3-70b-versatile", "Fast general model"),
            ("llama-3.1-8b-instant", "Ultra fast model"),
        ]
        
        for model_id, description in models_to_test:
            start = time.time()
            logger.info(f"[TEST] Testing model: {model_id}")
            
            try:
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "user", "content": "Say 'Hello' in one word."}
                    ],
                    max_tokens=10,
                    temperature=0,
                )
                elapsed = time.time() - start
                results[model_id] = {
                    "status": "success",
                    "response": response.choices[0].message.content,
                    "time_seconds": round(elapsed, 2),
                    "description": description,
                }
                logger.info(f"[TEST] {model_id} completed in {elapsed:.2f}s")
            except Exception as e:
                elapsed = time.time() - start
                results[model_id] = {
                    "status": "error",
                    "error": str(e),
                    "time_seconds": round(elapsed, 2),
                    "description": description,
                }
                logger.error(f"[TEST] {model_id} failed: {e}")
        
        return {
            "api_key_prefix": settings.groq_api_key[:15] + "...",
            "results": results,
        }
        
    except Exception as e:
        logger.error(f"[TEST] Groq test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
