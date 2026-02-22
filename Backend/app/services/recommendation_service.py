"""
LLM-powered fund recommendation service.
Uses a 2-step LLM flow:
1. Analyze preferences → decide categories to search
2. Analyze results → generate personalized insight
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from groq import Groq

from app.services.mutual_fund_service import get_mutual_fund_service

logger = logging.getLogger(__name__)


@dataclass
class RecommendationRequest:
    """User preferences for fund recommendation."""
    goal: str  # wealth, retirement, tax_saving, house, education, travel
    risk_tolerance: str  # conservative, moderate, aggressive
    investment_horizon: str  # short_term, medium_term, long_term
    monthly_amount: int = 5000


@dataclass
class CategoryRecommendation:
    """LLM's recommendation for fund categories."""
    categories: list[str] = field(default_factory=list)
    allocation: dict[str, int] = field(default_factory=dict)
    search_queries: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class FundRecommendation:
    """Final recommendation with funds and AI insight."""
    categories: list[str]
    allocation: dict[str, int]
    funds: list[dict]
    ai_insight: str
    reasoning: str


CATEGORY_ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "recommend_fund_categories",
        "description": "Recommend optimal mutual fund categories and allocation based on user's investment profile",
        "parameters": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recommended fund categories. Options: 'Large Cap', 'Mid Cap', 'Small Cap', 'Flexi Cap', 'ELSS', 'Index Fund', 'Debt', 'Liquid', 'Hybrid', 'Multi Cap'"
                },
                "allocation": {
                    "type": "object",
                    "description": "Percentage allocation for each category (should sum to 100). Example: {'Large Cap': 60, 'Mid Cap': 30, 'Debt': 10}"
                },
                "search_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search queries to find funds in each category. Include 'direct growth' for better results. Example: ['large cap direct growth', 'mid cap direct growth']"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation (1-2 sentences) of why these categories are recommended for this profile"
                }
            },
            "required": ["categories", "allocation", "search_queries", "reasoning"]
        }
    }
}


INSIGHT_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_investment_insight",
        "description": "Generate personalized investment insight based on user profile and recommended funds",
        "parameters": {
            "type": "object",
            "properties": {
                "insight": {
                    "type": "string",
                    "description": "A personalized 2-3 sentence insight about the recommended funds. Include specific advice based on the user's goal, risk tolerance, and investment horizon. Mention the SIP amount and potential benefits."
                }
            },
            "required": ["insight"]
        }
    }
}


async def analyze_preferences(request: RecommendationRequest) -> CategoryRecommendation:
    """
    Step 1: Use LLM to analyze user preferences and recommend fund categories.
    """
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        system_prompt = """You are an expert Indian mutual fund advisor. Based on the user's investment profile, recommend the optimal fund categories and allocation.

RULES:
1. For tax_saving goal, ALWAYS include ELSS
2. For conservative risk:
   - Short term: Prioritize Liquid/Debt funds (70-80%)
   - Long term: Large Cap heavy (60-70%)
3. For aggressive risk:
   - Long term: Include Small Cap (20-30%)
   - Can include Mid Cap (30-40%)
4. For moderate risk:
   - Balance between Large Cap and Mid Cap
   - Consider Flexi Cap for flexibility
5. For retirement/long-term wealth:
   - Equity-heavy allocation (70-80%)
   - Include some debt for stability (10-20%)
6. For short-term goals (house, travel):
   - More conservative allocation
   - Higher debt/liquid component

ALLOCATION MUST SUM TO 100%.
Include 'direct growth' in search queries for better fund results."""

        user_message = f"""User Profile:
- Goal: {request.goal}
- Risk Tolerance: {request.risk_tolerance}
- Investment Horizon: {request.investment_horizon}
- Monthly SIP Amount: ₹{request.monthly_amount:,}

Recommend the optimal fund categories and allocation for this investor."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            tools=[CATEGORY_ANALYSIS_TOOL],
            tool_choice={"type": "function", "function": {"name": "recommend_fund_categories"}},
            temperature=0.3,
            max_tokens=500,
        )
        
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            
            logger.info(f"[RECOMMENDATION] LLM category analysis: {args}")
            
            return CategoryRecommendation(
                categories=args.get("categories", []),
                allocation=args.get("allocation", {}),
                search_queries=args.get("search_queries", []),
                reasoning=args.get("reasoning", ""),
            )
        
        return _fallback_category_recommendation(request)
        
    except Exception as e:
        logger.error(f"[RECOMMENDATION] LLM error in step 1: {e}")
        return _fallback_category_recommendation(request)


async def generate_insight(
    request: RecommendationRequest,
    category_rec: CategoryRecommendation,
    funds: list[dict]
) -> str:
    """
    Step 2: Use LLM to generate personalized insight based on recommended funds.
    """
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        # Prepare fund summary for LLM
        fund_summary = []
        for fund in funds[:6]:
            name = fund.get("scheme_name", "Unknown")[:50]
            nav = fund.get("nav", "N/A")
            fund_summary.append(f"- {name} (NAV: ₹{nav})")
        
        funds_text = "\n".join(fund_summary) if fund_summary else "No specific funds found"
        
        system_prompt = """You are a friendly Indian mutual fund advisor. Generate a personalized, actionable insight for the investor.

RULES:
1. Keep it to 2-3 sentences
2. Be specific about their goal and timeline
3. Mention the SIP amount and its potential
4. Be encouraging but realistic
5. Don't use jargon - keep it simple
6. Reference the recommended categories"""

        user_message = f"""User Profile:
