from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DataPoint(BaseModel):
    """A single data metric with its value and date."""
    metric: str = Field(description="Name of the metric, e.g., '1Y Return', 'CAGR', 'NAV'")
    value: str = Field(description="The metric value, e.g., '15.2%', '₹45.67'")
    as_of_date: str = Field(description="Date when this data was recorded")


class Source(BaseModel):
    """Citation for data source."""
    name: str = Field(description="Name of the data source, e.g., 'AMFI India'")
    url: str = Field(description="URL of the data source")
    accessed_at: datetime = Field(default_factory=datetime.utcnow)


class InvestmentResponse(BaseModel):
    """Structured response from the investment advisor agent."""
    explanation: str = Field(default="", description="Comprehensive markdown-formatted analysis answering the user's query. Include verdict, detailed analysis, comparisons, and actionable recommendations. Use headers (##), bullet points, and tables for structure. Minimum 200 words for analysis questions.")
    data_points: list[DataPoint] = Field(
        default_factory=list,
        description="List of relevant data metrics supporting the answer"
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Citations for all data used in the response"
    )
    risk_disclaimer: str = Field(
        default="Mutual fund investments are subject to market risks. Please read all scheme-related documents carefully before investing. Past performance is not indicative of future returns.",
        description="Mandatory risk disclaimer"
    )
    confidence_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score based on data freshness and availability (0-1)"
    )


class FundComparisonResult(BaseModel):
    """Result of comparing two or more funds."""
    funds_compared: list[str]
    comparison_metrics: list[DataPoint]
    recommendation: Optional[str] = None
    analysis: str


class MarketAnalysis(BaseModel):
    """Analysis of current market conditions."""
    market_sentiment: str
    key_indicators: list[DataPoint]
    analysis: str
    outlook: str
