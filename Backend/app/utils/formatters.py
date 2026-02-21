from datetime import datetime
from typing import Any, Optional


def format_date(date_str: str, output_format: str = "%d %b %Y") -> str:
    """
    Format a date string to a more readable format.
    
    Args:
        date_str: Input date string
        output_format: Desired output format
    
    Returns:
        Formatted date string
    """
    common_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
    ]
    
    for fmt in common_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime(output_format)
        except ValueError:
            continue
    
    return date_str


def format_fund_name(name: str, max_length: int = 50) -> str:
    """
    Format and truncate fund name for display.
    
    Args:
        name: Full fund name
        max_length: Maximum length before truncation
    
    Returns:
        Formatted fund name
    """
    name = name.strip()
    if len(name) <= max_length:
        return name
    return name[:max_length - 3] + "..."


def format_returns_table(returns: dict[str, str]) -> str:
    """
    Format returns dictionary as a readable table string.
    
    Args:
        returns: Dictionary of period -> return value
    
    Returns:
        Formatted table string
    """
    if not returns:
        return "No return data available"
    
    lines = ["Period | Return"]
    lines.append("-" * 20)
    
    period_order = ["1m", "3m", "6m", "1y", "3y", "5y"]
    for period in period_order:
        if period in returns:
            lines.append(f"{period:6} | {returns[period]}")
    
    return "\n".join(lines)


def format_comparison_table(
    funds: list[dict[str, Any]],
    metrics: list[str]
) -> str:
    """
    Format a comparison table for multiple funds.
    
    Args:
        funds: List of fund data dictionaries
        metrics: List of metric keys to compare
    
    Returns:
        Formatted comparison table
    """
    if not funds:
        return "No funds to compare"
    
    header = "Metric | " + " | ".join(f.get("name", "Fund")[:15] for f in funds)
    separator = "-" * len(header)
    
    lines = [header, separator]
    
    for metric in metrics:
        row = f"{metric:15} | "
        values = []
        for fund in funds:
            value = fund.get(metric, "N/A")
            if isinstance(value, float):
                value = f"{value:.2f}"
            values.append(str(value)[:15])
        row += " | ".join(values)
        lines.append(row)
    
    return "\n".join(lines)


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input for safe processing.
    
    Args:
        text: Raw user input
    
    Returns:
        Sanitized text
    """
    text = text.strip()
    text = " ".join(text.split())
    text = text[:2000]
    return text


def extract_fund_names(query: str) -> list[str]:
    """
    Extract potential fund names from a user query.
    
    Args:
        query: User's query string
    
    Returns:
        List of potential fund names
    """
    common_fund_keywords = [
        "sbi", "hdfc", "icici", "axis", "kotak", "nippon",
        "tata", "dsp", "aditya birla", "uti", "franklin",
        "mirae", "pgim", "invesco", "motilal", "parag parikh",
        "bluechip", "flexi cap", "small cap", "mid cap",
        "large cap", "index", "nifty", "sensex", "elss"
    ]
    
    query_lower = query.lower()
    found = []
    
    for keyword in common_fund_keywords:
        if keyword in query_lower:
            found.append(keyword)
    
    return found


def build_source_citation(name: str, url: str, accessed_at: Optional[datetime] = None) -> dict:
    """
    Build a properly formatted source citation.
    
    Args:
        name: Source name
        url: Source URL
        accessed_at: When the data was accessed
    
    Returns:
        Citation dictionary
    """
    return {
        "name": name,
        "url": url,
        "accessed_at": (accessed_at or datetime.utcnow()).isoformat(),
    }
