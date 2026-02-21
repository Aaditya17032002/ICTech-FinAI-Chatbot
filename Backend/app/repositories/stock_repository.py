import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import yfinance as yf

from app.models.domain import StockData
from app.repositories.cache_repository import get_cache_repository

logger = logging.getLogger(__name__)


class StockRepository:
    """Repository for fetching stock data from Yahoo Finance."""
    
    YAHOO_SOURCE_URL = "https://finance.yahoo.com"
    YAHOO_SOURCE_NAME = "Yahoo Finance"
    
    NSE_SUFFIX = ".NS"
    BSE_SUFFIX = ".BO"
    
    POPULAR_INDICES = {
        "NIFTY50": "^NSEI",
        "SENSEX": "^BSESN",
        "NIFTYBANK": "^NSEBANK",
        "NIFTYIT": "^CNXIT",
    }
    
    def __init__(self):
        self._cache = get_cache_repository()
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to include exchange suffix if needed."""
        symbol = symbol.upper().strip()
        if symbol in self.POPULAR_INDICES:
            return self.POPULAR_INDICES[symbol]
        if not symbol.endswith(self.NSE_SUFFIX) and not symbol.endswith(self.BSE_SUFFIX) and not symbol.startswith("^"):
            return f"{symbol}{self.NSE_SUFFIX}"
        return symbol
    
    def get_stock_info(self, symbol: str) -> Optional[StockData]:
        """Get current stock information."""
        normalized = self._normalize_symbol(symbol)
        cache_key = f"stock_info_{normalized}"
        
        cached = self._cache.get(cache_key)
        if cached:
            return StockData(**cached)
        
        try:
            ticker = yf.Ticker(normalized)
            info = ticker.info
            
            if not info or "regularMarketPrice" not in info:
                return None
            
            stock_data = StockData(
                symbol=normalized,
                name=info.get("shortName") or info.get("longName"),
                current_price=info.get("regularMarketPrice") or info.get("currentPrice"),
                change_percent=info.get("regularMarketChangePercent"),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            )
            
            self._cache.set(cache_key, stock_data.model_dump(), ttl_seconds=300)
            return stock_data
        except Exception as e:
            logger.error(f"Error fetching stock info for {symbol}: {e}")
            return None
    
    def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> Optional[list[dict[str, Any]]]:
        """Get historical price data for a stock."""
        normalized = self._normalize_symbol(symbol)
        cache_key = f"stock_history_{normalized}_{period}_{interval}"
        
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        try:
            ticker = yf.Ticker(normalized)
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                return None
            
            data = []
            for date, row in hist.iterrows():
                data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })
            
            self._cache.set(cache_key, data, ttl_seconds=3600)
            return data
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def get_index_data(self, index_name: str) -> Optional[StockData]:
        """Get data for a market index."""
        if index_name.upper() in self.POPULAR_INDICES:
            return self.get_stock_info(index_name)
        return None
    
    def calculate_returns(self, symbol: str) -> dict[str, str]:
        """Calculate returns for different time periods."""
        normalized = self._normalize_symbol(symbol)
        
        try:
            ticker = yf.Ticker(normalized)
            hist = ticker.history(period="5y", interval="1d")
            
            if hist.empty:
                return {}
            
            current_price = hist["Close"].iloc[-1]
            returns = {}
            
            periods = {
                "1m": 21,
                "3m": 63,
                "6m": 126,
                "1y": 252,
                "3y": 756,
                "5y": 1260,
            }
            
            for period_name, trading_days in periods.items():
                if len(hist) > trading_days:
                    old_price = hist["Close"].iloc[-(trading_days + 1)]
                    if old_price > 0:
                        return_pct = ((current_price - old_price) / old_price) * 100
                        returns[period_name] = f"{return_pct:.2f}%"
            
            return returns
        except Exception as e:
            logger.error(f"Error calculating returns for {symbol}: {e}")
            return {}
    
    def get_source_info(self) -> dict[str, str]:
        """Get source citation information."""
        return {
            "name": self.YAHOO_SOURCE_NAME,
            "url": self.YAHOO_SOURCE_URL,
        }


_stock_repo_instance: Optional[StockRepository] = None


def get_stock_repository() -> StockRepository:
    """Get singleton stock repository instance."""
    global _stock_repo_instance
    if _stock_repo_instance is None:
        _stock_repo_instance = StockRepository()
    return _stock_repo_instance
