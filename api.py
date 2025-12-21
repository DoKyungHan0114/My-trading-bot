"""
TQQQ Trading System - Dashboard API Server
FastAPI server for the React frontend dashboard
"""

import logging
import os
import json
import sys
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Try to import trading system components
try:
    from config.settings import Settings
    from data.fetcher import DataFetcher
    from strategy.indicators import calculate_rsi, calculate_sma
    from execution.broker import AlpacaBroker
    TRADING_SYSTEM_AVAILABLE = True
except ImportError:
    TRADING_SYSTEM_AVAILABLE = False

# Try to import Firestore and automation components
try:
    from database.firestore import FirestoreClient
    from reports.report_generator import ReportGenerator
    from automation.claude_analyzer import ClaudeAnalyzer
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Initialize Firestore client
_firestore_client: Optional["FirestoreClient"] = None


def get_firestore() -> Optional["FirestoreClient"]:
    """Get or create Firestore client."""
    global _firestore_client
    if not FIRESTORE_AVAILABLE:
        return None
    if _firestore_client is None:
        try:
            _firestore_client = FirestoreClient()
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            return None
    return _firestore_client

app = FastAPI(
    title="TQQQ Trading Dashboard API",
    description="API for TQQQ RSI(2) Mean Reversion Trading System",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response Models
class AccountInfo(BaseModel):
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    daily_pnl: float
    daily_pnl_percent: float

class Position(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float
    entry_date: str

class Signal(BaseModel):
    timestamp: str
    type: str  # BUY, SELL, HOLD
    price: float
    rsi: float
    sma200: float
    reason: str
    strength: float

class Trade(BaseModel):
    id: str
    timestamp: str
    side: str
    symbol: str
    qty: float
    price: float
    total: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None

class SystemStatus(BaseModel):
    mode: str
    is_running: bool
    last_update: str
    market_open: bool

class PriceData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    rsi: Optional[float] = None
    sma200: Optional[float] = None

class DashboardData(BaseModel):
    account: AccountInfo
    position: Optional[Position]
    signal: Optional[Signal]
    trades: list[Trade]
    status: SystemStatus
    price_data: list[PriceData]
    equity_curve: list[dict]

# Mock data for when trading system is not connected
def get_mock_data() -> DashboardData:
    """Generate mock data for demonstration"""
    import random

    now = datetime.now()

    # Generate price data (7 days)
    price_data = []
    price = 65.0
    for i in range(7, -1, -1):
        date = now - timedelta(days=i)
        change = (random.random() - 0.48) * 3
        price = max(50, min(85, price + change))

        price_data.append(PriceData(
            timestamp=date.isoformat(),
            open=price - random.random(),
            high=price + random.random() * 2,
            low=price - random.random() * 2,
            close=price,
            volume=random.randint(10000000, 60000000),
            rsi=min(100, max(0, 50 + (random.random() - 0.5) * 60)),
            sma200=68 + (30 - i) * 0.05
        ))

    # Generate equity curve (7 days)
    equity_curve = []
    equity = 10000.0
    for i in range(7, -1, -1):
        date = now - timedelta(days=i)
        change = (random.random() - 0.45) * 200
        equity = max(8000, equity + change)
        equity_curve.append({
            "date": date.isoformat(),
            "equity": round(equity, 2)
        })

    current_price = price_data[-1].close
    entry_price = 72.45
    qty = 150

    return DashboardData(
        account=AccountInfo(
            equity=12450.32,
            cash=1245.03,
            buying_power=2490.06,
            portfolio_value=11205.29,
            daily_pnl=234.56,
            daily_pnl_percent=1.92
        ),
        position=Position(
            symbol="TQQQ",
            qty=qty,
            avg_entry_price=entry_price,
            current_price=current_price,
            market_value=current_price * qty,
            unrealized_pl=(current_price - entry_price) * qty,
            unrealized_plpc=((current_price - entry_price) / entry_price) * 100,
            entry_date=(now - timedelta(days=2)).isoformat()
        ),
        signal=Signal(
            timestamp=now.isoformat(),
            type="HOLD",
            price=current_price,
            rsi=price_data[-1].rsi or 45.0,
            sma200=price_data[-1].sma200 or 68.0,
            reason="RSI in neutral zone, holding current position",
            strength=0.65
        ),
        trades=[
            Trade(id="1", timestamp=(now - timedelta(days=1)).isoformat(), side="buy", symbol="TQQQ", qty=150, price=72.45, total=10867.50),
            Trade(id="2", timestamp=(now - timedelta(days=3)).isoformat(), side="sell", symbol="TQQQ", qty=120, price=71.20, total=8544.00, pnl=432.00, pnl_percent=5.33),
            Trade(id="3", timestamp=(now - timedelta(days=4)).isoformat(), side="buy", symbol="TQQQ", qty=120, price=67.60, total=8112.00),
            Trade(id="4", timestamp=(now - timedelta(days=5)).isoformat(), side="sell", symbol="TQQQ", qty=100, price=69.80, total=6980.00, pnl=280.00, pnl_percent=4.18),
            Trade(id="5", timestamp=(now - timedelta(days=6)).isoformat(), side="buy", symbol="TQQQ", qty=100, price=67.00, total=6700.00),
        ],
        status=SystemStatus(
            mode="paper",
            is_running=True,
            last_update=now.isoformat(),
            market_open=False
        ),
        price_data=price_data,
        equity_curve=equity_curve
    )


@app.get("/api/dashboard", response_model=DashboardData)
async def get_dashboard():
    """Get all dashboard data in one request"""
    if TRADING_SYSTEM_AVAILABLE:
        try:
            # TODO: Implement real data fetching from trading system
            return get_mock_data()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return get_mock_data()


@app.get("/api/account", response_model=AccountInfo)
async def get_account():
    """Get account information"""
    data = get_mock_data()
    return data.account


@app.get("/api/position", response_model=Optional[Position])
async def get_position():
    """Get current position"""
    data = get_mock_data()
    return data.position


@app.get("/api/signal", response_model=Optional[Signal])
async def get_signal():
    """Get latest trading signal"""
    data = get_mock_data()
    return data.signal


@app.get("/api/trades", response_model=list[Trade])
async def get_trades(limit: int = 10):
    """Get recent trades"""
    data = get_mock_data()
    return data.trades[:limit]


@app.get("/api/prices", response_model=list[PriceData])
async def get_prices(days: int = 7):
    """Get historical price data with indicators (7-day focus)"""
    data = get_mock_data()
    return data.price_data[-days:]


@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    """Get system status"""
    data = get_mock_data()
    return data.status


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    firestore = get_firestore()
    firestore_ok = firestore.health_check() if firestore else False

    return {
        "status": "healthy",
        "trading_system": TRADING_SYSTEM_AVAILABLE,
        "firestore": firestore_ok,
        "timestamp": datetime.now().isoformat()
    }


# =========================================================================
# STRATEGY ENDPOINTS
# =========================================================================

class StrategyResponse(BaseModel):
    strategy_id: str
    parent_id: Optional[str]
    parameters: dict
    created_at: str
    created_by: str
    is_active: bool


class StrategyChangeResponse(BaseModel):
    change_id: str
    from_strategy_id: Optional[str]
    to_strategy_id: str
    reason: str
    changed_at: str


class AnalyzeResponse(BaseModel):
    status: str
    message: str
    report_id: Optional[str] = None
    modifications: list[dict] = []


@app.get("/api/strategies", response_model=list[StrategyResponse])
async def list_strategies(limit: int = 50):
    """Get list of all strategy versions"""
    firestore = get_firestore()
    if not firestore:
        raise HTTPException(
            status_code=503,
            detail="Firestore not available"
        )

    try:
        strategies = firestore.list_strategies(limit=limit)
        return [
            StrategyResponse(
                strategy_id=s["strategy_id"],
                parent_id=s.get("parent_id"),
                parameters=s.get("parameters", {}),
                created_at=s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"]),
                created_by=s.get("created_by", "unknown"),
                is_active=s.get("is_active", False),
            )
            for s in strategies
        ]
    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """Get a specific strategy by ID"""
    firestore = get_firestore()
    if not firestore:
        raise HTTPException(
            status_code=503,
            detail="Firestore not available"
        )

    try:
        strategy = firestore.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        return StrategyResponse(
            strategy_id=strategy["strategy_id"],
            parent_id=strategy.get("parent_id"),
            parameters=strategy.get("parameters", {}),
            created_at=strategy["created_at"].isoformat() if hasattr(strategy["created_at"], "isoformat") else str(strategy["created_at"]),
            created_by=strategy.get("created_by", "unknown"),
            is_active=strategy.get("is_active", False),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/active", response_model=Optional[StrategyResponse])
async def get_active_strategy():
    """Get the currently active strategy"""
    firestore = get_firestore()
    if not firestore:
        raise HTTPException(
            status_code=503,
            detail="Firestore not available"
        )

    try:
        strategy = firestore.get_active_strategy()
        if not strategy:
            return None

        return StrategyResponse(
            strategy_id=strategy["strategy_id"],
            parent_id=strategy.get("parent_id"),
            parameters=strategy.get("parameters", {}),
            created_at=strategy["created_at"].isoformat() if hasattr(strategy["created_at"], "isoformat") else str(strategy["created_at"]),
            created_by=strategy.get("created_by", "unknown"),
            is_active=strategy.get("is_active", False),
        )
    except Exception as e:
        logger.error(f"Failed to get active strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategy-changes", response_model=list[StrategyChangeResponse])
async def list_strategy_changes(limit: int = 50):
    """Get strategy change history"""
    firestore = get_firestore()
    if not firestore:
        raise HTTPException(
            status_code=503,
            detail="Firestore not available"
        )

    try:
        changes = firestore.get_strategy_changes(limit=limit)
        return [
            StrategyChangeResponse(
                change_id=c["change_id"],
                from_strategy_id=c.get("from_strategy_id"),
                to_strategy_id=c["to_strategy_id"],
                reason=c.get("reason", ""),
                changed_at=c["changed_at"].isoformat() if hasattr(c["changed_at"], "isoformat") else str(c["changed_at"]),
            )
            for c in changes
        ]
    except Exception as e:
        logger.error(f"Failed to list strategy changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_analysis_task(auto_apply: bool = False):
    """Background task to run Claude analysis"""
    try:
        firestore = get_firestore()
        report_gen = ReportGenerator()
        analyzer = ClaudeAnalyzer(
            firestore_client=firestore,
            report_generator=report_gen,
        )

        # Generate report
        report = report_gen.generate_report()
        report_gen.save_report(report)

        # Run analysis
        result = analyzer.analyze(
            report=report,
            auto_apply=auto_apply,
            min_confidence=0.5,
        )

        if result:
            logger.info(f"Analysis complete: {result.summary}")
        else:
            logger.warning("Analysis returned no result")

    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def trigger_analysis(
    background_tasks: BackgroundTasks,
    auto_apply: bool = False,
):
    """
    Trigger manual analysis.
    Generates a report and optionally runs Claude analysis.
    """
    if not FIRESTORE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Analysis components not available"
        )

    try:
        # Generate report synchronously for immediate feedback
        report_gen = ReportGenerator()
        report = report_gen.generate_report()
        report_path = report_gen.save_report(report)

        # Run Claude analysis in background
        background_tasks.add_task(run_analysis_task, auto_apply)

        return AnalyzeResponse(
            status="started",
            message="Analysis started in background",
            report_id=report.report_id,
            modifications=[],
        )

    except Exception as e:
        logger.error(f"Failed to start analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions(limit: int = 7):
    """Get recent trading sessions"""
    firestore = get_firestore()
    if not firestore:
        raise HTTPException(
            status_code=503,
            detail="Firestore not available"
        )

    try:
        sessions = firestore.get_recent_sessions(limit=limit)
        return [
            {
                "session_id": s["session_id"],
                "strategy_id": s["strategy_id"],
                "date": s["date"].isoformat() if hasattr(s["date"], "isoformat") else str(s["date"]),
                "total_pnl": s.get("total_pnl", 0),
                "win_rate": s.get("win_rate", 0),
                "max_drawdown": s.get("max_drawdown", 0),
                "sharpe_ratio": s.get("sharpe_ratio", 0),
                "trade_count": s.get("trade_count", 0),
            }
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Serve static files from frontend build
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{path:path}")
    async def serve_frontend_routes(path: str):
        # Serve index.html for all non-API routes (SPA routing)
        file_path = frontend_dist / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
