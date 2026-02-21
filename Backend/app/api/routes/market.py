import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from app.services.stock_service import get_stock_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["Market"])


@router.get("/ticker")
async def get_market_ticker() -> dict[str, Any]:
    """
    Get live market ticker data for indices and popular funds.
    Used for the real-time marquee display.
    
    Returns:
        Dictionary with ticker items including indices and funds
    """
    logger.info("Fetching market ticker data")
    
    stock_service = get_stock_service()
    ticker_items = []
    
    # Fetch major indices
    indices = [
        ("NIFTY50", "NIFTY 50"),
        ("SENSEX", "SENSEX"),
        ("NIFTYBANK", "BANK NIFTY"),
    ]
    
    for symbol, display_name in indices:
        try:
            data = stock_service.get_index_quote(symbol)
            if data and data.current_price:
                ticker_items.append({
                    "name": display_name,
                    "value": f"{data.current_price:,.2f}",
                    "change": f"{data.change_percent:+.2f}%" if data.change_percent else "0.00%",
                    "up": (data.change_percent or 0) >= 0,
                    "type": "index"
                })
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
    
    # Add some popular stocks
    stocks = [
        ("RELIANCE.NS", "RELIANCE"),
        ("TCS.NS", "TCS"),
        ("HDFCBANK.NS", "HDFC BANK"),
    ]
    
    for symbol, display_name in stocks:
        try:
            data = stock_service.get_stock_quote(symbol)
            if data and data.current_price:
                ticker_items.append({
                    "name": display_name,
                    "value": f"₹{data.current_price:,.2f}",
                    "change": f"{data.change_percent:+.2f}%" if data.change_percent else "0.00%",
                    "up": (data.change_percent or 0) >= 0,
                    "type": "stock"
                })
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
    
    return {
        "items": ticker_items,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/overview")
async def get_market_overview() -> dict[str, Any]:
    """
    Get comprehensive market overview.
    
    Returns:
        Market indices, top gainers/losers, and market sentiment
    """
    logger.info("Fetching market overview")
    
    stock_service = get_stock_service()
    overview = stock_service.get_market_overview()
    
    return {
        "indices": overview,
        "updated_at": datetime.utcnow().isoformat(),
    }
