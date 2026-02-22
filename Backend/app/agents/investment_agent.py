import logging
import os
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel

from app.config import get_settings
from app.models.agent_outputs import Source, InvestmentResponse, DataPoint
from app.models.domain import UserProfile
from app.agents.prompts import INVESTMENT_ADVISOR_SYSTEM_PROMPT
from app.agents.tools.compliance import STANDARD_RISK_DISCLAIMER
from app.agents.tools.researcher import (
    research_mutual_fund,
    research_stock,
    research_market_overview,
    search_funds_by_category,
)
from app.utils.date_parser import (
    parse_date_query,
    format_date_context,
    get_current_date_str,
    get_current_date_display,
    DateRange,
    get_period_key_for_range,
)

logger = logging.getLogger(__name__)


class AgentDependencies(BaseModel):
    """Dependencies injected into the agent."""
    conversation_history: list[dict[str, str]] = []
    user_query: str = ""
    fetched_data: dict[str, Any] = {}
    user_profile_summary: str = ""
    date_context: str = ""
    requested_period: str = ""


settings = get_settings()
os.environ["GROQ_API_KEY"] = settings.groq_api_key

FAST_MODEL = "llama-3.3-70b-versatile"
REASONING_MODEL = "qwen/qwen3-32b"

logger.info(f"Initializing models: {FAST_MODEL}, {REASONING_MODEL}")

fast_model = GroqModel(FAST_MODEL)
reasoning_model = GroqModel(REASONING_MODEL)

ENHANCED_SYSTEM_PROMPT = INVESTMENT_ADVISOR_SYSTEM_PROMPT + """

## Multi-Step Analysis Process
When answering questions, follow this structured approach:

1. **Data Gathering**: First identify what data is needed to answer the question properly
2. **Analysis**: Analyze the gathered data with relevant metrics (NAV, returns, risk)
3. **Comparison**: If comparing funds/stocks, create a structured comparison TABLE
4. **Recommendation**: Provide actionable insights based on the analysis

## Data Available
You have access to real-time data from:
- AMFI India for mutual fund NAVs and returns (fetched live)
- Yahoo Finance for stock prices and market indices (fetched live)

## IMPORTANT: Date Handling
- The current date is provided in the context - USE IT
- If user asks about "last year", "2024-2025", etc., the date range is calculated and provided
- NEVER say "as of my training data" or "as of August 2024" - use the actual dates from the data
- All data shown is fetched in real-time at the moment of the query

## CRITICAL: Response Structure
Your response MUST follow this structure:

1. Start with a brief introduction (1-2 sentences)
2. Use ## headers for each major section
3. List each fund/stock with ### subheaders
4. Include a comparison table if multiple items
5. End with key takeaways as bullet points

NEVER write a wall of text. ALWAYS use:
- Headers (## and ###)
- Bullet points (-)
- Numbered lists (1. 2. 3.)
- Tables for comparisons
- Line breaks between sections
"""

fast_agent = Agent(
    fast_model,
    deps_type=AgentDependencies,
    output_type=InvestmentResponse,
    system_prompt=ENHANCED_SYSTEM_PROMPT,
)

reasoning_agent = Agent(
    reasoning_model,
    deps_type=AgentDependencies,
    output_type=InvestmentResponse,
    system_prompt=ENHANCED_SYSTEM_PROMPT + """

Think step-by-step for complex calculations like CAGR, risk assessment, and fund comparisons.
When comparing investments, analyze each option thoroughly before making recommendations.
Use chain-of-thought reasoning to explain your analysis process.""",
)


def classify_query(query: str) -> str:
    """Classify the query to determine which agent to use."""
    query_lower = query.lower()
    
    reasoning_keywords = [
        "compare", "vs", "versus", "better", "best",
        "cagr", "calculate", "return", "risk",
        "should i invest", "good time", "recommend",
        "analysis", "analyze", "evaluate", "which",
        "top performing", "highest return"
    ]
    
    for keyword in reasoning_keywords:
        if keyword in query_lower:
            return "reasoning"
    
    return "fast"


def extract_fund_names(query: str) -> list[str]:
    """Extract potential fund names from the query."""
    common_funds = [
        "sbi bluechip", "hdfc top 100", "axis bluechip", "icici prudential",
        "mirae asset", "kotak", "nippon", "aditya birla", "dsp", "uti",
        "tata", "franklin", "invesco", "motilal oswal", "parag parikh",
        "quant", "canara robeco", "bandhan", "edelweiss", "pgim"
    ]
    
    query_lower = query.lower()
    found = []
    
    for fund in common_funds:
        if fund in query_lower:
            found.append(fund)
    
    return found


