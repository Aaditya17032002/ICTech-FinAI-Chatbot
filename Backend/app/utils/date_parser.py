"""
Date parsing utilities for handling time-based investment queries.
Parses natural language date references like "last year", "2024-2025", "march 2024 to april 2025".
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


@dataclass
class DateRange:
    """Represents a date range for analysis."""
    start_date: datetime
    end_date: datetime
    period_label: str
    
    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days
    
    @property
    def months(self) -> int:
        return max(1, self.days // 30)
    
    @property
    def years(self) -> float:
        return round(self.days / 365, 2)


def get_current_date() -> datetime:
    """Get current date - centralized for consistency."""
    return datetime.now()


def get_current_date_str() -> str:
    """Get current date as formatted string."""
    return get_current_date().strftime("%Y-%m-%d")


def get_current_date_display() -> str:
    """Get current date in display format."""
    return get_current_date().strftime("%B %d, %Y")


def parse_date_query(query: str) -> Optional[DateRange]:
    """
    Parse a user query to extract date range information.
    
    Handles formats like:
    - "last year", "past year", "1 year"
    - "last 6 months", "past 3 months"
    - "2024-2025", "2024 to 2025"
    - "march 2024 to april 2025"
    - "since january 2024"
    - "from 2024"
    - "ytd", "year to date"
    
    Returns:
        DateRange object or None if no date reference found
    """
    query_lower = query.lower()
    today = get_current_date()
    
    # Pattern: "last/past N years/months/days"
    relative_pattern = r'(?:last|past|previous)\s+(\d+)\s*(year|month|week|day)s?'
    match = re.search(relative_pattern, query_lower)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if unit == "year":
            start = today - timedelta(days=num * 365)
            label = f"Last {num} year{'s' if num > 1 else ''}"
        elif unit == "month":
            start = today - timedelta(days=num * 30)
            label = f"Last {num} month{'s' if num > 1 else ''}"
        elif unit == "week":
            start = today - timedelta(weeks=num)
            label = f"Last {num} week{'s' if num > 1 else ''}"
        else:
            start = today - timedelta(days=num)
            label = f"Last {num} day{'s' if num > 1 else ''}"
        
        return DateRange(start_date=start, end_date=today, period_label=label)
    
    # Pattern: "last year", "this year", "past year"
    if re.search(r'\b(?:last|past|previous)\s+year\b', query_lower):
        start = today - timedelta(days=365)
        return DateRange(start_date=start, end_date=today, period_label="Last 1 year")
    
    if re.search(r'\bthis\s+year\b', query_lower):
        start = datetime(today.year, 1, 1)
        return DateRange(start_date=start, end_date=today, period_label=f"Year {today.year} (YTD)")
    
    # Pattern: "ytd", "year to date"
    if re.search(r'\b(?:ytd|year\s+to\s+date)\b', query_lower):
        start = datetime(today.year, 1, 1)
        return DateRange(start_date=start, end_date=today, period_label=f"Year to Date ({today.year})")
    
    # Pattern: "2024-2025" or "2024 to 2025" or "2024-25"
    year_range_pattern = r'\b(20\d{2})\s*[-–to]+\s*(20\d{2}|2\d)\b'
    match = re.search(year_range_pattern, query_lower)
    if match:
        start_year = int(match.group(1))
        end_year_str = match.group(2)
        end_year = int(end_year_str) if len(end_year_str) == 4 else int(f"20{end_year_str}")
        
        start = datetime(start_year, 1, 1)
        end = datetime(end_year, 12, 31)
        if end > today:
            end = today
        
        return DateRange(start_date=start, end_date=end, period_label=f"{start_year}-{end_year}")
    
    # Pattern: "month year to month year" (e.g., "march 2024 to april 2025")
    month_range_pattern = r'(\w+)\s+(20\d{2})\s*(?:to|-|–)\s*(\w+)\s+(20\d{2})'
    match = re.search(month_range_pattern, query_lower)
    if match:
        start_month_str = match.group(1)
        start_year = int(match.group(2))
        end_month_str = match.group(3)
        end_year = int(match.group(4))
        
        start_month = MONTH_MAP.get(start_month_str)
        end_month = MONTH_MAP.get(end_month_str)
        
        if start_month and end_month:
            start = datetime(start_year, start_month, 1)
            # End of the month
            if end_month == 12:
                end = datetime(end_year, 12, 31)
            else:
                end = datetime(end_year, end_month + 1, 1) - timedelta(days=1)
            
            if end > today:
                end = today
            
            label = f"{start_month_str.capitalize()} {start_year} to {end_month_str.capitalize()} {end_year}"
            return DateRange(start_date=start, end_date=end, period_label=label)
    
    # Pattern: "since month year" or "from month year"
    since_pattern = r'(?:since|from)\s+(\w+)\s+(20\d{2})'
    match = re.search(since_pattern, query_lower)
    if match:
        month_str = match.group(1)
        year = int(match.group(2))
        month = MONTH_MAP.get(month_str)
        
        if month:
            start = datetime(year, month, 1)
            label = f"Since {month_str.capitalize()} {year}"
            return DateRange(start_date=start, end_date=today, period_label=label)
    
    # Pattern: "since year" or "from year"
    since_year_pattern = r'(?:since|from)\s+(20\d{2})\b'
    match = re.search(since_year_pattern, query_lower)
    if match:
        year = int(match.group(1))
        start = datetime(year, 1, 1)
        return DateRange(start_date=start, end_date=today, period_label=f"Since {year}")
    
    # Pattern: "in year" (single year)
    in_year_pattern = r'\bin\s+(20\d{2})\b'
    match = re.search(in_year_pattern, query_lower)
    if match:
        year = int(match.group(1))
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        if end > today:
            end = today
        return DateRange(start_date=start, end_date=end, period_label=f"Year {year}")
    
    # Default patterns for common queries
    if any(kw in query_lower for kw in ["1y", "1 y", "one year", "1-year"]):
        start = today - timedelta(days=365)
        return DateRange(start_date=start, end_date=today, period_label="Last 1 year")
    
    if any(kw in query_lower for kw in ["3y", "3 y", "three year", "3-year"]):
        start = today - timedelta(days=3 * 365)
        return DateRange(start_date=start, end_date=today, period_label="Last 3 years")
    
    if any(kw in query_lower for kw in ["5y", "5 y", "five year", "5-year"]):
        start = today - timedelta(days=5 * 365)
        return DateRange(start_date=start, end_date=today, period_label="Last 5 years")
    
    if any(kw in query_lower for kw in ["6m", "6 m", "six month", "6-month"]):
        start = today - timedelta(days=180)
        return DateRange(start_date=start, end_date=today, period_label="Last 6 months")
    
    return None


def get_period_key_for_range(date_range: DateRange) -> str:
    """
    Convert a date range to the appropriate return period key (1m, 3m, 6m, 1y, 3y, 5y).
    """
    days = date_range.days
    
    if days <= 45:
        return "1m"
    elif days <= 100:
        return "3m"
    elif days <= 200:
        return "6m"
    elif days <= 400:
        return "1y"
    elif days <= 1200:
        return "3y"
    else:
        return "5y"


def format_date_context(date_range: Optional[DateRange] = None) -> str:
    """
    Format date context information for the AI prompt.
    """
    today = get_current_date()
    
    context = f"""## Current Date Context
- Today's Date: {today.strftime('%B %d, %Y')} ({today.strftime('%Y-%m-%d')})
- Current Year: {today.year}
- Current Month: {today.strftime('%B')}
"""
    
    if date_range:
        context += f"""
## User's Requested Time Period
- Period: {date_range.period_label}
- From: {date_range.start_date.strftime('%B %d, %Y')}
- To: {date_range.end_date.strftime('%B %d, %Y')}
- Duration: {date_range.days} days (~{date_range.months} months / {date_range.years} years)
- Relevant Return Period: {get_period_key_for_range(date_range)}
"""
    
    return context
