"""
AI-powered fund recommendation endpoint.
Uses 2-step LLM flow for personalized recommendations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.recommendation_service import (
    RecommendationRequest,
    get_recommendations,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommend", tags=["Recommendations"])


class RecommendRequestBody(BaseModel):
    """Request body for fund recommendations."""
    goal: str = Field(..., description="Investment goal: wealth, retirement, tax_saving, house, education, travel")
    risk_tolerance: str = Field(..., description="Risk appetite: conservative, moderate, aggressive")
    investment_horizon: str = Field(..., description="Timeline: short_term, medium_term, long_term")
    monthly_amount: int = Field(default=5000, ge=500, le=1000000, description="Monthly SIP amount in INR")


class FundItem(BaseModel):
    """Fund item in recommendation response."""
    scheme_code: Optional[str] = None
    scheme_name: Optional[str] = None
    nav: Optional[float] = None
    category: Optional[str] = None
    fund_house: Optional[str] = None


class RecommendResponse(BaseModel):
    """Response for fund recommendations."""
    categories: list[str]
    allocation: dict[str, int]
    funds: list[dict]
    ai_insight: str
    reasoning: str


@router.post("", response_model=RecommendResponse)
async def get_fund_recommendations(request: RecommendRequestBody) -> RecommendResponse:
    """
    Get AI-powered fund recommendations based on user preferences.
    
    This endpoint uses a 2-step LLM flow:
    1. LLM analyzes preferences and decides optimal fund categories
    2. Search API fetches matching funds
    3. LLM generates personalized insight based on results
    
    Args:
        request: User's investment preferences
    
    Returns:
        Personalized fund recommendations with AI insight
    """
    logger.info(f"[RECOMMEND API] Request: goal={request.goal}, risk={request.risk_tolerance}, horizon={request.investment_horizon}, amount={request.monthly_amount}")
    
    try:
        # Convert to service request
        service_request = RecommendationRequest(
            goal=request.goal,
            risk_tolerance=request.risk_tolerance,
            investment_horizon=request.investment_horizon,
            monthly_amount=request.monthly_amount,
        )
        
        # Get recommendations
        result = await get_recommendations(service_request)
        
        logger.info(f"[RECOMMEND API] Success: {len(result.funds)} funds, categories={result.categories}")
        
        return RecommendResponse(
            categories=result.categories,
            allocation=result.allocation,
            funds=result.funds,
            ai_insight=result.ai_insight,
            reasoning=result.reasoning,
        )
        
    except Exception as e:
        logger.error(f"[RECOMMEND API] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate recommendations. Please try again."
        )