def extract_categories(query: str) -> list[str]:
    """Extract fund categories from the query."""
    categories = {
        "large cap": ["large cap", "largecap", "large-cap", "bluechip", "blue chip"],
        "mid cap": ["mid cap", "midcap", "mid-cap"],
        "small cap": ["small cap", "smallcap", "small-cap"],
        "index": ["index", "nifty", "sensex"],
        "elss": ["elss", "tax saving", "tax saver"],
        "debt": ["debt", "bond", "liquid", "money market"],
        "hybrid": ["hybrid", "balanced", "aggressive"],
        "flexi cap": ["flexi cap", "flexicap", "multi cap", "multicap"],
    }
    
    query_lower = query.lower()
    found = []
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in query_lower:
                found.append(category)
                break
    
    return found


async def fetch_relevant_data(query: str, date_range: Optional[DateRange] = None) -> dict[str, Any]:
    """
    Multi-step data fetching based on query analysis.
    This is the key to providing detailed, data-driven responses.
    
    Args:
        query: User's question
        date_range: Optional parsed date range from the query
    """
    data = {
        "funds": [],
        "stocks": [],
        "market": None,
        "categories": [],
        "date_range": date_range,
        "fetched_at": get_current_date_str(),
    }
    
    logger.info(f"[DATA FETCH] Analyzing query: {query[:100]}...")
    if date_range:
        logger.info(f"[DATA FETCH] Date range requested: {date_range.period_label}")
    
    fund_names = extract_fund_names(query)
    categories = extract_categories(query)
    
    if fund_names:
        logger.info(f"[DATA FETCH] Found fund names: {fund_names}")
        for name in fund_names[:3]:
            try:
                results = research_mutual_fund(name)
                if results:
                    data["funds"].extend(results[:2])
            except Exception as e:
                logger.error(f"Error fetching fund {name}: {e}")
    
    if categories:
        logger.info(f"[DATA FETCH] Found categories: {categories}")
        for category in categories[:2]:
            try:
                results = search_funds_by_category(category, limit=5)
                if results:
                    data["categories"].append({
                        "category": category,
                        "funds": results
                    })
            except Exception as e:
                logger.error(f"Error fetching category {category}: {e}")
    
    if not fund_names and not categories:
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["top", "best", "performing", "recommend"]):
            try:
                results = search_funds_by_category("large cap", limit=5)
                if results:
                    data["categories"].append({
                        "category": "large cap",
                        "funds": results
                    })
            except Exception as e:
                logger.error(f"Error fetching default category: {e}")
    
    query_lower = query.lower()
    if any(kw in query_lower for kw in ["market", "nifty", "sensex", "index", "overview"]):
        try:
            data["market"] = research_market_overview()
        except Exception as e:
            logger.error(f"Error fetching market overview: {e}")
    
    stock_keywords = ["reliance", "tcs", "infosys", "hdfc bank", "icici bank"]
    for stock in stock_keywords:
        if stock in query_lower:
            try:
                result = research_stock(stock.upper().replace(" ", ""))
                if result:
                    data["stocks"].append(result)
            except Exception as e:
                logger.error(f"Error fetching stock {stock}: {e}")
    
    logger.info(f"[DATA FETCH] Fetched {len(data['funds'])} funds, {len(data['stocks'])} stocks")
    return data


