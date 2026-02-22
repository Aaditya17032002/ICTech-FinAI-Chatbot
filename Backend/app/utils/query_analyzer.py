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
    intent: str = "general"  # info, compare, recommend, analyze, off_topic
    needs_market_data: bool = False
    search_terms: list[str] = field(default_factory=list)
    is_finance_related: bool = True
    rejection_message: str = ""


QUERY_ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_investment_query",
        "description": "Extract investment entities and intent from a user query about Indian mutual funds, stocks, or financial markets",
        "parameters": {
            "type": "object",
            "properties": {
                "is_finance_related": {
                    "type": "boolean",
                    "description": "True if the query is about investments, mutual funds, stocks, markets, finance, money, or financial planning. False for completely unrelated topics like weather, sports, cooking, entertainment, etc."
                },
                "fund_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific mutual fund names mentioned (e.g., 'Nippon India Mid Cap Fund', 'SBI Bluechip', 'HDFC Top 100'). Extract the full fund name as the user mentioned it."
                },
                "fund_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fund categories mentioned. Map aliases: 'blue chip'/'bluechip' → 'large cap'. Categories: 'large cap', 'mid cap', 'small cap', 'index', 'ELSS', 'debt', 'hybrid', 'flexi cap', 'multi cap'"
                },
                "stock_symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock names or symbols mentioned (e.g., 'Reliance', 'TCS', 'Infosys', 'HDFC Bank')"
                },
                "intent": {
                    "type": "string",
                    "enum": ["info", "compare", "recommend", "analyze", "general", "off_topic"],
                    "description": "User's intent: 'info' for specific fund info, 'compare' for comparisons, 'recommend' for suggestions/best/top, 'analyze' for deep analysis, 'general' for finance questions, 'off_topic' for non-finance queries"
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
            "required": ["is_finance_related", "fund_names", "fund_categories", "intent"]
        }
    }
}


async def analyze_query_llm(query: str, conversation_history: list[dict] = None) -> QueryAnalysis:
    """
    Use LLM to intelligently analyze an investment query with conversation context.
    
    Extracts:
    - Specific fund names (any fund, not just from a static list)
    - Fund categories (large cap, mid cap, etc.)
    - Stock symbols
    - User intent
    - Whether market data is needed
    
    Args:
        query: The current user query
        conversation_history: Previous messages for context resolution
    
    Returns:
        QueryAnalysis object with extracted entities
    """
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        # Build context from conversation history
        context_str = ""
        if conversation_history and len(conversation_history) > 0:
            recent = conversation_history[-6:]  # Last 3 exchanges
            context_parts = []
            for msg in recent:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:300]
                context_parts.append(f"{role}: {content}")
            context_str = "\n".join(context_parts)
        
        system_prompt = """You are an expert at analyzing investment queries for Indian mutual funds and stocks.

FIRST: Determine if the query is finance-related. Finance topics include:
- Mutual funds, stocks, shares, investments
- Markets (NIFTY, SENSEX, BSE, NSE)
- Financial planning, SIP, returns, NAV
- Fund categories, portfolios, wealth management

NOT finance-related: weather, sports, cooking, movies, general knowledge, politics (unless about economic policy), etc.

Your job is to extract:
1. **is_finance_related**: True for investment/finance queries, False for unrelated topics
2. **Fund Names**: Any mutual fund names mentioned OR referenced from conversation context
3. **Categories**: Map these aliases:
   - "blue chip" / "bluechip" → "large cap"
   - "growth fund" → could be any category, use search_terms
   - Categories: large cap, mid cap, small cap, index, ELSS, debt, hybrid, flexi cap, multi cap
4. **Stocks**: Any stock names or symbols
5. **Intent**: recommend (for best/top/list), compare, analyze, info, general, off_topic

IMPORTANT - CONTEXT RESOLUTION:
- If user says "that fund", "this fund", "the fund", "it", "more about it", etc., look at the conversation history to find what fund/stock they're referring to
- Extract the actual fund/stock name from context, not the pronoun
- Example: If previous message was about "Nippon India Mid Cap" and user asks "tell me more about it", extract fund_names: ["Nippon India Mid Cap"]

Examples:
- "List me blue chip funds" → fund_categories: ["large cap"], intent: "recommend"
- "Is Nippon India Mid Cap Fund worth investing?" → fund_names: ["Nippon India Mid Cap"], intent: "analyze"
- "Tell me more about that fund" (context: Nippon India) → fund_names: ["Nippon India Mid Cap"], intent: "info"
- "What is its NAV?" (context: SBI Bluechip) → fund_names: ["SBI Bluechip"], intent: "info"
- "Compare it with HDFC Top 100" (context: Axis Bluechip) → fund_names: ["Axis Bluechip", "HDFC Top 100"], intent: "compare"

IMPORTANT: 
- "blue chip" ALWAYS maps to "large cap" category
- For "list", "show", "best", "top" queries, use intent: "recommend"
- Be generous with fund name extraction
- ALWAYS resolve pronouns using conversation context"""

        # Build the user message with context
        user_message = f"Analyze this investment query: \"{query}\""
        if context_str:
            user_message = f"Previous conversation:\n{context_str}\n\nCurrent query to analyze: \"{query}\""
            logger.info(f"[QUERY ANALYZER] Using conversation context for query resolution")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
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
            
            is_finance = args.get("is_finance_related", True)
            intent = args.get("intent", "general")
            
            # Generate rejection message for off-topic queries
            rejection_msg = ""
            if not is_finance or intent == "off_topic":
                rejection_msg = "I'm a financial advisor assistant specialized in Indian mutual funds and stocks. I can help you with investment queries, fund comparisons, market analysis, and portfolio recommendations. Please ask me something related to investments or finance!"
            
            return QueryAnalysis(
                fund_names=args.get("fund_names", []),
                fund_categories=args.get("fund_categories", []),
                stock_symbols=args.get("stock_symbols", []),
                intent=intent,
                needs_market_data=args.get("needs_market_data", False),
                search_terms=args.get("search_terms", []),
                is_finance_related=is_finance,
                rejection_message=rejection_msg,
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
    
    # Check if finance-related
    finance_keywords = [
        "fund", "invest", "stock", "share", "market", "nifty", "sensex",
        "sip", "nav", "return", "portfolio", "mutual", "equity", "debt",
        "cap", "elss", "tax", "wealth", "money", "finance", "trading"
    ]
    result.is_finance_related = any(kw in query_lower for kw in finance_keywords)
    
    if not result.is_finance_related:
        result.intent = "off_topic"
        result.rejection_message = "I'm a financial advisor assistant specialized in Indian mutual funds and stocks. I can help you with investment queries, fund comparisons, market analysis, and portfolio recommendations. Please ask me something related to investments or finance!"
        return result
    
    # Extract categories
    category_keywords = {
        "large cap": ["large cap", "largecap", "large-cap", "bluechip", "blue chip", "blue-chip"],
        "mid cap": ["mid cap", "midcap", "mid-cap"],
        "small cap": ["small cap", "smallcap", "small-cap"],
        "index": ["index fund", "nifty 50 fund", "sensex fund"],
        "elss": ["elss", "tax saving", "tax saver"],
        "debt": ["debt fund", "bond fund", "liquid fund", "money market"],
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


async def analyze_query(query: str, conversation_history: list[dict] = None) -> QueryAnalysis:
    """
    Analyze query with conversation context - tries LLM first, falls back to regex.
    
    Args:
        query: The current user query
        conversation_history: Previous messages for context resolution (e.g., "that fund" → actual fund name)
    """
    return await analyze_query_llm(query, conversation_history)
