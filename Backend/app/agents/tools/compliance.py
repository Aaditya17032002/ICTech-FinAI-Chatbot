import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.agent_outputs import DataPoint, Source, InvestmentResponse

logger = logging.getLogger(__name__)


STANDARD_RISK_DISCLAIMER = """Mutual fund investments are subject to market risks. Please read all scheme-related documents carefully before investing. Past performance is not indicative of future returns. The information provided is for educational purposes only and should not be considered as personalized financial advice. Please consult a qualified financial advisor before making investment decisions."""

SEBI_DISCLAIMER = """This information is provided for educational purposes only. Investment in securities market are subject to market risks. Read all the related documents carefully before investing. Registration granted by SEBI and certification from NISM in no way guarantee performance of the intermediary or provide any assurance of returns to investors."""


class ComplianceCheckResult(BaseModel):
    """Result from compliance check."""
    is_compliant: bool = True
    has_disclaimer: bool = False
    has_sources: bool = False
    has_data_points: bool = False
    missing_elements: list[str] = Field(default_factory=list)
    risk_disclaimer: str = STANDARD_RISK_DISCLAIMER


def check_response_compliance(
    explanation: str,
    data_points: list[DataPoint],
    sources: list[Source],
) -> ComplianceCheckResult:
    """
    Check if a response meets compliance requirements.
    
    Args:
        explanation: The response explanation text
        data_points: List of data points in the response
        sources: List of sources cited
    
    Returns:
        Compliance check result
    """
    logger.info("Checking response compliance")
    
    result = ComplianceCheckResult()
    missing = []
    
    if not explanation or len(explanation) < 10:
        missing.append("meaningful explanation")
        result.is_compliant = False
    
    if not data_points:
        missing.append("data points with specific metrics")
    else:
        result.has_data_points = True
    
    if not sources:
        missing.append("source citations")
    else:
        result.has_sources = True
    
    result.missing_elements = missing
    result.is_compliant = len(missing) == 0
    
    return result


def add_risk_disclaimer(
    response: InvestmentResponse,
    include_sebi: bool = False
) -> InvestmentResponse:
    """
    Ensure response has appropriate risk disclaimer.
    
    Args:
        response: The investment response to check
        include_sebi: Whether to include SEBI-specific disclaimer
    
    Returns:
        Response with risk disclaimer added/updated
    """
    logger.info("Adding risk disclaimer to response")
    
    disclaimer = STANDARD_RISK_DISCLAIMER
    if include_sebi:
        disclaimer = f"{STANDARD_RISK_DISCLAIMER}\n\n{SEBI_DISCLAIMER}"
    
    response.risk_disclaimer = disclaimer
    return response


def ensure_source_citations(
    response: InvestmentResponse,
    default_sources: Optional[list[dict]] = None
) -> InvestmentResponse:
    """
    Ensure response has source citations.
    
    Args:
        response: The investment response
        default_sources: Default sources to add if none present
    
    Returns:
        Response with sources ensured
    """
    logger.info("Ensuring source citations")
    
    if not response.sources and default_sources:
        for src in default_sources:
            response.sources.append(Source(
                name=src.get("name", "Unknown"),
                url=src.get("url", ""),
                accessed_at=datetime.utcnow(),
            ))
    
    return response


def validate_data_freshness(
    data_points: list[DataPoint],
    max_age_days: int = 7
) -> tuple[bool, list[str]]:
    """
    Validate that data points are recent enough.
    
    Args:
        data_points: List of data points to validate
        max_age_days: Maximum acceptable age in days
    
    Returns:
        Tuple of (is_fresh, list of stale data point names)
    """
    logger.info("Validating data freshness")
    
    stale_points = []
    today = datetime.utcnow().date()
    
    for dp in data_points:
        try:
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"]:
                try:
                    data_date = datetime.strptime(dp.as_of_date, fmt).date()
                    age = (today - data_date).days
                    if age > max_age_days:
                        stale_points.append(dp.metric)
                    break
                except ValueError:
                    continue
        except Exception:
            pass
    
    return len(stale_points) == 0, stale_points


def calculate_confidence_score(
    has_data_points: bool,
    has_sources: bool,
    data_fresh: bool,
    query_matched: bool = True
) -> float:
    """
    Calculate confidence score for a response.
    
    Args:
        has_data_points: Whether response has data points
        has_sources: Whether response has source citations
        data_fresh: Whether data is recent
        query_matched: Whether query was understood correctly
    
    Returns:
        Confidence score between 0 and 1
    """
    score = 0.4
    
    if has_data_points:
        score += 0.2
    if has_sources:
        score += 0.2
    if data_fresh:
        score += 0.1
    if query_matched:
        score += 0.1
    
    return min(score, 1.0)


def finalize_response(
    explanation: str,
    data_points: list[DataPoint],
    sources: list[Source],
) -> InvestmentResponse:
    """
    Finalize and validate an investment response.
    
    Args:
        explanation: Response explanation
        data_points: List of data points
        sources: List of sources
    
    Returns:
        Finalized, compliant InvestmentResponse
    """
    logger.info("Finalizing investment response")
    
    compliance = check_response_compliance(explanation, data_points, sources)
    
    data_fresh, _ = validate_data_freshness(data_points)
    
    confidence = calculate_confidence_score(
        has_data_points=compliance.has_data_points,
        has_sources=compliance.has_sources,
        data_fresh=data_fresh,
    )
    
    response = InvestmentResponse(
        explanation=explanation,
        data_points=data_points,
        sources=sources,
        risk_disclaimer=compliance.risk_disclaimer,
        confidence_score=confidence,
    )
    
    return response