def format_data_for_prompt(data: dict[str, Any], date_range: Optional[DateRange] = None) -> str:
    """Format fetched data into a structured prompt section."""
    sections = []
    
    # Add date context at the top
    sections.append(format_date_context(date_range))
    
    # Add data fetch timestamp
    fetched_at = data.get("fetched_at", get_current_date_str())
    sections.append(f"**Data fetched at:** {fetched_at}\n")
    
    if date_range:
        period_key = get_period_key_for_range(date_range)
        sections.append(f"**Requested analysis period:** {date_range.period_label} (use {period_key} returns for comparison)\n")
    
    if data.get("funds"):
        sections.append("## Real-Time Fund Data (Live from AMFI India):")
        for fund in data["funds"]:
            nav_date = fund.nav_date or fetched_at
            source_url = getattr(fund, 'source_url', '') or f"https://www.amfiindia.com/net-asset-value-details?SchemeCode={fund.scheme_code}"
            sections.append(f"""
**{fund.scheme_name}** (Code: {fund.scheme_code})
- NAV: ₹{fund.nav} (as of {nav_date})
- Category: {fund.category or 'N/A'}
- Fund House: {fund.fund_house or 'N/A'}
- Returns: {', '.join([f'{k}: {v}' for k, v in fund.returns.items()]) if fund.returns else 'N/A'}
- Source: [AMFI India - {fund.scheme_code}]({source_url})
""")
    
    if data.get("categories"):
        for cat_data in data["categories"]:
            sections.append(f"\n## Top {cat_data['category'].title()} Funds (Live Data):")
            for i, fund in enumerate(cat_data["funds"][:5], 1):
                nav_date = fund.nav_date if hasattr(fund, 'nav_date') and fund.nav_date else fetched_at
                source_url = getattr(fund, 'source_url', '') or f"https://www.amfiindia.com/net-asset-value-details?SchemeCode={fund.scheme_code}"
                sections.append(f"{i}. **{fund.scheme_name}** (Code: {fund.scheme_code})")
                sections.append(f"   - NAV: ₹{fund.nav} (as of {nav_date}), Returns: {fund.returns}")
                sections.append(f"   - [View on AMFI]({source_url})")
    
    if data.get("market"):
        sections.append("\n## Market Overview (Live from Yahoo Finance):")
        market_data = data["market"]
        source_urls = getattr(market_data, 'source_urls', {}) or {}
        for index, values in market_data.indices.items():
            url = source_urls.get(index, f"https://finance.yahoo.com/quote/^NSEI/")
            sections.append(f"- {index}: {values.get('value', 'N/A')} ({values.get('change_percent', 0):+.2f}%) - [View on Yahoo Finance]({url})")
    
    if data.get("stocks"):
        sections.append("\n## Stock Data (Live from Yahoo Finance):")
        for stock in data["stocks"]:
            source_url = getattr(stock, 'source_url', '') or f"https://finance.yahoo.com/quote/{stock.symbol}/"
            sections.append(f"- {stock.symbol}: ₹{stock.current_price} ({stock.change_percent:+.2f}%) - [View on Yahoo Finance]({source_url})")
    
    return "\n".join(sections) if sections else ""


def create_data_points_from_data(data: dict[str, Any]) -> list[DataPoint]:
    """Create structured data points from fetched data."""
    data_points = []
    
    if data.get("funds"):
        for fund in data["funds"][:4]:
            if fund.nav:
                data_points.append(DataPoint(
                    metric=f"{fund.scheme_name[:30]}... NAV",
                    value=f"₹{fund.nav}",
                    as_of_date=fund.nav_date or datetime.utcnow().strftime("%Y-%m-%d"),
                ))
            if fund.returns:
                for period, value in list(fund.returns.items())[:1]:
                    data_points.append(DataPoint(
                        metric=f"{fund.scheme_name[:20]}... {period} Return",
                        value=value,
                        as_of_date=fund.nav_date or datetime.utcnow().strftime("%Y-%m-%d"),
                    ))
    
    if data.get("categories"):
        for cat_data in data["categories"][:1]:
            top_funds = cat_data["funds"][:3]
            for fund in top_funds:
                if fund.returns:
                    one_year = fund.returns.get("1Y", fund.returns.get("1y", "N/A"))
                    data_points.append(DataPoint(
                        metric=f"{fund.scheme_name[:25]}...",
                        value=f"1Y: {one_year}",
                        as_of_date=fund.nav_date or datetime.utcnow().strftime("%Y-%m-%d"),
                    ))
    
    return data_points[:6]


