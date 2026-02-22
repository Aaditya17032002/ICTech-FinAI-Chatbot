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
    parse_date_query_async,
    format_date_context,
    get_current_date_str,
    get_current_date_display,
    DateRange,
    get_period_key_for_range,
)
from app.utils.query_analyzer import analyze_query, QueryAnalysis

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


# Legacy functions kept for backward compatibility but now use LLM-based analyzer
def extract_fund_names(query: str) -> list[str]:
    """Legacy function - use analyze_query() instead for async LLM-based extraction."""
    # Simple fallback extraction
    query_lower = query.lower()
    fund_houses = [
        "sbi", "hdfc", "icici", "axis", "kotak", "nippon", "aditya birla",
        "dsp", "uti", "tata", "franklin", "mirae", "parag parikh", "quant"
    ]
    return [h for h in fund_houses if h in query_lower]


def extract_categories(query: str) -> list[str]:
    """Legacy function - use analyze_query() instead for async LLM-based extraction."""
    categories = {
        "large cap": ["large cap", "largecap", "bluechip"],
        "mid cap": ["mid cap", "midcap"],
        "small cap": ["small cap", "smallcap"],
        "index": ["index fund"],
        "elss": ["elss", "tax saving"],
        "debt": ["debt", "bond", "liquid"],
        "hybrid": ["hybrid", "balanced"],
        "flexi cap": ["flexi cap", "flexicap", "multi cap"],
    }
    query_lower = query.lower()
    return [cat for cat, kws in categories.items() if any(kw in query_lower for kw in kws)]


async def fetch_relevant_data(query: str, date_range: Optional[DateRange] = None, conversation_history: list[dict] = None) -> tuple[dict[str, Any], QueryAnalysis]:
    """
    Multi-step data fetching based on LLM query analysis.
    Uses dynamic entity extraction to find any fund, not just from a static list.
    
    Args:
        query: User's question
        date_range: Optional parsed date range from the query
        conversation_history: Previous messages for context resolution
    
    Returns:
        Tuple of (data dict, QueryAnalysis)
    """
    data = {
        "funds": [],
        "stocks": [],
        "market": None,
        "categories": [],
        "date_range": date_range,
        "fetched_at": get_current_date_str(),
    }
    
    logger.info(f"[DATA FETCH] Analyzing query with LLM: {query[:100]}...")
    
    # Use LLM to analyze the query and extract entities (with conversation context for pronoun resolution)
    analysis = await analyze_query(query, conversation_history)
    logger.info(f"[DATA FETCH] LLM Analysis: funds={analysis.fund_names}, categories={analysis.fund_categories}, stocks={analysis.stock_symbols}, intent={analysis.intent}, is_finance={analysis.is_finance_related}")
    
    # Return early for off-topic queries
    if not analysis.is_finance_related or analysis.intent == "off_topic":
        logger.info("[DATA FETCH] Off-topic query detected, skipping data fetch")
        return data, analysis
    
    if date_range:
        logger.info(f"[DATA FETCH] Date range requested: {date_range.period_label}")
    
    # Fetch specific funds mentioned by name
    if analysis.fund_names:
        logger.info(f"[DATA FETCH] Searching for funds: {analysis.fund_names}")
        for fund_name in analysis.fund_names[:3]:
            try:
                results = research_mutual_fund(fund_name)
                if results:
                    data["funds"].extend(results[:3])
                    logger.info(f"[DATA FETCH] Found {len(results)} results for '{fund_name}'")
                else:
                    logger.warning(f"[DATA FETCH] No results for '{fund_name}'")
            except Exception as e:
                logger.error(f"Error fetching fund '{fund_name}': {e}")
    
    # Also search using search terms if provided
    if analysis.search_terms:
        for term in analysis.search_terms[:2]:
            if term not in [f.lower() for f in analysis.fund_names]:
                try:
                    results = research_mutual_fund(term)
                    if results:
                        # Avoid duplicates
                        existing_codes = {f.scheme_code for f in data["funds"]}
                        new_funds = [f for f in results if f.scheme_code not in existing_codes]
                        data["funds"].extend(new_funds[:2])
                except Exception as e:
                    logger.error(f"Error fetching search term '{term}': {e}")
    
    # Fetch funds by category
    if analysis.fund_categories:
        logger.info(f"[DATA FETCH] Fetching categories: {analysis.fund_categories}")
        for category in analysis.fund_categories[:2]:
            try:
                results = search_funds_by_category(category, limit=5)
                if results:
                    data["categories"].append({
                        "category": category,
                        "funds": results
                    })
            except Exception as e:
                logger.error(f"Error fetching category '{category}': {e}")
    
    # If no specific funds or categories found, but intent suggests recommendation
    if not data["funds"] and not data["categories"]:
        if analysis.intent in ["recommend", "compare", "analyze"]:
            logger.info("[DATA FETCH] No specific entities found, fetching default large cap funds")
            try:
                results = search_funds_by_category("large cap", limit=5)
                if results:
                    data["categories"].append({
                        "category": "large cap",
                        "funds": results
                    })
            except Exception as e:
                logger.error(f"Error fetching default category: {e}")
    
    # Fetch market data if needed
    if analysis.needs_market_data:
        try:
            data["market"] = research_market_overview()
        except Exception as e:
            logger.error(f"Error fetching market overview: {e}")
    
    # Fetch stock data
    if analysis.stock_symbols:
        logger.info(f"[DATA FETCH] Fetching stocks: {analysis.stock_symbols}")
        for stock in analysis.stock_symbols[:3]:
            try:
                result = research_stock(stock)
                if result:
                    data["stocks"].append(result)
            except Exception as e:
                logger.error(f"Error fetching stock '{stock}': {e}")
    
    logger.info(f"[DATA FETCH] Completed: {len(data['funds'])} funds, {len(data['stocks'])} stocks, {len(data['categories'])} categories")
    return data, analysis


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
        sections.append(f"""
**⚠️ USER'S REQUESTED TIME PERIOD: {date_range.period_label}**
- Duration: ~{date_range.months} months ({date_range.years} years)
- Best matching return period: **{period_key.upper()}** returns
- YOU MUST use {period_key.upper()} returns when comparing funds for this query
- DO NOT use 3Y returns if user asked for a ~1 year period
""")
    
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
    
    # Parse date range from query using LLM
    date_range = await parse_date_query_async(user_message)
    if date_range:
        logger.info(f"[AGENT] Detected date range: {date_range.period_label}")
    
    logger.info(f"[AGENT] Step 1: Fetching relevant data...")
    fetched_data, query_analysis = await fetch_relevant_data(user_message, date_range, conversation_history)
    
    # Handle off-topic queries
    if not query_analysis.is_finance_related or query_analysis.intent == "off_topic":
        logger.info("[AGENT] Off-topic query detected, returning rejection message")
        elapsed = time.time() - start_time
        return InvestmentResponse(
            message=query_analysis.rejection_message or "I'm a financial advisor assistant specialized in Indian mutual funds and stocks. I can help you with investment queries, fund comparisons, market analysis, and portfolio recommendations. Please ask me something related to investments or finance!",
            data_points=[],
            sources=[],
            disclaimer="",
        )
    
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

