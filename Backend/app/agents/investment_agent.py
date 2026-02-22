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

## MOST IMPORTANT: Answer What The User Actually Wants

### For "Is X worth investing?" or "Should I invest in X?" questions:
1. **Give a CLEAR verdict first**: "Yes, this fund is worth considering" OR "I would be cautious about this fund"
2. **Explain WHY** with data:
   - Compare returns to category average
   - Analyze short-term vs long-term performance
   - Consider risk factors
3. **Provide context**: How does it compare to similar funds?
4. **Give actionable advice**: "Consider this if you have X risk tolerance and Y time horizon"

### For "Which is better?" or comparison questions:
1. **State the winner clearly**: "Fund A is better for most investors because..."
2. **Show comparison table** with key metrics
3. **Explain the trade-offs**

### For "Best funds" or recommendation questions:
1. **List your top picks** with clear rankings
2. **Explain why each is recommended**
3. **Match to investor profiles** (conservative, moderate, aggressive)

## Analysis Framework for "Worth Investing?" Questions

Use this framework:
1. **Performance Analysis**:
   - Short-term (1Y): Is it positive/negative? Why?
   - Long-term (3Y, 5Y): Consistent growth?
   - Compare to benchmark/category average

2. **Verdict Criteria**:
   - 1Y negative but 3Y/5Y strong positive → "Short-term dip, long-term solid - GOOD for patient investors"
   - 1Y negative AND 3Y/5Y weak → "Underperforming - AVOID or wait"
   - All returns positive → "Strong performer - CONSIDER"

3. **Risk Assessment**:
   - High volatility? Suitable for aggressive investors only
   - Stable returns? Good for conservative investors

## Response Structure

1. **Opening Verdict** (1-2 sentences) - Answer the question directly
2. **Data Analysis** - Show the numbers with interpretation
3. **Comparison** (if relevant) - How does it stack up?
4. **Recommendation** - Clear, actionable advice
5. **Caveats** - Risk factors to consider

NEVER just restate data without analysis. ALWAYS give your opinion backed by data.
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

## Deep Analysis Mode

You are in REASONING mode - provide thorough analysis:

1. **Think step-by-step**: Break down the analysis into clear steps
2. **Be opinionated**: Don't sit on the fence - give clear recommendations
3. **Use comparisons**: Compare to category averages, benchmarks, peers
4. **Consider context**: Market conditions, fund strategy, risk factors

### For "Worth Investing?" Analysis:
- Calculate if returns beat inflation (7-8%)
- Compare to category average returns
- Assess consistency of returns
- Consider expense ratio impact
- Give a CLEAR BUY/HOLD/AVOID recommendation

### Example Good Response:
"**Verdict: Worth considering for long-term investors.**

While the -11.71% 1-year return looks concerning, this is largely due to recent market correction affecting Large & Mid Cap funds. The 3-year return of 34.60% (11.5% CAGR) and 5-year return of 64.21% (10.4% CAGR) show solid long-term performance.

**Why I recommend it:**
- Long-term returns beat inflation significantly
- Category average for Large & Mid Cap is ~9% CAGR - this fund outperforms
- Current NAV dip could be a good entry point

**Who should invest:**
- Investors with 5+ year horizon
- Moderate to aggressive risk tolerance
- Those comfortable with short-term volatility

**Who should avoid:**
- Short-term investors (< 3 years)
- Conservative investors seeking stable returns"
""",
)

# Simple Q&A agent - for general finance questions without data needs
SIMPLE_QA_PROMPT = """You are a knowledgeable Indian financial advisor assistant.

Answer general finance questions clearly and concisely. You specialize in:
- Mutual funds (types, benefits, how they work)
- Investment concepts (SIP, lumpsum, NAV, expense ratio)
- Tax benefits (Section 80C, ELSS, capital gains)
- Risk and diversification
- Basic financial planning

RESPONSE STYLE:
- Be concise but comprehensive
- Use bullet points for lists
- Use simple language, avoid jargon
- Give practical examples when helpful
- Keep responses focused (2-4 paragraphs max)
- Use markdown formatting (headers, bullets, bold)

