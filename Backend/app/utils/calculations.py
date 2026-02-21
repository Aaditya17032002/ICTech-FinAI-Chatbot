from typing import Optional


def calculate_cagr(
    beginning_value: float,
    ending_value: float,
    years: float
) -> Optional[float]:
    """
    Calculate Compound Annual Growth Rate (CAGR).
    
    Formula: CAGR = ((Ending Value / Beginning Value) ^ (1/n)) - 1
    
    Args:
        beginning_value: Initial investment value
        ending_value: Final investment value
        years: Number of years
    
    Returns:
        CAGR as a percentage, or None if calculation is not possible
    """
    if beginning_value <= 0 or ending_value <= 0 or years <= 0:
        return None
    
    try:
        cagr = ((ending_value / beginning_value) ** (1 / years)) - 1
        return round(cagr * 100, 2)
    except (ZeroDivisionError, ValueError):
        return None


def calculate_absolute_return(
    beginning_value: float,
    ending_value: float
) -> Optional[float]:
    """
    Calculate absolute return percentage.
    
    Formula: ((Ending - Beginning) / Beginning) * 100
    
    Args:
        beginning_value: Initial value
        ending_value: Final value
    
    Returns:
        Absolute return as a percentage
    """
    if beginning_value <= 0:
        return None
    
    return round(((ending_value - beginning_value) / beginning_value) * 100, 2)


def calculate_sip_returns(
    monthly_investment: float,
    final_value: float,
    months: int
) -> dict[str, float]:
    """
    Calculate SIP returns metrics.
    
    Args:
        monthly_investment: Monthly SIP amount
        final_value: Current value of investment
        months: Number of months invested
    
    Returns:
        Dictionary with total_invested, current_value, absolute_return, xirr_approx
    """
    total_invested = monthly_investment * months
    absolute_return = calculate_absolute_return(total_invested, final_value)
    
    return {
        "total_invested": total_invested,
        "current_value": final_value,
        "absolute_return": absolute_return or 0,
        "gain_loss": final_value - total_invested,
    }


def calculate_standard_deviation(returns: list[float]) -> Optional[float]:
    """
    Calculate standard deviation of returns (volatility measure).
    
    Args:
        returns: List of periodic returns
    
    Returns:
        Standard deviation as a percentage
    """
    if not returns or len(returns) < 2:
        return None
    
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    
    return round(variance ** 0.5, 2)


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 6.0
) -> Optional[float]:
    """
    Calculate Sharpe Ratio (risk-adjusted return).
    
    Formula: (Average Return - Risk Free Rate) / Standard Deviation
    
    Args:
        returns: List of periodic returns
        risk_free_rate: Annual risk-free rate (default 6% for India)
    
    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return None
    
    avg_return = sum(returns) / len(returns)
    std_dev = calculate_standard_deviation(returns)
    
    if std_dev is None or std_dev == 0:
        return None
    
    return round((avg_return - risk_free_rate) / std_dev, 2)


def format_indian_currency(amount: float) -> str:
    """
    Format amount in Indian currency notation (lakhs, crores).
    
    Args:
        amount: Amount to format
    
    Returns:
        Formatted string with appropriate suffix
    """
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} Cr"
    elif amount >= 100_000:
        return f"₹{amount / 100_000:.2f} L"
    elif amount >= 1000:
        return f"₹{amount / 1000:.2f} K"
    else:
        return f"₹{amount:.2f}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format a value as percentage string."""
    return f"{value:.{decimal_places}f}%"
