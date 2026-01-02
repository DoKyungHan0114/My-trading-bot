# TQQQ Algorithmic Trading System

An AI-powered algorithmic trading system for TQQQ (3x leveraged Nasdaq ETF) using RSI(2) mean reversion strategy with automated backtesting, RAG-enhanced analysis, and real-time execution.

## Overview

This system implements a production-grade mean reversion trading strategy that identifies oversold conditions in TQQQ using the 2-period RSI indicator. It features AI-driven strategy optimization with RAG (Retrieval-Augmented Generation), high-performance Rust backtesting, and cloud-native deployment on GCP.

### Key Features

- **Automated Trading**: Real-time signal generation and order execution via Alpaca API
- **AI Strategy Analysis**: Claude AI analyzes backtest results with RAG context for parameter optimization
- **RAG System**: TF-IDF based historical session retrieval for context-aware AI suggestions
- **High-Performance Backtesting**: Rust-accelerated engine (~100x faster than Python)
- **Hedge Strategy**: Automatic hedging using SQQQ (inverse ETF) during overbought conditions
- **Web Dashboard**: React-based monitoring and control interface
- **Cloud-Native Deployment**: Docker containers on GCP Cloud Run with auto-scaling
- **Comprehensive Logging**: Audit trail, trade logging, and tax reporting

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                 FRONTEND (React + TypeScript)                  │
└─────────────────────────────┬─────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (Python)                     │
├───────────────────┬───────────────────┬───────────────────────┤
│    Trading Bot    │  Backtest Engine  │   Claude AI + RAG     │
│   (Real-time)     │  (Python / Rust)  │   (Optimization)      │
└─────────┬─────────┴─────────┬─────────┴───────────┬───────────┘
          │                   │                     │
          ▼                   ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Alpaca API    │  │    Firestore    │  │     Discord     │
│ (Broker + Data) │  │ (Sessions/Logs) │  │    (Alerts)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **High-Performance** | Rust (Backtest Engine with LTO optimization) |
| **Database** | Google Cloud Firestore |
| **Brokerage** | Alpaca Markets API |
| **AI/LLM** | Claude API (Anthropic) |
| **RAG** | scikit-learn (TF-IDF), Cosine Similarity |
| **Notifications** | Discord Webhooks |
| **Infrastructure** | GCP Cloud Run, Docker, Cloud Build |
| **Testing** | pytest, pytest-asyncio |

## Trading Strategy

### RSI(2) Mean Reversion

The strategy exploits short-term oversold conditions in leveraged ETFs:

| Parameter | Value | Description |
|-----------|-------|-------------|
| RSI Period | 2 | Ultra short-term momentum |
| Entry Signal | RSI ≤ 30 | Oversold condition |
| Exit Signal | RSI ≥ 75 | Overbought / target reached |
| Stop Loss | 5% | Risk management |
| Position Size | 90% | Capital allocation |

### Signal Filters

- **VWAP Filter**: Enter only when price < VWAP (better entries)
- **SMA Trend**: 20-period SMA for trend confirmation
- **Volume Filter**: Minimum volume requirement
- **Bollinger Bands**: Volatility-based entry validation

### Hedge Strategy (SQQQ)

When RSI exceeds 90 (extreme overbought):
1. Opens hedge position in SQQQ (inverse ETF)
2. Closes hedge when RSI drops below 60
3. Limits hedge size to 30% of portfolio

## RAG System

The RAG (Retrieval-Augmented Generation) system provides historical context to Claude AI for better optimization suggestions.

### How It Works

```
Current Market Condition → TF-IDF Vectorization → Cosine Similarity Search
                                                           ↓
                                               Similar Historical Sessions
                                                           ↓
                                               Context for Claude AI
```

### Features

- **Session Retrieval**: Finds historically similar market conditions
- **Regime-Based Matching**: Filters by market regime (BULL/BEAR, HIGH/LOW volatility)
- **Performance Context**: Provides past strategy performance in similar conditions
- **Automatic Caching**: Reduces computation for repeated queries

### Data Points Used

- Market conditions (regime, volatility, RSI, ATR, volume ratio)
- Strategy parameters (20+ tunable parameters)
- Performance metrics (PnL, win rate, max drawdown, Sharpe ratio)

## Deployment

### Docker Containers

Two separate containers for independent scaling:

**API Server** (`Dockerfile.api`)
- FastAPI + React frontend
- Health check endpoint
- Auto-scaling: 0-3 instances

**Trading Bot** (`Dockerfile.trading-bot`)
- Paper/Live trading modes
- Persistent state management

### GCP Cloud Run Configuration

```yaml
Memory: 512Mi
CPU: 1 core
Concurrency: 80 requests
Auto-scaling: 0-3 instances
Timeout: 300 seconds
Health Probes: startup (12 failures), liveness (3 failures)
```

### CI/CD Pipeline (Cloud Build)

```
GitHub Push → Cloud Build → Container Registry → Cloud Run Deploy
                  ↓
            Run Tests (pytest)
```

### Secrets Management

- Alpaca API keys via GCP Secret Manager
- Firestore credentials via service account
- Environment-specific configuration

## Testing

### Framework

- **pytest** with asyncio support
- Mock fixtures for external dependencies

### Test Fixtures

```python
# Market condition fixtures
sample_ohlcv_data      # Neutral RSI conditions
oversold_ohlcv_data    # Sharp decline (RSI < 30)
overbought_ohlcv_data  # Sharp rise (RSI > 70)

# Mock services
mock_alpaca_account    # Account data
mock_broker            # Full AlpacaBroker mock
mock_discord_notifier  # Discord integration
mock_firestore         # Firestore client
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_backtest.py -v
```