DO NOT:
- Make up specific fund names or NAV values
- Provide specific return percentages without data
- Give personalized investment advice without knowing the user's profile

IMPORTANT: Your response MUST include a clear, helpful explanation in the 'explanation' field.
Always provide a substantive answer - never leave the explanation empty."""

simple_qa_agent = Agent(
    fast_model,
    deps_type=AgentDependencies,
    output_type=InvestmentResponse,
    system_prompt=SIMPLE_QA_PROMPT,
)


def classify_query(query: str) -> str:
    """Classify the query to determine which agent to use."""
    query_lower = query.lower()
    
    reasoning_keywords = [
        "compare", "vs", "versus", "better", "best",
        "cagr", "calculate", "return", "risk",
        "should i invest", "good time", "recommend",
        "analysis", "analyze", "evaluate", "which",
        "top performing", "highest return",
        "worth investing", "worth it", "good investment",
        "buy", "sell", "hold", "avoid"
    ]
    
    for keyword in reasoning_keywords:
        if keyword in query_lower:
            return "reasoning"
    
    return "fast"


def is_simple_query(query: str) -> bool:
    """
    Determine if query is a simple Q&A that doesn't need data fetching.
    Simple queries are general finance questions that can be answered from knowledge.
    """
    query_lower = query.lower()
    
    # Keywords that indicate data is needed
    data_needed_keywords = [
        # Specific fund/stock queries
        "nav", "price", "current", "today", "now", "latest",
        # Performance queries
        "return", "performance", "performing", "growth",
        # Comparison/recommendation
        "best", "top", "compare", "recommend", "suggest", "which",
        # Specific entities
        "sbi", "hdfc", "icici", "axis", "kotak", "nippon", "aditya birla",
        "nifty", "sensex", "reliance", "tcs", "infosys",
        # Categories with data
        "large cap", "mid cap", "small cap", "elss", "index fund",
        # Time-based
        "last year", "this year", "2024", "2025", "2026",
    ]
    
    # If any data keyword is present, it's not a simple query
    for keyword in data_needed_keywords:
        if keyword in query_lower:
            return False
    
    # Keywords that indicate simple Q&A (general knowledge)
    simple_keywords = [
        "what is", "what are", "explain", "meaning", "definition",
        "how does", "how do", "why", "difference between",
        "types of", "kind of", "example", "basics",
        "beginner", "start investing", "learn", "understand",
        "tax benefit", "tax saving", "section 80c",
        "sip vs lumpsum", "mutual fund vs", "equity vs debt",
        "risk", "diversification", "portfolio", "asset allocation",
    ]
    
    for keyword in simple_keywords:
        if keyword in query_lower:
            return True
    
    return False


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
    # First try fund_names, then search_terms for better matching
    all_search_queries = []
    
    if analysis.fund_names:
        all_search_queries.extend(analysis.fund_names[:3])
    
    if analysis.search_terms:
        # Add search terms that aren't already in the list
        for term in analysis.search_terms[:5]:
            if term.lower() not in [q.lower() for q in all_search_queries]:
                all_search_queries.append(term)
    
    if all_search_queries:
        logger.info(f"[DATA FETCH] Searching with queries: {all_search_queries}")
        found_codes = set()
        
        for search_query in all_search_queries:
            if len(data["funds"]) >= 5:  # Limit total funds
                break
            try:
                results = research_mutual_fund(search_query)
                if results:
                    # Add only new funds (avoid duplicates)
                    for fund in results[:3]:
                        if fund.scheme_code not in found_codes:
                            found_codes.add(fund.scheme_code)
                            data["funds"].append(fund)
                            logger.info(f"[DATA FETCH] Found: {fund.scheme_name}")
                else:
                    logger.warning(f"[DATA FETCH] No results for '{search_query}'")
            except Exception as e:
                logger.error(f"Error fetching fund '{search_query}': {e}")
    
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


def _generate_fallback_explanation(query: str, data: dict[str, Any], error_msg: str = "") -> str:
    """
    Generate a helpful explanation from fetched data when the LLM fails.
    This ensures users always get useful information even if the AI response fails.
    """
    sections = []
    
    # Check what data we have
    funds = data.get("funds", [])
    categories = data.get("categories", [])
    stocks = data.get("stocks", [])
    market = data.get("market")
    
    if not funds and not categories and not stocks:
        return "I couldn't find specific data for your query. Please try asking about a specific mutual fund (e.g., 'SBI Bluechip Fund') or stock (e.g., 'Reliance Industries')."
    
    # Generate response based on available data
    if funds:
        sections.append("## Fund Information\n")
        sections.append(f"Here's what I found for your query about **{query[:50]}**:\n")
        
        for fund in funds[:3]:
            sections.append(f"### {fund.scheme_name}\n")
            sections.append(f"- **NAV:** ₹{fund.nav} (as of {fund.nav_date or 'today'})")
            sections.append(f"- **Category:** {fund.category or 'N/A'}")
            sections.append(f"- **Fund House:** {fund.fund_house or 'N/A'}")
            
            if fund.returns:
                returns_str = ", ".join([f"{k}: {v}" for k, v in list(fund.returns.items())[:3]])
                sections.append(f"- **Returns:** {returns_str}")
            sections.append("")
    
    if categories:
        for cat_data in categories[:1]:
            sections.append(f"\n## Top {cat_data['category'].title()} Funds\n")
            for i, fund in enumerate(cat_data["funds"][:5], 1):
                returns_str = ""
                if fund.returns:
                    one_y = fund.returns.get("1Y", fund.returns.get("1y", "N/A"))
                    returns_str = f" | 1Y Return: {one_y}"
                sections.append(f"{i}. **{fund.scheme_name}** - NAV: ₹{fund.nav}{returns_str}")
    
    if stocks:
        sections.append("\n## Stock Information\n")
        for stock in stocks[:3]:
            sections.append(f"- **{stock.symbol}:** ₹{stock.current_price} ({stock.change_percent:+.2f}%)")
    
    # Add investment consideration
    sections.append("\n## Key Considerations\n")
    sections.append("- Review the fund's historical performance across different time periods")
    sections.append("- Consider your investment horizon and risk tolerance")
    sections.append("- Compare expense ratios and fund manager track record")
    sections.append("- Diversify across multiple funds and asset classes")
    
    return "\n".join(sections)


async def _handle_simple_query(
    user_message: str,
    conversation_history: list[dict[str, str]] = None,
    user_profile: Optional[UserProfile] = None,
    start_time: float = None
) -> InvestmentResponse:
    """
    Handle simple Q&A queries that don't need data fetching.
    Uses the fast model for quick responses.
    """
    if start_time is None:
        start_time = time.time()
    
    profile_summary = user_profile.get_profile_summary() if user_profile else ""
    
    deps = AgentDependencies(
        user_query=user_message,
        conversation_history=conversation_history or [],
        fetched_data={},
        user_profile_summary=profile_summary,
    )
    
    try:
        prompt_parts = []
        
        if profile_summary:
            prompt_parts.append(f"User profile: {profile_summary}")
        
        if conversation_history:
            recent = conversation_history[-4:]
            context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:200]}" for m in recent])
            prompt_parts.append(f"Previous conversation:\n{context}")
        
        prompt_parts.append(f"\nUser question: {user_message}")
        prompt_parts.append("""
