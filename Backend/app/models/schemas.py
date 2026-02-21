from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .agent_outputs import InvestmentResponse
from .domain import RiskTolerance, InvestmentHorizon, InvestmentGoal


class UserProfileRequest(BaseModel):
    """Request model for creating/updating user profile."""
    name: Optional[str] = Field(default=None, max_length=100)
    age: Optional[int] = Field(default=None, ge=18, le=100)
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM_TERM
    investment_goals: list[InvestmentGoal] = Field(default_factory=lambda: [InvestmentGoal.WEALTH_CREATION])
    monthly_investment_capacity: Optional[float] = Field(default=None, ge=500)


class UserProfileResponse(BaseModel):
    """Response model for user profile."""
    user_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    risk_tolerance: RiskTolerance
    investment_horizon: InvestmentHorizon
    investment_goals: list[InvestmentGoal]
    monthly_investment_capacity: Optional[float] = None
    recommended_categories: list[str]
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(min_length=1, max_length=2000, description="User's question or query")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation continuity")
    user_profile: Optional[UserProfileRequest] = Field(default=None, description="Optional user profile for personalized advice")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str = Field(description="Session ID for this conversation")
    response: InvestmentResponse = Field(description="Structured investment response")
    processing_time_ms: int = Field(description="Time taken to process the request in milliseconds")
    cached: bool = Field(default=False, description="Whether this response was served from cache")


class StreamToken(BaseModel):
    """Single token in streaming response."""
    token: str


class StreamComplete(BaseModel):
    """Final message in streaming response."""
    response: InvestmentResponse


class FundSearchRequest(BaseModel):
    """Request model for fund search."""
    q: str = Field(min_length=1, max_length=200, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")


class FundSearchResult(BaseModel):
    """Single fund in search results."""
    scheme_code: str
    scheme_name: str
    category: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None


class FundSearchResponse(BaseModel):
    """Response model for fund search."""
    results: list[FundSearchResult]
    total: int


class FundDetailResponse(BaseModel):
    """Detailed fund information."""
    scheme_code: str
    scheme_name: str
    fund_house: Optional[str] = None
    category: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    returns: dict[str, str] = Field(default_factory=dict)
    aum: Optional[str] = None
    expense_ratio: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