## Performance Optimizations

### Cost Optimization

- **Lazy Initialization**: Firestore/Alpaca clients loaded on first use
- **Caching**: RAG vectors, market data, strategy parameters
- **Auto-scaling**: Min 0 instances when idle (no idle cost)
- **Image Optimization**: Python slim base, no pip cache

### Speed Optimization

- **Rust Backtesting**: ~100x faster than Python implementation
  - LTO (Link-Time Optimization) enabled
  - Single codegen unit for maximum optimization
  - Vectorized indicator calculations
- **Parallel Processing**: Independent API calls run concurrently
- **Data Caching**: Local CSV cache for historical data

### Reliability

- **Retry Logic**: Exponential backoff with jitter (max 3 retries)
- **Graceful Degradation**: Local config fallback if Firestore unavailable
- **Health Checks**: Startup and liveness probes
- **Audit Trail**: Complete trade history for compliance

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Rust (for building backtest engine)
- Alpaca Trading Account
- Google Cloud Project (for Firestore)

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/tqqq-trading-system.git
cd tqqq-trading-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Build Rust backtest engine (optional, for high-performance backtesting)
cd rust && cargo build --release && cd ..

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```bash
# Alpaca API
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id

# Discord (optional)
DISCORD_WEBHOOK_URL=your_webhook_url

# Claude AI (optional)
ANTHROPIC_API_KEY=your_api_key
```

## Usage

### Development

```bash
# Run both backend and frontend
./scripts/dev.sh

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### Run Backtest

```bash
# Run 7-day backtest with $10,000 capital
./scripts/run_backtest.sh

# Custom parameters
./scripts/run_backtest.sh 30 50000  # 30 days, $50,000

# With Claude AI analysis and auto-apply suggestions
AUTO_APPLY=true ./scripts/run_backtest.sh

# Use Rust engine for faster backtesting
./scripts/run_backtest_rust.sh
```

### Production

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Start production server
./scripts/start-prod.sh

# Or use Docker
docker-compose up -d
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | Unified dashboard data |
| `/api/health` | GET | System health check |
| `/api/trading/tick` | POST | Execute one trading iteration |
| `/api/trading/status` | GET | Current bot status |
| `/api/commands` | GET | List available commands |
| `/api/commands/{id}/run` | POST | Execute command |
| `/api/commands/{id}/stream` | POST | Execute with streaming output |
| `/api/reports/pdf` | GET | List PDF reports |
| `/api/reports/pdf/latest` | GET | Download latest report |
| `/api/strategies` | GET | List strategy versions |
| `/api/strategies/active` | GET | Get active strategy |
| `/api/analyze` | POST | Trigger Claude AI analysis |
| `/api/sessions` | GET | Recent trading sessions |

## Firestore Collections

```
tqqq_strategies/
├── strategy_id, parent_id (version chain)
├── parameters: {rsi_period, stop_loss, ...}
├── is_active, created_at, created_by

tqqq_sessions/
├── session_id, strategy_id
├── total_pnl, win_rate, sharpe_ratio
├── market_condition: {regime, volatility}

tqqq_trades/
├── trade_id, strategy_id
├── entry/exit_time, entry/exit_price
├── pnl, pnl_percent, quantity
```

## Backtest Results

The system generates comprehensive PDF reports including:

- **Equity Curve**: Portfolio value over time with drawdown visualization
- **Trade History**: Entry/exit points plotted on price chart
- **Performance Metrics**: Sharpe ratio, Sortino ratio, Max Drawdown, Win Rate
- **RSI Signal Overlay**: RSI indicator with entry/exit signals marked
- **Profit Analysis**: Win rate, profit factor, average win/loss ratio

### Sample Output

```
═══════════════════════════════════════════════════════════════
                    BACKTEST RESULTS SUMMARY
═══════════════════════════════════════════════════════════════
Period:           2024-01-01 to 2024-12-31
Initial Capital:  $10,000.00
Final Value:      $12,234.56
───────────────────────────────────────────────────────────────
Total Return:     +22.35%
Annual Return:    +22.35%
Sharpe Ratio:     1.24
Sortino Ratio:    1.87
Max Drawdown:     -8.45%
───────────────────────────────────────────────────────────────
Total Trades:     47
Win Rate:         68.1%
Profit Factor:    2.31
Avg Win:          +3.2%
Avg Loss:         -1.8%
═══════════════════════════════════════════════════════════════
```

## AI-Powered Optimization

Claude AI analyzes backtest results with RAG context and suggests:

- **RSI Threshold Adjustments**: Fine-tune oversold/overbought levels
- **Stop Loss Optimization**: Dynamic stop loss based on volatility
- **Position Sizing**: Capital allocation recommendations
- **Filter Parameter Tuning**: VWAP, Bollinger, Volume filter adjustments

### Analysis Flow

```
Backtest Results + Market Regime + RAG Historical Context
                          ↓
                    Claude AI Analysis
                          ↓
    ┌─────────────────────┴─────────────────────┐
    ↓                                           ↓
Parameter Modifications              Confidence Score (0-1)
    ↓                                           ↓
    └─────────────────────┬─────────────────────┘
                          ↓
              Auto-Apply (if confidence > 0.5)
                    or Manual Review
```

Suggestions can be auto-applied or reviewed manually before activation.

## Disclaimer

This software is for educational purposes only. Algorithmic trading involves substantial risk of loss. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred through the use of this system.

## License

MIT License - see [LICENSE](LICENSE) for details.
