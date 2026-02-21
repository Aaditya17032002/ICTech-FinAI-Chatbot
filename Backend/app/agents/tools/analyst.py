import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.utils.calculations import (
    calculate_cagr,
    calculate_absolute_return,
    calculate_sharpe_ratio,
    calculate_standard_deviation,
    format_indian_currency,
    format_percentage,
)

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    """Result from financial analysis."""
    analysis_type: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    interpretation: str = ""
    recommendation: Optional[str] = None


def analyze_returns(
    fund_name: str,
    returns: dict[str, str],
    category_avg: Optional[dict[str, str]] = None
) -> AnalysisResult:
    """
    Analyze fund returns and compare with category average.
    
    Args:
        fund_name: Name of the fund
        returns: Dictionary of period -> return percentage
        category_avg: Optional category average returns for comparison
    
    Returns:
        Analysis result with interpretation
    """
    logger.info(f"Analyzing returns for: {fund_name}")
    
    metrics = {"fund_returns": returns}
    
    interpretation_parts = []
    
    if "1y" in returns:
        return_1y = float(returns["1y"].replace("%", ""))
        if return_1y > 15:
            interpretation_parts.append(f"{fund_name} has delivered strong 1-year returns of {returns['1y']}")
        elif return_1y > 10:
            interpretation_parts.append(f"{fund_name} has delivered moderate 1-year returns of {returns['1y']}")
        else:
            interpretation_parts.append(f"{fund_name} has delivered {returns['1y']} in the past year")
    
    if "3y" in returns:
        interpretation_parts.append(f"3-year return stands at {returns['3y']}")
    
    if category_avg:
        metrics["category_average"] = category_avg
        if "1y" in returns and "1y" in category_avg:
            fund_return = float(returns["1y"].replace("%", ""))
            cat_return = float(category_avg["1y"].replace("%", ""))
            if fund_return > cat_return:
                interpretation_parts.append(f"outperforming category average by {fund_return - cat_return:.2f}%")
            else:
                interpretation_parts.append(f"underperforming category average by {cat_return - fund_return:.2f}%")
    
    return AnalysisResult(
        analysis_type="returns_analysis",
        metrics=metrics,
        interpretation=". ".join(interpretation_parts) + "." if interpretation_parts else "Insufficient data for analysis.",
    )


def calculate_fund_cagr(
    beginning_nav: float,
    ending_nav: float,
    years: float
) -> AnalysisResult:
    """
    Calculate and interpret CAGR for a fund.
    
    Args:
        beginning_nav: NAV at start of period
        ending_nav: Current NAV
        years: Number of years
    
    Returns:
        Analysis result with CAGR interpretation
    """
    logger.info(f"Calculating CAGR: {beginning_nav} -> {ending_nav} over {years} years")
    
    cagr = calculate_cagr(beginning_nav, ending_nav, years)
    
    if cagr is None:
        return AnalysisResult(
            analysis_type="cagr_calculation",
            metrics={},
            interpretation="Unable to calculate CAGR with provided values.",
        )
    
    metrics = {
        "beginning_nav": beginning_nav,
        "ending_nav": ending_nav,
        "years": years,
        "cagr": f"{cagr}%",
    }
    
    if cagr > 15:
        interpretation = f"The fund has delivered an excellent CAGR of {cagr}% over {years} years, significantly beating inflation and fixed deposit returns."
    elif cagr > 12:
        interpretation = f"The fund has delivered a good CAGR of {cagr}% over {years} years, comfortably beating inflation."
    elif cagr > 8:
        interpretation = f"The fund has delivered a moderate CAGR of {cagr}% over {years} years."
    else:
        interpretation = f"The fund has delivered a CAGR of {cagr}% over {years} years, which is relatively modest."
    
    return AnalysisResult(
        analysis_type="cagr_calculation",
        metrics=metrics,
        interpretation=interpretation,
    )


def compare_investments(
    investments: list[dict[str, Any]],
    comparison_metrics: list[str] = None
) -> AnalysisResult:
    """
    Compare multiple investments across various metrics.
    
    Args:
        investments: List of investment data dictionaries
        comparison_metrics: Specific metrics to compare
    
    Returns:
        Comparison analysis result
    """
    if not investments or len(investments) < 2:
        return AnalysisResult(
            analysis_type="comparison",
            metrics={},
            interpretation="Need at least 2 investments to compare.",
        )
    
    logger.info(f"Comparing {len(investments)} investments")
    
    if comparison_metrics is None:
        comparison_metrics = ["1y_return", "3y_return", "nav", "expense_ratio"]
    
    comparison_table = []
    for inv in investments:
        row = {"name": inv.get("name", inv.get("scheme_name", "Unknown"))}
        returns = inv.get("returns", {})
        row["1y_return"] = returns.get("1y", "N/A")
        row["3y_return"] = returns.get("3y", "N/A")
        row["nav"] = inv.get("nav", "N/A")
        comparison_table.append(row)
    
    interpretation_parts = []
    
    best_1y = None
    best_1y_return = float("-inf")
    for inv in investments:
        returns = inv.get("returns", {})
        if "1y" in returns:
            try:
                return_val = float(returns["1y"].replace("%", ""))
                if return_val > best_1y_return:
                    best_1y_return = return_val
                    best_1y = inv.get("name", inv.get("scheme_name"))
            except (ValueError, AttributeError):
                pass
    
    if best_1y:
        interpretation_parts.append(f"{best_1y} leads with the best 1-year return of {best_1y_return}%")
    
    return AnalysisResult(
        analysis_type="comparison",
        metrics={"comparison_table": comparison_table},
        interpretation=". ".join(interpretation_parts) + "." if interpretation_parts else "Comparison data compiled.",
        recommendation="Consider your risk tolerance and investment horizon when choosing between these options.",
    )


