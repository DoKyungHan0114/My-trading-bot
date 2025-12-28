# TQQQ Algorithmic Trading System

An AI-powered algorithmic trading system for TQQQ (3x leveraged Nasdaq ETF) using RSI(2) mean reversion strategy with automated backtesting, analysis, and execution.

## Overview

This system implements a mean reversion trading strategy that identifies oversold conditions in TQQQ using the 2-period RSI indicator. It features automated backtesting, AI-driven strategy analysis, and real-time execution through the Alpaca brokerage API.

### Key Features

- **Automated Trading**: Real-time signal generation and order execution via Alpaca API
- **AI Strategy Analysis**: Claude AI analyzes backtest results and suggests parameter optimizations
- **Comprehensive Backtesting**: Historical performance analysis with detailed PDF reports
- **Hedge Strategy**: Automatic hedging using SQQQ (inverse ETF) during overbought conditions
- **Web Dashboard**: React-based command runner for monitoring and control
- **Discord Integration**: Real-time trade notifications and daily reports
- **Cloud Deployment**: Production-ready with GCP (Firestore, Compute Engine)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Dashboard                             │
│                    (React + TypeScript)                          │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│         (Command Execution, PDF Reports, Strategy API)           │
└─────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Trading Core │    │ Backtest Engine │    │  Claude AI      │
│  (Execution)  │    │ (Analysis/PDF)  │    │  (Optimizer)    │
└───────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Alpaca API   │    │   Firestore     │    │  Strategy DB    │
│  (Brokerage)  │    │   (Sessions)    │    │  (Versions)     │
└───────────────┘    └─────────────────┘    └─────────────────┘
```

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

### Additional Filters

- **VWAP Filter**: Only enter when price is below VWAP (better entries)
- **SMA Trend**: 20-period SMA for trend confirmation
- **Volume Filter**: Optional minimum volume requirement
- **Bollinger Bands**: Optional volatility-based entries

### Hedge Strategy

When RSI exceeds 90 (extreme overbought), the system:
1. Opens a hedge position in SQQQ (inverse ETF)
2. Closes hedge when RSI drops below 60
3. Limits hedge size to 30% of portfolio

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, Vite |
| **Backend** | Python, FastAPI, Uvicorn |
| **Database** | Google Cloud Firestore |
| **Brokerage** | Alpaca Markets API |
| **AI Analysis** | Claude API (Anthropic) |
| **Notifications** | Discord Webhooks |
| **Infrastructure** | Google Compute Engine |
| **CI/CD** | GitHub Actions |

## Project Structure

```
tqqq-trading-system/
├── api.py                 # FastAPI server
├── main.py                # Trading loop entry point
├── backtest_runner.py     # Backtest orchestrator
├── discord_bot.py         # Discord notifications
├── export_strategy.py     # Strategy export to JSON
│
├── strategy/              # Trading strategy logic
│   ├── signals.py         # Signal generation
│   └── indicators.py      # Technical indicators (RSI, SMA, etc.)
│
├── backtest/              # Backtesting engine
│   ├── engine.py          # Core backtest logic
│   ├── metrics.py         # Performance metrics
│   └── optimizer.py       # Parameter optimization
│
├── automation/            # AI-powered automation
│   ├── claude_analyzer.py # Claude AI integration
│   ├── daily_report.py    # Automated daily reports
│   └── scheduler.py       # Task scheduling
│
├── execution/             # Order execution
│   └── broker.py          # Alpaca API wrapper
│
├── database/              # Data persistence
│   └── firestore.py       # Firestore client
│
├── reports/               # Generated reports
│   └── pdf/               # Backtest PDF reports
│
├── frontend/              # React dashboard
│   └── src/
│       └── App.tsx        # Command runner UI
│
└── deploy/                # Deployment scripts
    └── gce_setup.sh       # GCP setup
```

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Alpaca Trading Account
- Google Cloud Project (for Firestore)

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/tqqq-trading-system.git
cd tqqq-trading-system

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

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
./dev.sh

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### Run Backtest

```bash
# Run 7-day backtest with $10,000 capital
./run_backtest.sh

# Custom parameters
./run_backtest.sh 30 50000  # 30 days, $50,000

# With auto-apply AI suggestions
AUTO_APPLY=true ./run_backtest.sh
```

### Export Strategy

```bash
# Export current strategy to JSON
./export_strategy.py --pretty -o strategy.json
```

### Production

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Start production server
./start-prod.sh
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/commands` | GET | List available commands |
| `/api/commands/{id}/run` | POST | Execute command |
| `/api/commands/{id}/stream` | POST | Execute with streaming output |
| `/api/reports/pdf` | GET | List PDF reports |
| `/api/reports/pdf/latest` | GET | Download latest report |
| `/api/strategies` | GET | List strategy versions |
| `/api/health` | GET | System health check |

## Backtest Results

The system generates comprehensive PDF reports including:

- Equity curve visualization
- Trade history with entry/exit points
- Performance metrics (Sharpe, Sortino, Max Drawdown)
- RSI signal overlay charts
- Win rate and profit factor analysis

## AI-Powered Optimization

Claude AI analyzes backtest results and suggests:

- RSI threshold adjustments
- Stop loss optimization
- Position sizing recommendations
- Filter parameter tuning

Suggestions can be auto-applied or reviewed manually.

## Disclaimer

This software is for educational purposes only. Algorithmic trading involves substantial risk of loss. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred through the use of this system.

## License

MIT License - see [LICENSE](LICENSE) for details.
