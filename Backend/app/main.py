import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.routes import chat, funds, health, market, profile, recommend

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    cache_dir = Path(settings.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    from app.services.data_prefetch_service import startup_prefetch
    await startup_prefetch()
    
    logger.info("Application startup complete")
    
    yield
    
    logger.info("Application shutting down")
    from app.repositories.cache_repository import get_cache_repository
    try:
        cache = get_cache_repository()
        cache.close()
    except Exception as e:
        logger.error(f"Error closing cache: {e}")
    
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Investment Insight Chatbot API - A multi-agent AI system for investment advice.
    
    ## Features
    - Real-time mutual fund data from AMFI India
    - Stock market data from Yahoo Finance
    - AI-powered investment insights using PydanticAI
    - Conversation memory for contextual responses
    - Response caching for improved performance
    - Streaming responses via SSE
    
    ## Disclaimer
    This API provides information for educational purposes only. 
    Investment decisions should be made after consulting a qualified financial advisor.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again later.",
        },
    )


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(funds.router, prefix=settings.api_prefix)
app.include_router(market.router, prefix=settings.api_prefix)
app.include_router(profile.router, prefix=settings.api_prefix)
app.include_router(recommend.router, prefix=settings.api_prefix)

# Static files directory for frontend build
STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/api-info")
async def api_info():
    """API information endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Investment Insight Chatbot API",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
        "endpoints": {
            "chat": f"{settings.api_prefix}/chat",
            "chat_stream": f"{settings.api_prefix}/chat/stream",
            "funds_search": f"{settings.api_prefix}/funds/search",
            "fund_details": f"{settings.api_prefix}/funds/{{scheme_code}}",
            "user_profile": f"{settings.api_prefix}/profile",
            "market_ticker": f"{settings.api_prefix}/market/ticker",
        },
    }


# Mount static assets if frontend is built
if STATIC_DIR.exists() and (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")


@app.get("/")
async def root():
    """Serve frontend index.html or API info."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Investment Insight Chatbot API",
        "docs": "/docs",
        "message": "Frontend not built. Run 'npm run build' in Frontend folder.",
    }


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Catch-all route for SPA - serves index.html for client-side routing."""
    # Skip API routes and docs
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    
    # Try to serve static file first
    static_file = STATIC_DIR / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)
    
    # Fall back to index.html for SPA routing
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    
    return JSONResponse(status_code=404, content={"detail": "Not found"})


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
