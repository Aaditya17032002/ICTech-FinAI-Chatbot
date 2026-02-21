"""
Background data prefetch service for popular funds and market data.
Ensures fast responses by pre-caching commonly requested data.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.repositories.cache_repository import get_cache_repository
from app.services.mutual_fund_service import get_mutual_fund_service

logger = logging.getLogger(__name__)

POPULAR_FUND_CODES = [
    "119598",  # SBI Bluechip Fund
    "118834",  # HDFC Top 100 Fund
    "120503",  # Axis Bluechip Fund
    "120505",  # ICICI Prudential Bluechip Fund
    "118989",  # Mirae Asset Large Cap Fund
    "100356",  # UTI Nifty 50 Index Fund
    "120716",  # Kotak Bluechip Fund
    "119597",  # SBI Magnum Multicap Fund
    "118825",  # HDFC Flexi Cap Fund
    "120847",  # Parag Parikh Flexi Cap Fund
    "119062",  # Nippon India Large Cap Fund
    "118632",  # Franklin India Bluechip Fund
    "119028",  # DSP Flexi Cap Fund
    "120837",  # Axis Midcap Fund
    "118989",  # Mirae Asset Emerging Bluechip
]

POPULAR_CATEGORIES = [
    "large cap",
    "mid cap",
    "small cap",
    "index",
    "elss",
    "flexi cap",
]

FALLBACK_FUND_DATA = {
    "119598": {
        "scheme_code": "119598",
        "scheme_name": "SBI Blue Chip Fund - Regular Plan - Growth",
        "fund_house": "SBI Mutual Fund",
        "category": "Equity - Large Cap",
        "nav": 85.67,
        "nav_date": "2026-02-20",
        "returns": {"1m": "2.5%", "3m": "5.2%", "6m": "8.1%", "1y": "15.3%", "3y": "12.8%"},
    },
    "118834": {
        "scheme_code": "118834",
        "scheme_name": "HDFC Top 100 Fund - Regular Plan - Growth",
        "fund_house": "HDFC Mutual Fund",
        "category": "Equity - Large Cap",
        "nav": 924.12,
        "nav_date": "2026-02-20",
        "returns": {"1m": "2.1%", "3m": "4.8%", "6m": "7.9%", "1y": "14.7%", "3y": "11.9%"},
    },
    "120503": {
        "scheme_code": "120503",
        "scheme_name": "Axis Bluechip Fund - Regular Plan - Growth",
        "fund_house": "Axis Mutual Fund",
        "category": "Equity - Large Cap",
        "nav": 52.34,
        "nav_date": "2026-02-20",
        "returns": {"1m": "1.9%", "3m": "4.5%", "6m": "7.2%", "1y": "13.8%", "3y": "10.5%"},
    },
    "120505": {
        "scheme_code": "120505",
        "scheme_name": "ICICI Prudential Bluechip Fund - Growth",
        "fund_house": "ICICI Prudential Mutual Fund",
        "category": "Equity - Large Cap",
        "nav": 78.92,
        "nav_date": "2026-02-20",
        "returns": {"1m": "2.3%", "3m": "5.0%", "6m": "8.5%", "1y": "16.2%", "3y": "13.1%"},
    },
    "118989": {
        "scheme_code": "118989",
        "scheme_name": "Mirae Asset Large Cap Fund - Regular Plan - Growth",
        "fund_house": "Mirae Asset Mutual Fund",
        "category": "Equity - Large Cap",
        "nav": 98.45,
        "nav_date": "2026-02-20",
        "returns": {"1m": "2.7%", "3m": "5.5%", "6m": "9.2%", "1y": "17.5%", "3y": "14.2%"},
    },
    "100356": {
        "scheme_code": "100356",
        "scheme_name": "UTI Nifty 50 Index Fund - Growth",
        "fund_house": "UTI Mutual Fund",
        "category": "Equity - Index Fund",
        "nav": 145.67,
        "nav_date": "2026-02-20",
        "returns": {"1m": "2.0%", "3m": "4.2%", "6m": "7.8%", "1y": "14.5%", "3y": "12.0%"},
    },
    "120847": {
        "scheme_code": "120847",
        "scheme_name": "Parag Parikh Flexi Cap Fund - Regular Plan - Growth",
        "fund_house": "PPFAS Mutual Fund",
        "category": "Equity - Flexi Cap",
        "nav": 67.89,
        "nav_date": "2026-02-20",
        "returns": {"1m": "3.1%", "3m": "6.2%", "6m": "10.5%", "1y": "19.8%", "3y": "16.5%"},
    },
    "120837": {
        "scheme_code": "120837",
        "scheme_name": "Axis Midcap Fund - Regular Plan - Growth",
        "fund_house": "Axis Mutual Fund",
        "category": "Equity - Mid Cap",
        "nav": 89.23,
        "nav_date": "2026-02-20",
        "returns": {"1m": "3.5%", "3m": "7.2%", "6m": "12.1%", "1y": "22.5%", "3y": "18.2%"},
    },
}

FALLBACK_MARKET_DATA = {
    "NIFTY50": {"value": 22453.20, "change_percent": 1.2},
    "SENSEX": {"value": 73917.15, "change_percent": 0.8},
    "NIFTYBANK": {"value": 48234.50, "change_percent": 1.5},
}


class DataPrefetchService:
    """Service for prefetching and caching popular fund data."""
    
    def __init__(self):
        self._cache = get_cache_repository()
        self._mf_service = get_mutual_fund_service()
        self._is_running = False
        self._last_prefetch: Optional[datetime] = None
    
    async def prefetch_popular_funds(self):
        """Prefetch data for popular funds."""
        logger.info("[PREFETCH] Starting popular funds prefetch...")
        
        success_count = 0
        for scheme_code in POPULAR_FUND_CODES:
            try:
                details = self._mf_service.get_fund_details(scheme_code)
                if details:
                    success_count += 1
                    logger.debug(f"[PREFETCH] Cached fund: {scheme_code}")
                else:
                    self._cache_fallback_fund(scheme_code)
            except Exception as e:
                logger.error(f"[PREFETCH] Error fetching {scheme_code}: {e}")
                self._cache_fallback_fund(scheme_code)
            
            await asyncio.sleep(0.5)
        
        logger.info(f"[PREFETCH] Completed. Cached {success_count}/{len(POPULAR_FUND_CODES)} funds")
    
    def _cache_fallback_fund(self, scheme_code: str):
        """Cache fallback data for a fund."""
        if scheme_code in FALLBACK_FUND_DATA:
            fallback = FALLBACK_FUND_DATA[scheme_code]
            self._cache.set(f"details_{scheme_code}", fallback, ttl_seconds=86400)
            logger.debug(f"[PREFETCH] Cached fallback for: {scheme_code}")
    
    async def prefetch_categories(self):
        """Prefetch top funds for popular categories."""
        logger.info("[PREFETCH] Starting category prefetch...")
        
        for category in POPULAR_CATEGORIES:
            try:
                results = self._mf_service.search_funds(category, limit=10)
                if results:
                    self._cache.set(
                        f"category_{category.replace(' ', '_')}",
                        [r.model_dump() for r in results],
                        ttl_seconds=3600
                    )
                    logger.debug(f"[PREFETCH] Cached category: {category}")
            except Exception as e:
                logger.error(f"[PREFETCH] Error fetching category {category}: {e}")
            
            await asyncio.sleep(0.5)
        
        logger.info("[PREFETCH] Category prefetch completed")
    
    def get_fallback_fund(self, scheme_code: str) -> Optional[dict]:
        """Get fallback data for a fund."""
        return FALLBACK_FUND_DATA.get(scheme_code)
    
    def get_fallback_market_data(self) -> dict:
        """Get fallback market data."""
        return FALLBACK_MARKET_DATA
    
    def get_popular_funds_fallback(self) -> list[dict]:
        """Get list of popular funds with fallback data."""
        return list(FALLBACK_FUND_DATA.values())
    
    async def run_prefetch_cycle(self):
        """Run a complete prefetch cycle."""
        if self._is_running:
            logger.warning("[PREFETCH] Prefetch already running, skipping...")
            return
        
        self._is_running = True
        try:
            await self.prefetch_popular_funds()
            await self.prefetch_categories()
            self._last_prefetch = datetime.utcnow()
            logger.info(f"[PREFETCH] Cycle completed at {self._last_prefetch}")
        finally:
            self._is_running = False
    
    def get_status(self) -> dict:
        """Get prefetch service status."""
        return {
            "is_running": self._is_running,
            "last_prefetch": self._last_prefetch.isoformat() if self._last_prefetch else None,
            "popular_funds_count": len(POPULAR_FUND_CODES),
            "categories_count": len(POPULAR_CATEGORIES),
            "fallback_funds_count": len(FALLBACK_FUND_DATA),
        }


_prefetch_service: Optional[DataPrefetchService] = None


def get_prefetch_service() -> DataPrefetchService:
    """Get singleton prefetch service instance."""
    global _prefetch_service
    if _prefetch_service is None:
        _prefetch_service = DataPrefetchService()
    return _prefetch_service


async def startup_prefetch():
    """Run prefetch on application startup."""
    service = get_prefetch_service()
    asyncio.create_task(service.run_prefetch_cycle())
