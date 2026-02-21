import logging
from typing import Any, Optional

from app.models.domain import StockData
from app.repositories.stock_repository import StockRepository, get_stock_repository
from app.utils.calculations import calculate_cagr, format_indian_currency

logger = logging.getLogger(__name__)


class StockService:
    """Service layer for stock market operations."""
    
    def __init__(self, stock_repo: Optional[StockRepository] = None):
        self._repo = stock_repo or get_stock_repository()
    
    def get_stock_quote(self, symbol: str) -> Optional[StockData]:
        """
        Get current stock quote.
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")
        
        Returns:
            Stock data or None if not found
        """
        return self._repo.get_stock_info(symbol)
    
    def get_index_quote(self, index_name: str) -> Optional[StockData]:
        """
        Get current index value.
        
        Args:
            index_name: Index name (e.g., "NIFTY50", "SENSEX")
        
        Returns:
            Index data or None
        """
        return self._repo.get_index_data(index_name)
    
    def get_stock_returns(self, symbol: str) -> dict[str, str]:
        """
        Get stock returns for different periods.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary of period -> return percentage
        """
        return self._repo.calculate_returns(symbol)
    
    def get_historical_prices(
        self,
        symbol: str,
        period: str = "1y"
    ) -> Optional[list[dict[str, Any]]]:
        """
        Get historical price data.
        
        Args:
            symbol: Stock symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
        
        Returns:
            List of historical price data
        """
        return self._repo.get_historical_data(symbol, period)
    
    def get_market_overview(self) -> dict[str, Any]:
        """
        Get overview of major market indices.
        
        Returns:
            Dictionary with major index data
        """
        indices = ["NIFTY50", "SENSEX", "NIFTYBANK"]
        overview = {}
        
        for index in indices:
            data = self._repo.get_index_data(index)
            if data:
                overview[index] = {
                    "value": data.current_price,
                    "change_percent": data.change_percent,
                }
        
        return overview
    
    def compare_stocks(self, symbols: list[str]) -> list[dict[str, Any]]:
        """
        Compare multiple stocks.
        
        Args:
            symbols: List of stock symbols
        
        Returns:
            List of stock comparison data
        """
        comparison = []
        
        for symbol in symbols:
            stock = self._repo.get_stock_info(symbol)
            if stock:
                returns = self._repo.calculate_returns(symbol)
                comparison.append({
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "price": stock.current_price,
                    "change_percent": stock.change_percent,
                    "market_cap": format_indian_currency(stock.market_cap) if stock.market_cap else None,
                    "pe_ratio": stock.pe_ratio,
                    "returns": returns,
                })
        
        return comparison
    
    def get_stock_fundamentals(self, symbol: str) -> Optional[dict[str, Any]]:
        """
        Get fundamental data for a stock.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with fundamental metrics
        """
        stock = self._repo.get_stock_info(symbol)
        if not stock:
            return None
        
        return {
            "symbol": stock.symbol,
            "name": stock.name,
            "current_price": stock.current_price,
            "market_cap": format_indian_currency(stock.market_cap) if stock.market_cap else None,
            "pe_ratio": stock.pe_ratio,
            "52_week_high": stock.fifty_two_week_high,
            "52_week_low": stock.fifty_two_week_low,
        }
    
    def get_source_info(self) -> dict[str, str]:
        """Get data source information for citations."""
        return self._repo.get_source_info()


_stock_service_instance: Optional[StockService] = None


def get_stock_service() -> StockService:
    """Get singleton stock service instance."""
    global _stock_service_instance
    if _stock_service_instance is None:
        _stock_service_instance = StockService()
    return _stock_service_instance
