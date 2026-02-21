import logging
import os
import time
from datetime import datetime
from typing import Any, AsyncGenerator

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

logger = logging.getLogger(__name__)


class AgentDependencies(BaseModel):
    """Dependencies injected into the agent."""
    conversation_history: list[dict[str, str]] = []
    user_query: str = ""
    fetched_data: dict[str, Any] = {}
    user_profile_summary: str = ""


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
3. **Comparison**: If comparing funds/stocks, create a structured comparison
4. **Recommendation**: Provide actionable insights based on the analysis

## Response Format
- Always include specific data points with actual values
- Cite the source and date for all data
- Structure complex responses with clear sections
- Include relevant metrics like CAGR, expense ratio, AUM when available

## Data Available
You have access to real-time data from:
- AMFI India for mutual fund NAVs and returns
- Yahoo Finance for stock prices and market indices
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


async def fetch_relevant_data(query: str) -> dict[str, Any]:
    """
    Multi-step data fetching based on query analysis.
    This is the key to providing detailed, data-driven responses.
    """
    data = {
        "funds": [],
        "stocks": [],
        "market": None,
        "categories": [],
    }
    
    logger.info(f"[DATA FETCH] Analyzing query: {query[:100]}...")
    
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


def format_data_for_prompt(data: dict[str, Any]) -> str:
    """Format fetched data into a structured prompt section."""
    sections = []
    
    if data.get("funds"):
        sections.append("## Real-Time Fund Data:")
        for fund in data["funds"]:
            sections.append(f"""
**{fund.scheme_name}** (Code: {fund.scheme_code})
- NAV: ₹{fund.nav} (as of {fund.nav_date})
- Category: {fund.category or 'N/A'}
- Fund House: {fund.fund_house or 'N/A'}
- Returns: {', '.join([f'{k}: {v}' for k, v in fund.returns.items()]) if fund.returns else 'N/A'}
""")
    
    if data.get("categories"):
        for cat_data in data["categories"]:
            sections.append(f"\n## Top {cat_data['category'].title()} Funds:")
            for i, fund in enumerate(cat_data["funds"][:5], 1):
                sections.append(f"{i}. **{fund.scheme_name}** - NAV: ₹{fund.nav}, Returns: {fund.returns}")
    
    if data.get("market"):
        sections.append("\n## Market Overview:")
        for index, values in data["market"].indices.items():
            sections.append(f"- {index}: {values.get('value', 'N/A')} ({values.get('change_percent', 0):+.2f}%)")
    
    if data.get("stocks"):
        sections.append("\n## Stock Data:")
        for stock in data["stocks"]:
            sections.append(f"- {stock.symbol}: ₹{stock.current_price} ({stock.change_percent:+.2f}%)")
    
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
    """Create source citations from fetched data."""
    sources = []
    now = datetime.utcnow()
    
    if data.get("funds") or data.get("categories"):
        sources.append(Source(
            name="AMFI India",
            url="https://www.amfiindia.com",
            accessed_at=now,
        ))
    
    if data.get("stocks") or data.get("market"):
        sources.append(Source(
            name="Yahoo Finance",
            url="https://finance.yahoo.com",
            accessed_at=now,
        ))
    
    if not sources:
        sources.append(Source(
            name="AMFI India",
            url="https://www.amfiindia.com",
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
    
    logger.info(f"[AGENT] Step 1: Fetching relevant data...")
    fetched_data = await fetch_relevant_data(user_message)
    
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
    
    deps = AgentDependencies(
        user_query=user_message,
        conversation_history=conversation_history or [],
        fetched_data=fetched_data,
        user_profile_summary=profile_summary,
    )
    
    try:
        data_context = format_data_for_prompt(fetched_data)
        
        prompt_parts = []
        
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
        prompt_parts.append("\nProvide a comprehensive, well-structured response with specific data points and actionable insights.")
        
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
    logger.info(f"[AGENT STREAM] Step 1: Fetching relevant data...")
    fetched_data = await fetch_relevant_data(user_message)
    
    query_type = classify_query(user_message)
    selected_agent = reasoning_agent if query_type == "reasoning" else fast_agent
    model_name = REASONING_MODEL if query_type == "reasoning" else FAST_MODEL
    
    logger.info(f"[AGENT STREAM] Step 2: Processing with {model_name}...")
    
    deps = AgentDependencies(
        user_query=user_message,
        conversation_history=conversation_history or [],
        fetched_data=fetched_data,
    )
    
    try:
        data_context = format_data_for_prompt(fetched_data)
        
        prompt_parts = []
        if conversation_history:
            recent = conversation_history[-4:]
            context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:200]}" for m in recent])
            prompt_parts.append(f"Previous conversation:\n{context}")
        
        if data_context:
            prompt_parts.append(f"\n{data_context}")
        
        prompt_parts.append(f"\nUser question: {user_message}")
        prompt_parts.append("\nProvide a comprehensive, well-structured response with specific data points.")
        
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
