"""
Dynamic query analyzer using LLM to extract entities from investment queries.
Extracts fund names, stock symbols, categories, and intent from natural language.
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from groq import Groq

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysis:
    """Result of analyzing an investment query."""
    fund_names: list[str] = field(default_factory=list)
    fund_categories: list[str] = field(default_factory=list)
    stock_symbols: list[str] = field(default_factory=list)
    intent: str = "general"  # info, compare, recommend, analyze
    needs_market_data: bool = False
    search_terms: list[str] = field(default_factory=list)


QUERY_ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_investment_query",
        "description": "Extract investment entities and intent from a user query",
        "parameters": {
            "type": "object",
            "properties": {
                "fund_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific mutual fund names mentioned (e.g., 'Nippon India Mid Cap Fund', 'SBI Bluechip', 'HDFC Top 100'). Extract the full fund name as the user mentioned it."
                },
                "fund_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fund categories mentioned (e.g., 'large cap', 'mid cap', 'small cap', 'index', 'ELSS', 'debt', 'hybrid', 'flexi cap')"
                },
                "stock_symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock names or symbols mentioned (e.g., 'Reliance', 'TCS', 'Infosys', 'HDFC Bank')"
                },
                "intent": {
                    "type": "string",
                    "enum": ["info", "compare", "recommend", "analyze", "general"],
                    "description": "User's intent: 'info' for specific fund info, 'compare' for comparisons, 'recommend' for suggestions, 'analyze' for deep analysis, 'general' for other"
                },
                "needs_market_data": {
                    "type": "boolean",
                    "description": "Whether the query needs market index data (NIFTY, SENSEX)"
                },
                "search_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key search terms to use for finding relevant funds if specific names aren't clear"
                }
            },
            "required": ["fund_names", "fund_categories", "intent"]
        }
    }
}


async def analyze_query_llm(query: str) -> QueryAnalysis:
    """
    Use LLM to intelligently analyze an investment query.
    
    Extracts:
    - Specific fund names (any fund, not just from a static list)
    - Fund categories (large cap, mid cap, etc.)
    - Stock symbols
    - User intent
    - Whether market data is needed
    
    Returns:
        QueryAnalysis object with extracted entities
    """
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        system_prompt = """You are an expert at analyzing investment queries for Indian mutual funds and stocks.

Your job is to extract:
1. **Fund Names**: Any mutual fund names mentioned. Be generous - if someone says "Nippon mid cap" or "nippon india mid cap fund", extract it as a search term.
2. **Categories**: Fund categories like large cap, mid cap, small cap, ELSS, index, debt, hybrid, flexi cap
3. **Stocks**: Any stock names or symbols (Reliance, TCS, Infosys, etc.)
4. **Intent**: What does the user want to know?

Examples:
- "Is Nippon India Mid Cap Fund worth investing?" → fund_names: ["Nippon India Mid Cap"], intent: "analyze"
- "Compare SBI Bluechip vs HDFC Top 100" → fund_names: ["SBI Bluechip", "HDFC Top 100"], intent: "compare"
- "Best large cap funds" → fund_categories: ["large cap"], intent: "recommend"
- "How is Reliance stock doing?" → stock_symbols: ["Reliance"], intent: "info"
- "Top performing mid cap funds last year" → fund_categories: ["mid cap"], intent: "recommend"

IMPORTANT: Always extract fund names even if partially mentioned. "Nippon mid cap" should become "Nippon India Mid Cap" or at least "Nippon Mid Cap" as a search term."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this investment query: \"{query}\""}
            ],
            tools=[QUERY_ANALYSIS_TOOL],
            tool_choice={"type": "function", "function": {"name": "analyze_investment_query"}},
            temperature=0,
            max_tokens=300,
        )
        
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            
            logger.info(f"[QUERY ANALYZER] Extracted: {args}")
            
            return QueryAnalysis(
                fund_names=args.get("fund_names", []),
                fund_categories=args.get("fund_categories", []),
                stock_symbols=args.get("stock_symbols", []),
                intent=args.get("intent", "general"),
                needs_market_data=args.get("needs_market_data", False),
                search_terms=args.get("search_terms", [])
            )
        
        return QueryAnalysis()
        
    except Exception as e:
        logger.error(f"[QUERY ANALYZER] LLM error: {e}, falling back to regex")
        return analyze_query_regex(query)


def analyze_query_regex(query: str) -> QueryAnalysis:
    """
    Fallback regex-based query analyzer.
    """
    query_lower = query.lower()
    
    result = QueryAnalysis()
    
    # Extract categories
    category_keywords = {
        "large cap": ["large cap", "largecap", "large-cap", "bluechip", "blue chip"],
        "mid cap": ["mid cap", "midcap", "mid-cap"],
        "small cap": ["small cap", "smallcap", "small-cap"],
        "index": ["index fund", "nifty 50 fund", "sensex fund"],
        "elss": ["elss", "tax saving", "tax saver"],
        "debt": ["debt", "bond", "liquid", "money market"],
        "hybrid": ["hybrid", "balanced", "aggressive hybrid"],
        "flexi cap": ["flexi cap", "flexicap", "multi cap", "multicap"],
    }
    
    for category, keywords in category_keywords.items():
        for kw in keywords:
            if kw in query_lower:
                result.fund_categories.append(category)
                break
    
    # Extract fund house names as search terms
    fund_houses = [
        "sbi", "hdfc", "icici", "axis", "kotak", "nippon", "aditya birla",
        "dsp", "uti", "tata", "franklin", "mirae", "parag parikh", "quant",
        "canara robeco", "bandhan", "edelweiss", "pgim", "motilal oswal", "invesco"
    ]
    
    for house in fund_houses:
        if house in query_lower:
            # Try to extract more context around the fund house name
            result.search_terms.append(house)
    
    # Extract stock names
    stocks = ["reliance", "tcs", "infosys", "hdfc bank", "icici bank", "wipro", "hcl", "bharti airtel"]
    for stock in stocks:
        if stock in query_lower:
            result.stock_symbols.append(stock.upper().replace(" ", ""))
    
    # Determine intent
    if any(kw in query_lower for kw in ["compare", "vs", "versus", "better"]):
        result.intent = "compare"
    elif any(kw in query_lower for kw in ["best", "top", "recommend", "suggest"]):
        result.intent = "recommend"
    elif any(kw in query_lower for kw in ["worth", "should i", "good time", "analyze"]):
        result.intent = "analyze"
    elif any(kw in query_lower for kw in ["what is", "tell me about", "info"]):
        result.intent = "info"
    
    # Check for market data need
    if any(kw in query_lower for kw in ["market", "nifty", "sensex", "index"]):
        result.needs_market_data = True
    
    return result


async def analyze_query(query: str) -> QueryAnalysis:
    """
    Analyze query - tries LLM first, falls back to regex.
    """
    return await analyze_query_llm(query)