Answer this general finance question clearly and concisely.
Use bullet points and headers where appropriate.
Keep the response focused and practical.""")
        
        prompt = "\n".join(prompt_parts)
        
        result = await simple_qa_agent.run(prompt, deps=deps)
        response = result.output
        
        logger.info(f"[AGENT] Simple Q&A raw response: explanation={response.explanation[:100] if response.explanation else 'EMPTY'}...")
        
        # If explanation is empty, the LLM might have failed to generate properly
        if not response.explanation or response.explanation.strip() == "":
            logger.warning("[AGENT] Simple Q&A returned empty explanation, using fallback")
            response.explanation = f"I can help explain that! {user_message} - Please let me provide a clear answer. Could you try asking again?"
        
        # Simple queries don't have data points or sources
        response.data_points = []
        response.sources = []
        response.confidence_score = 0.9
        
        elapsed = time.time() - start_time
        logger.info(f"[AGENT] Simple Q&A completed in {elapsed:.2f}s")
        
        return response
        
    except Exception as e:
        logger.error(f"[AGENT] Simple Q&A error: {e}, falling back to data query flow", exc_info=True)
        # Fall back to the regular data query flow
        return None  # Signal to use regular flow


async def run_agent(
    user_message: str,
    conversation_history: list[dict[str, str]] = None,
    user_profile: Optional[UserProfile] = None
) -> InvestmentResponse:
    """
    Run the investment advisor agent with smart routing.
    
    - Simple Q&A queries: Answer directly without data fetching (fast)
    - Data queries: Fetch data first, then generate response
    
    Args:
        user_message: The user's question
        conversation_history: Previous conversation messages
        user_profile: Optional user profile for personalized advice
    
    Returns:
        Structured investment response
    """
    start_time = time.time()
    
    # First, check if this is a simple Q&A that doesn't need data
    simple_query = is_simple_query(user_message)
    
    if simple_query:
        logger.info(f"[AGENT] Simple Q&A detected - answering directly without data fetch")
        result = await _handle_simple_query(user_message, conversation_history, user_profile, start_time)
        if result is not None and result.explanation and result.explanation.strip():
            return result
        logger.info(f"[AGENT] Simple Q&A failed or empty, falling back to data query flow")
    
    # For data-dependent queries, proceed with full flow
    logger.info(f"[AGENT] Data query detected - fetching relevant data...")
    
    # Parse date range from query using LLM
    date_range = await parse_date_query_async(user_message)
    if date_range:
        logger.info(f"[AGENT] Detected date range: {date_range.period_label}")
    
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
        
        # Add specific instructions based on query intent
        if query_analysis.intent == "analyze" or "worth" in user_message.lower() or "should i" in user_message.lower():
            prompt_parts.append("""
