from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskTolerance(str, Enum):
    """User's risk tolerance level."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InvestmentHorizon(str, Enum):
    """User's investment time horizon."""
    SHORT_TERM = "short_term"  # < 1 year
    MEDIUM_TERM = "medium_term"  # 1-5 years
    LONG_TERM = "long_term"  # > 5 years


class InvestmentGoal(str, Enum):
    """User's primary investment goal."""
    WEALTH_CREATION = "wealth_creation"
    RETIREMENT = "retirement"
    TAX_SAVING = "tax_saving"
    EMERGENCY_FUND = "emergency_fund"
    CHILD_EDUCATION = "child_education"
    HOME_PURCHASE = "home_purchase"
    REGULAR_INCOME = "regular_income"


class UserProfile(BaseModel):
    """User's investment profile for personalized recommendations."""
    user_id: str
    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=18, le=100)
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM_TERM
    investment_goals: list[InvestmentGoal] = Field(default_factory=lambda: [InvestmentGoal.WEALTH_CREATION])
    monthly_investment_capacity: Optional[float] = Field(default=None, ge=500)
    existing_investments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_recommended_categories(self) -> list[str]:
        """Get recommended fund categories based on profile."""
        categories = []
        
        if self.risk_tolerance == RiskTolerance.CONSERVATIVE:
            categories.extend(["debt", "liquid", "short term", "conservative hybrid"])
        elif self.risk_tolerance == RiskTolerance.MODERATE:
            categories.extend(["large cap", "flexi cap", "balanced hybrid", "index"])
        else:
            categories.extend(["mid cap", "small cap", "flexi cap", "sectoral"])
        
        if InvestmentGoal.TAX_SAVING in self.investment_goals:
            categories.append("elss")
        if InvestmentGoal.REGULAR_INCOME in self.investment_goals:
            categories.append("dividend yield")
        if InvestmentGoal.RETIREMENT in self.investment_goals:
            categories.append("balanced advantage")
        
        return list(set(categories))

    def get_profile_summary(self) -> str:
        """Get a text summary of the user profile for the AI."""
        age_text = f"Age: {self.age}" if self.age else "Age: Not specified"
        goals = ", ".join([g.value.replace("_", " ").title() for g in self.investment_goals])
        capacity_text = f"₹{self.monthly_investment_capacity:,.0f}" if self.monthly_investment_capacity else "Not specified"
        
        return f"""
User Profile:
- {age_text}
- Risk Tolerance: {self.risk_tolerance.value.title()}
- Investment Horizon: {self.investment_horizon.value.replace("_", " ").title()}
- Goals: {goals}
- Monthly Investment Capacity: {capacity_text}
- Recommended Categories: {", ".join(self.get_recommended_categories())}
"""


class FundCategory(str, Enum):
    EQUITY_LARGE_CAP = "Equity - Large Cap"
    EQUITY_MID_CAP = "Equity - Mid Cap"
    EQUITY_SMALL_CAP = "Equity - Small Cap"
    EQUITY_MULTI_CAP = "Equity - Multi Cap"
    EQUITY_FLEXI_CAP = "Equity - Flexi Cap"
    EQUITY_ELSS = "Equity - ELSS"
    EQUITY_INDEX = "Equity - Index Fund"
    DEBT_SHORT_TERM = "Debt - Short Term"
    DEBT_LONG_TERM = "Debt - Long Term"
    DEBT_LIQUID = "Debt - Liquid"
    HYBRID_BALANCED = "Hybrid - Balanced"
    HYBRID_AGGRESSIVE = "Hybrid - Aggressive"
    OTHER = "Other"


class MutualFund(BaseModel):
    scheme_code: str
    scheme_name: str
    fund_house: Optional[str] = None
    category: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    

class MutualFundDetail(MutualFund):
    returns: Optional[dict[str, str]] = Field(default_factory=dict)
    aum: Optional[str] = None
    expense_ratio: Optional[str] = None
    min_investment: Optional[str] = None
    exit_load: Optional[str] = None


class StockData(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None


class HistoricalNAV(BaseModel):
    date: str
    nav: float


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationSession(BaseModel):
    session_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    user_profile: Optional[UserProfile] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
