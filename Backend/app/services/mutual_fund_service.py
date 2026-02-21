import logging
from datetime import datetime
from typing import Optional

from app.models.domain import MutualFund, MutualFundDetail
from app.models.schemas import FundSearchResult, FundDetailResponse
from app.repositories.fund_repository import FundRepository, get_fund_repository
from app.utils.calculations import calculate_cagr

logger = logging.getLogger(__name__)


class MutualFundService:
    """Service layer for mutual fund operations."""
    
    def __init__(self, fund_repo: Optional[FundRepository] = None):
        self._repo = fund_repo or get_fund_repository()
    
    def search_funds(self, query: str, limit: int = 20) -> list[FundSearchResult]:
        """
        Search for mutual funds by name.
        
        Args:
            query: Search query
            limit: Maximum results to return
        
        Returns:
            List of matching funds
        """
        funds = self._repo.search_schemes(query, limit)
        
        return [
            FundSearchResult(
                scheme_code=f.scheme_code,
                scheme_name=f.scheme_name,
                category=f.category,
                nav=f.nav,
                nav_date=f.nav_date,
            )
            for f in funds
        ]
    
    def get_fund_details(self, scheme_code: str) -> Optional[FundDetailResponse]:
        """
        Get detailed information about a specific fund.
        
        Args:
            scheme_code: AMFI scheme code
        
        Returns:
            Fund details or None if not found
        """
        details = self._repo.get_scheme_details(scheme_code)
        if not details:
            return None
        
        returns = self._repo.calculate_returns(scheme_code)
        
        return FundDetailResponse(
            scheme_code=details.scheme_code,
            scheme_name=details.scheme_name,
            fund_house=details.fund_house,
            category=details.category,
            nav=details.nav,
            nav_date=details.nav_date,
            returns=returns,
            aum=details.aum,
            expense_ratio=details.expense_ratio,
        )
    
    def get_fund_nav(self, scheme_code: str) -> Optional[dict]:
        """
        Get current NAV for a fund.
        
        Args:
            scheme_code: AMFI scheme code
        
        Returns:
            NAV data dictionary
        """
        return self._repo.get_scheme_quote(scheme_code)
    
    def get_fund_returns(self, scheme_code: str) -> dict[str, str]:
        """
        Get returns for different time periods.
        
        Args:
            scheme_code: AMFI scheme code
        
        Returns:
            Dictionary of period -> return percentage
        """
        return self._repo.calculate_returns(scheme_code)
    
    def compare_funds(self, scheme_codes: list[str]) -> list[dict]:
        """
        Compare multiple funds side by side.
        
        Args:
            scheme_codes: List of scheme codes to compare
        
        Returns:
            List of fund comparison data
        """
        comparison = []
        
        for code in scheme_codes:
            details = self._repo.get_scheme_details(code)
            if details:
                returns = self._repo.calculate_returns(code)
                comparison.append({
                    "scheme_code": code,
                    "scheme_name": details.scheme_name,
                    "category": details.category,
                    "nav": details.nav,
                    "returns": returns,
                })
        
        return comparison
    
    def get_top_funds_by_category(
        self,
        category_keyword: str,
        limit: int = 10
    ) -> list[FundSearchResult]:
        """
        Get top funds matching a category keyword.
        
        Args:
            category_keyword: Category to search for (e.g., "large cap", "index")
            limit: Maximum results
        
        Returns:
            List of matching funds
        """
        return self.search_funds(category_keyword, limit)
    
    def calculate_fund_cagr(
        self,
        scheme_code: str,
        years: int = 3
    ) -> Optional[float]:
        """
        Calculate CAGR for a fund over specified years.
        
        Args:
            scheme_code: AMFI scheme code
            years: Number of years for CAGR calculation
        
        Returns:
            CAGR percentage or None
        """
        history = self._repo.get_historical_nav(scheme_code)
        if not history or len(history) < 2:
            return None
        
        days_needed = years * 365
        if len(history) < days_needed:
            return None
        
        current_nav = history[0].nav
        old_nav = history[min(days_needed - 1, len(history) - 1)].nav
        
        return calculate_cagr(old_nav, current_nav, years)
    
    def get_source_info(self) -> dict[str, str]:
        """Get data source information for citations."""
        return self._repo.get_source_info()


_mf_service_instance: Optional[MutualFundService] = None


def get_mutual_fund_service() -> MutualFundService:
    """Get singleton mutual fund service instance."""
    global _mf_service_instance
    if _mf_service_instance is None:
        _mf_service_instance = MutualFundService()
    return _mf_service_instance