def create_sources_from_data(data: dict[str, Any]) -> list[Source]:
    """Create source citations from fetched data with exact URLs."""
    sources = []
    now = datetime.utcnow()
    added_urls = set()
    
    # Add specific fund sources
    if data.get("funds"):
        for fund in data["funds"][:3]:
            url = getattr(fund, 'source_url', '') or f"https://www.amfiindia.com/net-asset-value-details?SchemeCode={fund.scheme_code}"
            if url not in added_urls:
                sources.append(Source(
                    name=f"AMFI India - {fund.scheme_name[:40]}",
                    url=url,
                    accessed_at=now,
                ))
                added_urls.add(url)
    
    # Add category fund sources
    if data.get("categories"):
        for cat_data in data["categories"][:1]:
            for fund in cat_data["funds"][:2]:
                url = getattr(fund, 'source_url', '') or f"https://www.amfiindia.com/net-asset-value-details?SchemeCode={fund.scheme_code}"
                if url not in added_urls:
                    sources.append(Source(
                        name=f"AMFI India - {fund.scheme_name[:40]}",
                        url=url,
                        accessed_at=now,
                    ))
                    added_urls.add(url)
    
    # Add stock sources
    if data.get("stocks"):
        for stock in data["stocks"][:3]:
            url = getattr(stock, 'source_url', '') or f"https://finance.yahoo.com/quote/{stock.symbol}/"
            if url not in added_urls:
                sources.append(Source(
                    name=f"Yahoo Finance - {stock.name or stock.symbol}",
                    url=url,
                    accessed_at=now,
                ))
                added_urls.add(url)
    
    # Add market index sources
    if data.get("market"):
        market_data = data["market"]
        source_urls = getattr(market_data, 'source_urls', {}) or {}
        for index_name, url in list(source_urls.items())[:2]:
            if url not in added_urls:
                sources.append(Source(
                    name=f"Yahoo Finance - {index_name}",
                    url=url,
                    accessed_at=now,
                ))
                added_urls.add(url)
    
    # Fallback if no specific sources
    if not sources:
        sources.append(Source(
            name="AMFI India - NAV Data",
            url="https://www.amfiindia.com/net-asset-value-details",
            accessed_at=now,
        ))
    
    return sources


async def run_agent(
    user_message: str,
    conversation_history: list[dict[str, str]] = None,
    user_profile: Optional[UserProfile] = None
) -> InvestmentResponse:
    """
    Run the investment advisor agent with multi-step data fetching.
    
    Args:
        user_message: The user's question
        conversation_history: Previous conversation messages
        user_profile: Optional user profile for personalized advice
    
    Returns:
        Structured investment response
    """
    start_time = time.time()
    
    # Parse date range from query
    date_range = parse_date_query(user_message)
    if date_range:
        logger.info(f"[AGENT] Detected date range: {date_range.period_label}")
    
    logger.info(f"[AGENT] Step 1: Fetching relevant data...")
    fetched_data = await fetch_relevant_data(user_message, date_range)
    
    if user_profile:
        for category in user_profile.get_recommended_categories()[:2]:
            if not any(cat["category"] == category for cat in fetched_data.get("categories", [])):
                try:
                    results = search_funds_by_category(category, limit=3)
                    if results:
                        fetched_data["categories"].append({
                            "category": category,
                            "funds": results
                        })
                except Exception as e:
                    logger.error(f"Error fetching profile category {category}: {e}")
    
    query_type = classify_query(user_message)
    selected_agent = reasoning_agent if query_type == "reasoning" else fast_agent
    model_name = REASONING_MODEL if query_type == "reasoning" else FAST_MODEL
    
    logger.info(f"[AGENT] Step 2: Processing with {model_name}...")
    
    profile_summary = user_profile.get_profile_summary() if user_profile else ""
    
    # Generate date context
    date_context = format_date_context(date_range)
    requested_period = date_range.period_label if date_range else ""
    
    deps = AgentDependencies(
        user_query=user_message,
        conversation_history=conversation_history or [],
        fetched_data=fetched_data,
        user_profile_summary=profile_summary,
        date_context=date_context,
        requested_period=requested_period,
    )
    
    try:
        data_context = format_data_for_prompt(fetched_data, date_range)
        
        prompt_parts = []
        
        # Always add date context first
        prompt_parts.append(date_context)
        prompt_parts.append(f"\n**IMPORTANT:** Today is {get_current_date_display()}. All data below is fetched LIVE. Do not use your training data for any financial figures.\n")
        
        if profile_summary:
            prompt_parts.append(f"## User Investment Profile\n{profile_summary}")
            prompt_parts.append("\nTailor your response to this user's risk tolerance, investment horizon, and goals.")
        
        if conversation_history:
            recent = conversation_history[-4:]
            context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:200]}" for m in recent])
            prompt_parts.append(f"\nPrevious conversation:\n{context}")
        
        if data_context:
            prompt_parts.append(f"\n{data_context}")
        
        prompt_parts.append(f"\nUser question: {user_message}")
        prompt_parts.append("""
## Response Instructions
Provide a comprehensive, well-formatted response following this structure:

1. **Start with a brief summary** (2-3 sentences)
2. **Use ## headers** for main sections
3. **Use ### subheaders** for each fund/stock
4. **Include a comparison table** if comparing multiple items
5. **End with bullet-point takeaways**

FORMAT REQUIREMENTS:
- Use markdown headers (## and ###)
- Use bullet points (-) for lists
- Use numbered lists for rankings
- Use tables for comparisons
- Add blank lines between sections
- Keep paragraphs short (2-3 sentences)
- NEVER write everything in one paragraph
""")
        
        if user_profile:
            prompt_parts.append(f"\nRemember to consider the user's {user_profile.risk_tolerance.value} risk tolerance and {user_profile.investment_horizon.value.replace('_', ' ')} investment horizon.")
        
        prompt = "\n".join(prompt_parts)
        
        result = await selected_agent.run(prompt, deps=deps)
        
        response = result.output
        
        if not response.data_points or len(response.data_points) == 0:
            response.data_points = create_data_points_from_data(fetched_data)
        
        if not response.sources or len(response.sources) == 0:
            response.sources = create_sources_from_data(fetched_data)
        
        elapsed = time.time() - start_time
        logger.info(f"[AGENT] Completed in {elapsed:.2f}s using {model_name}")
        
        return response
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[AGENT] Error after {elapsed:.2f}s: {e}", exc_info=True)
        
        return InvestmentResponse(
            explanation="I apologize, but I encountered an error processing your request. Please try rephrasing your question or ask about a specific mutual fund or stock.",
            data_points=create_data_points_from_data(fetched_data),
            sources=create_sources_from_data(fetched_data),
            risk_disclaimer=STANDARD_RISK_DISCLAIMER,
            confidence_score=0.3,
        )


