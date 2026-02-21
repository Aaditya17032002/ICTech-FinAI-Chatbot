import logging
from datetime import datetime
from typing import Any, Optional

from mftool import Mftool

from app.models.domain import MutualFund, MutualFundDetail, HistoricalNAV
from app.repositories.cache_repository import get_cache_repository

logger = logging.getLogger(__name__)


class FundRepository:
    """Repository for fetching mutual fund data from AMFI India via mftool."""
    
    AMFI_SOURCE_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
    AMFI_SOURCE_NAME = "AMFI India"
    
    def __init__(self):
        self._mf = Mftool()
        self._cache = get_cache_repository()
        self._schemes_cache_key = "all_schemes"
    
    def get_all_schemes(self) -> dict[str, str]:
        """Get all available mutual fund schemes (code -> name mapping)."""
        cached = self._cache.get(self._schemes_cache_key)
        if cached:
            return cached
        
        try:
            schemes = self._mf.get_scheme_codes()
            if schemes:
                self._cache.set(self._schemes_cache_key, schemes, ttl_seconds=86400)
            return schemes or {}
        except Exception as e:
            logger.error(f"Error fetching all schemes: {e}")
            return {}
    
    def search_schemes(self, query: str, limit: int = 20) -> list[MutualFund]:
        """Search for schemes by name."""
        query_lower = query.lower()
        schemes = self.get_all_schemes()
        
        results = []
        for code, name in schemes.items():
            if query_lower in name.lower():
                fund = MutualFund(scheme_code=code, scheme_name=name)
                quote = self.get_scheme_quote(code)
                if quote:
                    fund.nav = quote.get("nav")
                    fund.nav_date = quote.get("nav_date")
                results.append(fund)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_scheme_quote(self, scheme_code: str) -> Optional[dict[str, Any]]:
        """Get current NAV quote for a scheme."""
        cache_key = f"quote_{scheme_code}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached
        
        try:
            quote = self._mf.get_scheme_quote(scheme_code)
            if quote:
                result = {
                    "scheme_code": quote.get("scheme_code"),
                    "scheme_name": quote.get("scheme_name"),
                    "nav": float(quote.get("nav", 0)) if quote.get("nav") else None,
                    "nav_date": quote.get("last_updated"),
                }
                self._cache.set(cache_key, result, ttl_seconds=3600)
                return result
            return None
        except Exception as e:
            logger.error(f"Error fetching quote for {scheme_code}: {e}")
            return None
    
    def get_scheme_details(self, scheme_code: str) -> Optional[MutualFundDetail]:
        """Get detailed information about a scheme."""
        cache_key = f"details_{scheme_code}"
        cached = self._cache.get(cache_key)
        if cached:
            return MutualFundDetail(**cached)
        
        try:
            details = self._mf.get_scheme_details(scheme_code)
            if not details:
                return None
            
            quote = self.get_scheme_quote(scheme_code)
            
            fund_detail = MutualFundDetail(
                scheme_code=scheme_code,
                scheme_name=details.get("scheme_name", ""),
                fund_house=details.get("fund_house"),
                category=details.get("scheme_category"),
                nav=float(quote.get("nav")) if quote and quote.get("nav") else None,
                nav_date=quote.get("nav_date") if quote else None,
            )
            
            self._cache.set(cache_key, fund_detail.model_dump(), ttl_seconds=3600)
            return fund_detail
        except Exception as e:
            logger.error(f"Error fetching details for {scheme_code}: {e}")
            return None
    
    def get_historical_nav(self, scheme_code: str, as_dataframe: bool = False) -> list[HistoricalNAV]:
        """Get historical NAV data for a scheme."""
        cache_key = f"history_{scheme_code}"
        cached = self._cache.get(cache_key)
        if cached:
            return [HistoricalNAV(**item) for item in cached]
        
        try:
            history = self._mf.get_scheme_historical_nav(scheme_code, as_Dataframe=as_dataframe)
            if history and isinstance(history, dict) and "data" in history:
                nav_list = []
                for item in history["data"]:
                    nav_list.append(HistoricalNAV(
                        date=item.get("date", ""),
                        nav=float(item.get("nav", 0))
                    ))
                self._cache.set(cache_key, [n.model_dump() for n in nav_list], ttl_seconds=86400)
                return nav_list
            return []
        except Exception as e:
            logger.error(f"Error fetching historical NAV for {scheme_code}: {e}")
            return []
    
    def calculate_returns(self, scheme_code: str) -> dict[str, str]:
        """Calculate returns for different time periods."""
        history = self.get_historical_nav(scheme_code)
        if not history or len(history) < 2:
            return {}
        
        current_nav = history[0].nav
        returns = {}
        
        periods = {
            "1m": 30,
            "3m": 90,
            "6m": 180,
            "1y": 365,
            "3y": 1095,
            "5y": 1825,
        }
        
        for period_name, days in periods.items():
            if len(history) > days:
                old_nav = history[min(days, len(history) - 1)].nav
                if old_nav > 0:
                    return_pct = ((current_nav - old_nav) / old_nav) * 100
                    returns[period_name] = f"{return_pct:.2f}%"
        
        return returns
    
    def get_source_info(self) -> dict[str, str]:
        """Get source citation information."""
        return {
            "name": self.AMFI_SOURCE_NAME,
            "url": self.AMFI_SOURCE_URL,
        }


_fund_repo_instance: Optional[FundRepository] = None


def get_fund_repository() -> FundRepository:
    """Get singleton fund repository instance."""
    global _fund_repo_instance
    if _fund_repo_instance is None:
        _fund_repo_instance = FundRepository()
    return _fund_repo_instance
