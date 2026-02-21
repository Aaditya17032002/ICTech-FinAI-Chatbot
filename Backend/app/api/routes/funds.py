import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import FundSearchResponse, FundDetailResponse, FundSearchResult
from app.services.mutual_fund_service import get_mutual_fund_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/funds", tags=["Funds"])


@router.get("/search", response_model=FundSearchResponse)
async def search_funds(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
) -> FundSearchResponse:
    """
    Search for mutual funds by name or keyword.
    
    Args:
        q: Search query (fund name, AMC name, or category)
        limit: Maximum number of results to return
    
    Returns:
        List of matching funds with basic details
    """
    logger.info(f"Searching funds with query: {q}")
    
    try:
        mf_service = get_mutual_fund_service()
        results = mf_service.search_funds(q, limit)
        
        return FundSearchResponse(
            results=results,
            total=len(results),
        )
    except Exception as e:
        logger.error(f"Error searching funds: {e}")
        raise HTTPException(status_code=500, detail="Error searching funds")


@router.get("/{scheme_code}", response_model=FundDetailResponse)
async def get_fund_details(scheme_code: str) -> FundDetailResponse:
    """
    Get detailed information about a specific mutual fund.
    
    Args:
        scheme_code: AMFI scheme code of the fund
    
    Returns:
        Detailed fund information including NAV, returns, and metadata
    """
    logger.info(f"Getting details for fund: {scheme_code}")
    
    try:
        mf_service = get_mutual_fund_service()
        details = mf_service.get_fund_details(scheme_code)
        
        if not details:
            raise HTTPException(
                status_code=404,
                detail=f"Fund with scheme code {scheme_code} not found"
            )
        
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fund details: {e}")
        raise HTTPException(status_code=500, detail="Error fetching fund details")


@router.get("/{scheme_code}/returns")
async def get_fund_returns(scheme_code: str) -> dict:
    """
    Get returns for a specific fund across different time periods.
    
    Args:
        scheme_code: AMFI scheme code of the fund
    
    Returns:
        Dictionary of period -> return percentage
    """
    logger.info(f"Getting returns for fund: {scheme_code}")
    
    try:
        mf_service = get_mutual_fund_service()
        returns = mf_service.get_fund_returns(scheme_code)
        
        if not returns:
            raise HTTPException(
                status_code=404,
                detail=f"Returns data not available for scheme code {scheme_code}"
            )
        
        return {
            "scheme_code": scheme_code,
            "returns": returns,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fund returns: {e}")
        raise HTTPException(status_code=500, detail="Error fetching fund returns")


@router.post("/compare")
async def compare_funds(scheme_codes: list[str]) -> dict:
    """
    Compare multiple mutual funds side by side.
    
    Args:
        scheme_codes: List of AMFI scheme codes to compare (2-5 funds)
    
    Returns:
        Comparison data for all requested funds
    """
    if len(scheme_codes) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 scheme codes required for comparison"
        )
    
    if len(scheme_codes) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 funds can be compared at once"
        )
    
    logger.info(f"Comparing funds: {scheme_codes}")
    
    try:
        mf_service = get_mutual_fund_service()
        comparison = mf_service.compare_funds(scheme_codes)
        
        return {
            "funds": comparison,
            "total": len(comparison),
        }
    except Exception as e:
        logger.error(f"Error comparing funds: {e}")
        raise HTTPException(status_code=500, detail="Error comparing funds")
