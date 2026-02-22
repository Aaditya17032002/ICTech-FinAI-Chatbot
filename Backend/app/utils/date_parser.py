"""
Dynamic date parsing utilities using LLM for intelligent date extraction.
Parses natural language date references like "last year", "2024-2025", "march 2024 to april 2025".
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from groq import Groq

logger = logging.getLogger(__name__)


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


# Tool definition for the LLM
DATE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_date_range",
        "description": "Extract date range from a user query about investments or funds. Call this when the user mentions any time period.",
        "parameters": {
            "type": "object",
            "properties": {
                "has_date_reference": {
                    "type": "boolean",
                    "description": "Whether the query contains any date or time period reference"
                },
                "start_year": {
                    "type": "integer",
                    "description": "Start year (e.g., 2024). Use current year minus duration for relative periods like 'last year'."
                },
                "start_month": {
                    "type": "integer",
                    "description": "Start month (1-12). Use 1 if not specified."
                },
                "start_day": {
                    "type": "integer",
                    "description": "Start day (1-31). Use 1 if not specified."
                },
                "end_year": {
                    "type": "integer",
                    "description": "End year. Use current year for open-ended periods like 'since 2024'."
                },
                "end_month": {
                    "type": "integer",
                    "description": "End month (1-12). Use current month for open-ended periods."
                },
                "end_day": {
                    "type": "integer",
                    "description": "End day (1-31). Use current day for open-ended periods."
                },
                "period_label": {
                    "type": "string",
                    "description": "Human-readable label for the period (e.g., 'Last 1 year', 'March 2024 to April 2025', 'Since January 2024')"
                },
                "period_type": {
                    "type": "string",
                    "enum": ["relative", "absolute", "ytd", "since", "none"],
                    "description": "Type of period: 'relative' for 'last X months', 'absolute' for specific dates, 'ytd' for year-to-date, 'since' for open-ended, 'none' if no date reference"
                }
            },
            "required": ["has_date_reference"]
        }
    }
}


async def parse_date_query_llm(query: str) -> Optional[DateRange]:
    """
    Use LLM to intelligently parse date references from user query.
    
    This is more flexible than regex and can handle:
    - Natural language: "funds that did well last year"
    - Complex ranges: "between march 2024 and april 2025"
    - Relative periods: "in the past 6 months"
    - Implicit dates: "top performers of 2024"
    - Contextual: "since the market crash in 2020"
    
    Returns:
        DateRange object or None if no date reference found
    """
    today = get_current_date()
    
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        system_prompt = f"""You are a date extraction assistant. Today's date is {today.strftime('%B %d, %Y')} ({today.strftime('%Y-%m-%d')}).

Your job is to extract date/time period references from investment-related queries.

Examples:
- "best funds last year" → relative period, 1 year back from today
- "top performers from march 2024 to april 2025" → absolute period with specific months
- "funds since 2024" → since period, from Jan 2024 to today
- "ytd returns" → year-to-date, from Jan 1 of current year to today
- "best funds to invest" → no date reference (has_date_reference: false)
- "performance in 2024" → absolute period, full year 2024
- "last 6 months" → relative period, 6 months back from today
- "Q1 2024" → absolute period, Jan-Mar 2024
- "first half of 2024" → absolute period, Jan-Jun 2024

Always calculate actual dates based on today being {today.strftime('%Y-%m-%d')}."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Fast, cheap model for this simple task
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract date range from this query: \"{query}\""}
            ],
            tools=[DATE_EXTRACTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_date_range"}},
            temperature=0,
            max_tokens=200,
        )
        
        # Extract the tool call result
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            
            logger.info(f"[DATE PARSER LLM] Extracted: {args}")
            
            if not args.get("has_date_reference", False):
                return None
            
            # Build DateRange from extracted parameters
            try:
                start_date = datetime(
                    args.get("start_year", today.year),
                    args.get("start_month", 1),
                    args.get("start_day", 1)
                )
                
                end_date = datetime(
                    args.get("end_year", today.year),
                    args.get("end_month", today.month),
                    args.get("end_day", today.day)
                )
                
                # Cap end date to today if in future
                if end_date > today:
                    end_date = today
                
                # Ensure start is before end
                if start_date > end_date:
                    start_date, end_date = end_date, start_date
                
                period_label = args.get("period_label", f"{start_date.strftime('%b %Y')} to {end_date.strftime('%b %Y')}")
                
                return DateRange(
                    start_date=start_date,
                    end_date=end_date,
                    period_label=period_label
                )
            except (ValueError, TypeError) as e:
                logger.error(f"[DATE PARSER LLM] Error building date range: {e}")
                return None
        
        return None
        
    except Exception as e:
        logger.error(f"[DATE PARSER LLM] Error: {e}")
        # Fall back to regex parser
        return parse_date_query_regex(query)


def parse_date_query_regex(query: str) -> Optional[DateRange]:
    """
    Fallback regex-based date parser for when LLM is unavailable.
    """
    query_lower = query.lower()
    today = get_current_date()
    
    MONTH_MAP = {
        "january": 1, "jan": 1, "february": 2, "feb": 2,
        "march": 3, "mar": 3, "april": 4, "apr": 4,
        "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
        "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10, "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    
    import re
    
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
    
    # Pattern: "last year", "past year"
    if re.search(r'\b(?:last|past|previous)\s+year\b', query_lower):
        start = today - timedelta(days=365)
        return DateRange(start_date=start, end_date=today, period_label="Last 1 year")
    
    # Pattern: "this year"
    if re.search(r'\bthis\s+year\b', query_lower):
        start = datetime(today.year, 1, 1)
        return DateRange(start_date=start, end_date=today, period_label=f"Year {today.year} (YTD)")
    
    # Pattern: "ytd", "year to date"
    if re.search(r'\b(?:ytd|year\s+to\s+date)\b', query_lower):
        start = datetime(today.year, 1, 1)
        return DateRange(start_date=start, end_date=today, period_label=f"Year to Date ({today.year})")
    
    # Pattern: "2024-2025" or "2024 to 2025"
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
    
    # Pattern: "month year to month year"
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
    
    # Pattern: "in year"
    in_year_pattern = r'\bin\s+(20\d{2})\b'
    match = re.search(in_year_pattern, query_lower)
    if match:
        year = int(match.group(1))
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        if end > today:
            end = today
        return DateRange(start_date=start, end_date=end, period_label=f"Year {year}")
    
    return None


def parse_date_query(query: str) -> Optional[DateRange]:
    """
    Parse date query - tries LLM first, falls back to regex.
    This is a sync wrapper for the async LLM function.
    """
    import asyncio
    
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, use regex fallback (can't await in sync context)
            logger.info("[DATE PARSER] Using regex fallback (event loop running)")
            return parse_date_query_regex(query)
        else:
            return loop.run_until_complete(parse_date_query_llm(query))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(parse_date_query_llm(query))
    except Exception as e:
        logger.error(f"[DATE PARSER] Error: {e}, falling back to regex")
        return parse_date_query_regex(query)


async def parse_date_query_async(query: str) -> Optional[DateRange]:
    """
    Async version of parse_date_query for use in async contexts.
    """
    return await parse_date_query_llm(query)


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
    elif days <= 550:  # ~1.5 years
        return "1y"
    elif days <= 1400:  # ~4 years
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