def analyze_risk_metrics(
    returns_history: list[float],
    fund_name: str
) -> AnalysisResult:
    """
    Analyze risk metrics for a fund.
    
    Args:
        returns_history: List of periodic returns
        fund_name: Name of the fund
    
    Returns:
        Risk analysis result
    """
    logger.info(f"Analyzing risk metrics for: {fund_name}")
    
    std_dev = calculate_standard_deviation(returns_history)
    sharpe = calculate_sharpe_ratio(returns_history)
    
    metrics = {}
    interpretation_parts = []
    
    if std_dev is not None:
        metrics["standard_deviation"] = f"{std_dev}%"
        if std_dev < 10:
            interpretation_parts.append(f"{fund_name} shows low volatility with a standard deviation of {std_dev}%")
        elif std_dev < 20:
            interpretation_parts.append(f"{fund_name} shows moderate volatility with a standard deviation of {std_dev}%")
        else:
            interpretation_parts.append(f"{fund_name} shows high volatility with a standard deviation of {std_dev}%")
    
    if sharpe is not None:
        metrics["sharpe_ratio"] = sharpe
        if sharpe > 1:
            interpretation_parts.append(f"The Sharpe ratio of {sharpe} indicates good risk-adjusted returns")
        elif sharpe > 0:
            interpretation_parts.append(f"The Sharpe ratio of {sharpe} indicates moderate risk-adjusted returns")
        else:
            interpretation_parts.append(f"The negative Sharpe ratio suggests returns below the risk-free rate")
    
    return AnalysisResult(
        analysis_type="risk_analysis",
        metrics=metrics,
        interpretation=". ".join(interpretation_parts) + "." if interpretation_parts else "Insufficient data for risk analysis.",
    )


def explain_financial_concept(concept: str) -> AnalysisResult:
    """
    Explain a financial concept.
    
    Args:
        concept: The concept to explain (e.g., "CAGR", "NAV", "expense ratio")
    
    Returns:
        Analysis result with explanation
    """
    logger.info(f"Explaining concept: {concept}")
    
    explanations = {
        "cagr": {
            "full_name": "Compound Annual Growth Rate",
            "explanation": "CAGR represents the mean annual growth rate of an investment over a specified period longer than one year. It smooths out the volatility of year-to-year returns to show a single growth rate.",
            "formula": "CAGR = ((Ending Value / Beginning Value) ^ (1/n)) - 1",
            "importance": "CAGR is useful for comparing the performance of different investments over the same time period, as it accounts for the compounding effect.",
        },
        "nav": {
            "full_name": "Net Asset Value",
            "explanation": "NAV is the per-unit market value of a mutual fund. It is calculated by dividing the total value of all assets minus liabilities by the number of outstanding units.",
            "formula": "NAV = (Total Assets - Total Liabilities) / Number of Units",
            "importance": "NAV helps investors understand the current value of their investment and is used to calculate returns.",
        },
        "expense ratio": {
            "full_name": "Total Expense Ratio (TER)",
            "explanation": "The expense ratio is the annual fee charged by a mutual fund to cover operating expenses, management fees, and administrative costs.",
            "importance": "A lower expense ratio means more of your money stays invested. Over long periods, even small differences in expense ratios can significantly impact returns.",
        },
        "aum": {
            "full_name": "Assets Under Management",
            "explanation": "AUM represents the total market value of all investments managed by a mutual fund.",
            "importance": "Higher AUM can indicate investor confidence but may also make it harder for the fund to be agile in its investment decisions.",
        },
        "sip": {
            "full_name": "Systematic Investment Plan",
            "explanation": "SIP is a method of investing a fixed amount regularly in a mutual fund. It helps in rupee cost averaging and building wealth over time.",
            "importance": "SIP helps reduce the impact of market volatility and instills investment discipline.",
        },
    }
    
    concept_lower = concept.lower().strip()
    
    if concept_lower in explanations:
        info = explanations[concept_lower]
        return AnalysisResult(
            analysis_type="concept_explanation",
            metrics=info,
            interpretation=info["explanation"],
        )
    
    return AnalysisResult(
        analysis_type="concept_explanation",
        metrics={},
        interpretation=f"I don't have a detailed explanation for '{concept}'. Please ask about common financial terms like CAGR, NAV, expense ratio, AUM, or SIP.",
    )
