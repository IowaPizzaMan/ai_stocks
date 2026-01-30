from .stocks import router as stocks_router
from .data import router as data_router
from .analysis import router as analysis_router
from .watchlists import router as watchlists_router

__all__ = ["stocks_router", "data_router", "analysis_router", "watchlists_router"]