DATE PERIOD REQUIREMENTS:
- If user specifies a time period (e.g., "march 2024 to april 2025"), use the MATCHING return period
- For ~1 year periods, use 1Y returns (NOT 3Y)
- For ~3 year periods, use 3Y returns
- For ~5 year periods, use 5Y returns
- Always mention the time period the user asked about in your response
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
        error_msg = str(e)
        logger.error(f"[AGENT] Error after {elapsed:.2f}s: {error_msg}", exc_info=True)
        
        # Provide more helpful error message based on error type
        user_message_text = "I apologize, but I encountered an error processing your request. Please try rephrasing your question or ask about a specific mutual fund or stock."
        
        if "rate limit" in error_msg.lower():
            user_message_text = "I'm currently experiencing high demand. Please wait a moment and try again."
        elif "timeout" in error_msg.lower():
            user_message_text = "The request took too long to process. Please try a simpler question."
        elif "validation" in error_msg.lower() or "pydantic" in error_msg.lower():
            user_message_text = "I had trouble formatting my response. Let me try to help with the data I found."
        
        return InvestmentResponse(
            explanation=user_message_text,
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
    # Parse date range from query using LLM
    date_range = await parse_date_query_async(user_message)
    if date_range:
        logger.info(f"[AGENT STREAM] Detected date range: {date_range.period_label}")
    
    logger.info(f"[AGENT STREAM] Step 1: Fetching relevant data...")
    fetched_data, query_analysis = await fetch_relevant_data(user_message, date_range, conversation_history)
    
    # Handle off-topic queries
    if not query_analysis.is_finance_related or query_analysis.intent == "off_topic":
        logger.info("[AGENT STREAM] Off-topic query detected")
        yield {
            "type": "message",
            "content": query_analysis.rejection_message or "I'm a financial advisor assistant specialized in Indian mutual funds and stocks. I can help you with investment queries, fund comparisons, market analysis, and portfolio recommendations. Please ask me something related to investments or finance!"
        }
        yield {"type": "complete", "data_points": [], "sources": []}
        return
    
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

DATE PERIOD REQUIREMENTS:
- If user specifies a time period (e.g., "march 2024 to april 2025"), use the MATCHING return period
- For ~1 year periods, use 1Y returns (NOT 3Y)
- For ~3 year periods, use 3Y returns
- For ~5 year periods, use 5Y returns
- Always mention the time period the user asked about in your response
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
