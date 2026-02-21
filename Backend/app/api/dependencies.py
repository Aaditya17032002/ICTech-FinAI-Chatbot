from functools import lru_cache
from typing import Generator

from app.config import Settings, get_settings
from app.repositories.cache_repository import CacheRepository, get_cache_repository
from app.repositories.fund_repository import FundRepository, get_fund_repository
from app.repositories.stock_repository import StockRepository, get_stock_repository
from app.services.chat_service import ChatService, get_chat_service
from app.services.mutual_fund_service import MutualFundService, get_mutual_fund_service
from app.services.stock_service import StockService, get_stock_service


def get_settings_dependency() -> Settings:
    """Dependency for settings."""
    return get_settings()


def get_cache_dependency() -> CacheRepository:
    """Dependency for cache repository."""
    return get_cache_repository()


def get_fund_repo_dependency() -> FundRepository:
    """Dependency for fund repository."""
    return get_fund_repository()


def get_stock_repo_dependency() -> StockRepository:
    """Dependency for stock repository."""
    return get_stock_repository()


def get_mf_service_dependency() -> MutualFundService:
    """Dependency for mutual fund service."""
    return get_mutual_fund_service()


def get_stock_service_dependency() -> StockService:
    """Dependency for stock service."""
    return get_stock_service()


def get_chat_service_dependency() -> ChatService:
    """Dependency for chat service."""
    return get_chat_service()
