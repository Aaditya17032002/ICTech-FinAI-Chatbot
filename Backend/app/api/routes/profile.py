import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.domain import UserProfile, RiskTolerance, InvestmentHorizon, InvestmentGoal
from app.models.schemas import UserProfileRequest, UserProfileResponse
from app.repositories.cache_repository import get_cache_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["User Profile"])

_profiles: dict[str, UserProfile] = {}


def _get_or_create_profile(user_id: Optional[str], request: Optional[UserProfileRequest] = None) -> UserProfile:
    """Get existing profile or create a new one."""
    cache = get_cache_repository()
    
    if user_id and user_id in _profiles:
        return _profiles[user_id]
    
    if user_id:
        cached = cache.get(f"profile_{user_id}")
        if cached:
            profile = UserProfile(**cached)
            _profiles[user_id] = profile
            return profile
    
    new_id = user_id or str(uuid.uuid4())
    profile = UserProfile(
        user_id=new_id,
        name=request.name if request else None,
        age=request.age if request else None,
        risk_tolerance=request.risk_tolerance if request else RiskTolerance.MODERATE,
        investment_horizon=request.investment_horizon if request else InvestmentHorizon.MEDIUM_TERM,
        investment_goals=request.investment_goals if request else [InvestmentGoal.WEALTH_CREATION],
        monthly_investment_capacity=request.monthly_investment_capacity if request else None,
    )
    _profiles[new_id] = profile
    return profile


def _save_profile(profile: UserProfile):
    """Save profile to cache."""
    cache = get_cache_repository()
    profile.updated_at = datetime.utcnow()
    cache.set(f"profile_{profile.user_id}", profile.model_dump(mode="json"), ttl_seconds=86400 * 30)


@router.post("", response_model=UserProfileResponse)
async def create_profile(request: UserProfileRequest) -> UserProfileResponse:
    """
    Create a new user profile for personalized investment recommendations.
    
    The profile helps tailor advice based on:
    - Risk tolerance (conservative/moderate/aggressive)
    - Investment horizon (short/medium/long term)
    - Investment goals (wealth creation, retirement, tax saving, etc.)
    """
    logger.info("Creating new user profile")
    
    profile = _get_or_create_profile(None, request)
    _save_profile(profile)
    
    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        age=profile.age,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon=profile.investment_horizon,
        investment_goals=profile.investment_goals,
        monthly_investment_capacity=profile.monthly_investment_capacity,
        recommended_categories=profile.get_recommended_categories(),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_profile(user_id: str) -> UserProfileResponse:
    """Get an existing user profile by ID."""
    logger.info(f"Getting profile for user: {user_id}")
    
    profile = _get_or_create_profile(user_id)
    
    if profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        age=profile.age,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon=profile.investment_horizon,
        investment_goals=profile.investment_goals,
        monthly_investment_capacity=profile.monthly_investment_capacity,
        recommended_categories=profile.get_recommended_categories(),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put("/{user_id}", response_model=UserProfileResponse)
async def update_profile(user_id: str, request: UserProfileRequest) -> UserProfileResponse:
    """Update an existing user profile."""
    logger.info(f"Updating profile for user: {user_id}")
    
    profile = _get_or_create_profile(user_id)
    
    if profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.name = request.name
    profile.age = request.age
    profile.risk_tolerance = request.risk_tolerance
    profile.investment_horizon = request.investment_horizon
    profile.investment_goals = request.investment_goals
    profile.monthly_investment_capacity = request.monthly_investment_capacity
    
    _save_profile(profile)
    
    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        age=profile.age,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon=profile.investment_horizon,
        investment_goals=profile.investment_goals,
        monthly_investment_capacity=profile.monthly_investment_capacity,
        recommended_categories=profile.get_recommended_categories(),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.delete("/{user_id}")
async def delete_profile(user_id: str) -> dict:
    """Delete a user profile."""
    logger.info(f"Deleting profile for user: {user_id}")
    
    cache = get_cache_repository()
    
    if user_id in _profiles:
        del _profiles[user_id]
    
    cache.delete(f"profile_{user_id}")
    
    return {"message": "Profile deleted successfully"}


@router.get("/{user_id}/recommendations")
async def get_profile_recommendations(user_id: str) -> dict:
    """
    Get personalized fund recommendations based on user profile.
    
    Returns recommended fund categories and investment strategies.
    """
    logger.info(f"Getting recommendations for user: {user_id}")
    
    profile = _get_or_create_profile(user_id)
    
    if profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    recommendations = {
        "user_id": user_id,
        "risk_profile": profile.risk_tolerance.value,
        "recommended_categories": profile.get_recommended_categories(),
        "investment_strategy": _get_investment_strategy(profile),
        "asset_allocation": _get_asset_allocation(profile),
        "tips": _get_personalized_tips(profile),
    }
    
    return recommendations


def _get_investment_strategy(profile: UserProfile) -> str:
    """Get investment strategy based on profile."""
    if profile.risk_tolerance == RiskTolerance.CONSERVATIVE:
        return "Focus on capital preservation with debt funds and liquid funds. Consider balanced hybrid funds for some equity exposure with lower volatility."
    elif profile.risk_tolerance == RiskTolerance.MODERATE:
        return "Balanced approach with a mix of large-cap equity and debt funds. Index funds and flexi-cap funds offer good diversification."
    else:
        return "Growth-oriented strategy with mid-cap and small-cap funds. Higher risk but potential for better long-term returns. Consider sectoral funds for specific themes."


def _get_asset_allocation(profile: UserProfile) -> dict:
    """Get recommended asset allocation based on profile."""
    if profile.risk_tolerance == RiskTolerance.CONSERVATIVE:
        return {"equity": 30, "debt": 60, "gold": 10}
    elif profile.risk_tolerance == RiskTolerance.MODERATE:
        return {"equity": 60, "debt": 30, "gold": 10}
    else:
        return {"equity": 80, "debt": 15, "gold": 5}


def _get_personalized_tips(profile: UserProfile) -> list[str]:
    """Get personalized investment tips based on profile."""
    tips = []
    
    if profile.age and profile.age < 30:
        tips.append("At your age, you can afford to take more risk. Consider increasing equity allocation.")
    elif profile.age and profile.age > 50:
        tips.append("As you approach retirement, gradually shift towards debt funds for stability.")
    
    if InvestmentGoal.TAX_SAVING in profile.investment_goals:
        tips.append("ELSS funds offer tax benefits under Section 80C with a 3-year lock-in period.")
    
    if InvestmentGoal.RETIREMENT in profile.investment_goals:
        tips.append("Consider NPS (National Pension System) for additional tax benefits and retirement corpus.")
    
    if profile.investment_horizon == InvestmentHorizon.LONG_TERM:
        tips.append("For long-term goals, SIP in equity funds can help average out market volatility.")
    
    if profile.monthly_investment_capacity and profile.monthly_investment_capacity >= 10000:
        tips.append("With your investment capacity, consider diversifying across 3-4 funds in different categories.")
    
    if not tips:
        tips.append("Start with a SIP in a diversified equity fund and review your portfolio quarterly.")
    
    return tips


def get_profile_for_session(user_id: Optional[str]) -> Optional[UserProfile]:
    """Helper function to get profile for chat session."""
    if not user_id:
        return None
    return _get_or_create_profile(user_id)