- Goal: {request.goal.replace('_', ' ')}
- Risk: {request.risk_tolerance}
- Horizon: {request.investment_horizon.replace('_', ' ')}
- Monthly SIP: ₹{request.monthly_amount:,}

Recommended Categories: {', '.join(category_rec.categories)}
Allocation: {category_rec.allocation}

Top Recommended Funds:
{funds_text}

Generate a personalized insight for this investor."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            tools=[INSIGHT_GENERATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_investment_insight"}},
            temperature=0.5,
            max_tokens=200,
        )
        
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            
            insight = args.get("insight", "")
            logger.info(f"[RECOMMENDATION] LLM generated insight: {insight[:100]}...")
            return insight
        
        return _fallback_insight(request, category_rec)
        
    except Exception as e:
        logger.error(f"[RECOMMENDATION] LLM error in step 2: {e}")
        return _fallback_insight(request, category_rec)


async def get_recommendations(request: RecommendationRequest) -> FundRecommendation:
    """
    Main function: 2-step LLM flow for fund recommendations.
    
    Step 1: LLM analyzes preferences → decides categories
    Step 2: Search API fetches funds
    Step 3: LLM generates personalized insight
    """
    logger.info(f"[RECOMMENDATION] Starting for: {request}")
    
    # Step 1: LLM decides categories
    category_rec = await analyze_preferences(request)
    logger.info(f"[RECOMMENDATION] Categories: {category_rec.categories}, Allocation: {category_rec.allocation}")
    
    # Step 2: Search for funds in recommended categories
    mf_service = get_mutual_fund_service()
    all_funds = []
    
    for query in category_rec.search_queries[:3]:  # Limit to 3 searches
        try:
            results = mf_service.search_funds(query, limit=4)
            all_funds.extend(results)
            logger.info(f"[RECOMMENDATION] Found {len(results)} funds for '{query}'")
        except Exception as e:
            logger.error(f"[RECOMMENDATION] Search error for '{query}': {e}")
    
    # Remove duplicates by scheme_code
    seen_codes = set()
    unique_funds = []
    for fund in all_funds:
        code = fund.scheme_code if hasattr(fund, 'scheme_code') else fund.get('scheme_code')
        if code and code not in seen_codes:
            seen_codes.add(code)
            # Convert to dict if needed
            if hasattr(fund, 'model_dump'):
                unique_funds.append(fund.model_dump())
            elif hasattr(fund, '__dict__'):
                unique_funds.append(fund.__dict__)
            else:
                unique_funds.append(fund)
    
    # Limit to 8 funds
    unique_funds = unique_funds[:8]
    logger.info(f"[RECOMMENDATION] Total unique funds: {len(unique_funds)}")
    
    # Step 3: LLM generates insight
    insight = await generate_insight(request, category_rec, unique_funds)
    
    return FundRecommendation(
        categories=category_rec.categories,
        allocation=category_rec.allocation,
        funds=unique_funds,
        ai_insight=insight,
        reasoning=category_rec.reasoning,
    )


def _fallback_category_recommendation(request: RecommendationRequest) -> CategoryRecommendation:
    """Fallback if LLM fails in step 1."""
    categories = []
    allocation = {}
    queries = []
    
    if request.goal == "tax_saving":
        categories = ["ELSS"]
        allocation = {"ELSS": 100}
        queries = ["elss tax saving direct growth"]
    elif request.risk_tolerance == "conservative":
        if request.investment_horizon == "short_term":
            categories = ["Liquid", "Debt"]
            allocation = {"Liquid": 60, "Debt": 40}
            queries = ["liquid fund direct", "debt fund direct growth"]
        else:
            categories = ["Large Cap", "Debt"]
            allocation = {"Large Cap": 70, "Debt": 30}
            queries = ["large cap direct growth", "debt fund direct growth"]
    elif request.risk_tolerance == "aggressive":
        if request.investment_horizon == "long_term":
            categories = ["Mid Cap", "Small Cap"]
            allocation = {"Mid Cap": 50, "Small Cap": 50}
            queries = ["mid cap direct growth", "small cap direct growth"]
        else:
            categories = ["Mid Cap", "Flexi Cap"]
            allocation = {"Mid Cap": 60, "Flexi Cap": 40}
            queries = ["mid cap direct growth", "flexi cap direct growth"]
    else:
        # Moderate
        categories = ["Large Cap", "Mid Cap"]
        allocation = {"Large Cap": 60, "Mid Cap": 40}
        queries = ["large cap direct growth", "mid cap direct growth"]
    
    return CategoryRecommendation(
        categories=categories,
        allocation=allocation,
        search_queries=queries,
        reasoning="Based on your profile, this allocation balances growth potential with risk management.",
    )


def _fallback_insight(request: RecommendationRequest, category_rec: CategoryRecommendation) -> str:
    """Fallback insight if LLM fails in step 2."""
    goal_text = request.goal.replace("_", " ")
    horizon_text = request.investment_horizon.replace("_", " ")
    categories_text = ", ".join(category_rec.categories)
    
    return f"For your {goal_text} goal with a {horizon_text} horizon, {categories_text} funds are well-suited. With a ₹{request.monthly_amount:,}/month SIP, you can build a diversified portfolio that matches your {request.risk_tolerance} risk appetite."