async def run_agent_stream(
    user_message: str,
    conversation_history: list[dict[str, str]] = None
) -> AsyncGenerator[Any, None]:
    """Run the investment advisor agent with streaming output."""
    # Parse date range from query
    date_range = parse_date_query(user_message)
    if date_range:
        logger.info(f"[AGENT STREAM] Detected date range: {date_range.period_label}")
    
    logger.info(f"[AGENT STREAM] Step 1: Fetching relevant data...")
    fetched_data = await fetch_relevant_data(user_message, date_range)
    
    query_type = classify_query(user_message)
    selected_agent = reasoning_agent if query_type == "reasoning" else fast_agent
    model_name = REASONING_MODEL if query_type == "reasoning" else FAST_MODEL
    
    logger.info(f"[AGENT STREAM] Step 2: Processing with {model_name}...")
    
    # Generate date context
    date_context = format_date_context(date_range)
    
    deps = AgentDependencies(
        user_query=user_message,
        conversation_history=conversation_history or [],
        fetched_data=fetched_data,
        date_context=date_context,
        requested_period=date_range.period_label if date_range else "",
    )
    
    try:
        data_context = format_data_for_prompt(fetched_data, date_range)
        
        prompt_parts = []
        
        # Always add date context first
        prompt_parts.append(date_context)
        prompt_parts.append(f"\n**IMPORTANT:** Today is {get_current_date_display()}. All data below is fetched LIVE. Do not use your training data for any financial figures.\n")
        
        if conversation_history:
            recent = conversation_history[-4:]
            context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:200]}" for m in recent])
            prompt_parts.append(f"Previous conversation:\n{context}")
        
        if data_context:
            prompt_parts.append(f"\n{data_context}")
        
        prompt_parts.append(f"\nUser question: {user_message}")
        prompt_parts.append("""
## Response Instructions
Provide a comprehensive, well-formatted response following this structure:

1. **Start with a brief summary** (2-3 sentences)
2. **Use ## headers** for main sections
3. **Use ### subheaders** for each fund/stock
4. **Include a comparison table** if comparing multiple items
5. **End with bullet-point takeaways**

FORMAT REQUIREMENTS:
- Use markdown headers (## and ###)
- Use bullet points (-) for lists
- Use numbered lists for rankings
- Use tables for comparisons
- Add blank lines between sections
- Keep paragraphs short (2-3 sentences)
- NEVER write everything in one paragraph
- Use ONLY the data provided above
""")
        
        prompt = "\n".join(prompt_parts)
        
        async with selected_agent.run_stream(prompt, deps=deps) as result:
            async for chunk in result.stream_text():
                yield chunk
            
            final_result = result.output
            
            if not final_result.data_points:
                final_result.data_points = create_data_points_from_data(fetched_data)
            if not final_result.sources:
                final_result.sources = create_sources_from_data(fetched_data)
            
            yield final_result
            
    except Exception as e:
        logger.error(f"[AGENT STREAM] Error: {e}", exc_info=True)
        yield InvestmentResponse(
            explanation="I apologize, but I encountered an error. Please try again.",
            data_points=create_data_points_from_data(fetched_data),
            sources=create_sources_from_data(fetched_data),
            risk_disclaimer=STANDARD_RISK_DISCLAIMER,
            confidence_score=0.3,
        )