## CRITICAL: This is an INVESTMENT ANALYSIS question - User wants your OPINION!

Structure your response EXACTLY like this:

### 1. VERDICT (First line - be direct!)
Start with: "**Verdict: [RECOMMENDED/CONSIDER WITH CAUTION/AVOID]**" followed by one sentence why.

### 2. PERFORMANCE ANALYSIS
| Period | Return | Assessment |
|--------|--------|------------|
| 1 Year | X% | Good/Bad/Concerning |
| 3 Year | X% | Above/Below average |
| 5 Year | X% | Strong/Weak |

### 3. KEY INSIGHTS
- Bullet point analysis of the data
- Compare to category average if possible
- Note any red flags or positives

### 4. WHO SHOULD INVEST
- Risk profile: Conservative/Moderate/Aggressive
- Time horizon: Short/Medium/Long term
- Investment goal: Growth/Income/Tax saving

### 5. WHO SHOULD AVOID
- List investor types this fund is NOT suitable for

### 6. FINAL RECOMMENDATION
One clear, actionable sentence.
""")
        else:
            prompt_parts.append("""
## Response Instructions
Provide a comprehensive, well-formatted response:

1. **Start with a direct answer** to the user's question
2. **Use ## headers** for main sections
3. **Include data points** with analysis
4. **End with actionable takeaways**
""")
        
        prompt_parts.append("""
FORMAT REQUIREMENTS:
- Use markdown headers (## and ###)
- Use bullet points (-) for lists
- Use tables for data comparison
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
        error_msg = str(e)
        logger.error(f"[AGENT] Error after {elapsed:.2f}s: {error_msg}", exc_info=True)
        
        # Generate a helpful response from the data we have
        explanation = _generate_fallback_explanation(user_message, fetched_data, error_msg)
        
        return InvestmentResponse(
            explanation=explanation,
            data_points=create_data_points_from_data(fetched_data),
            sources=create_sources_from_data(fetched_data),
            risk_disclaimer=STANDARD_RISK_DISCLAIMER,
            confidence_score=0.6,
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
