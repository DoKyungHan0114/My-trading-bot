# TQQQ 트레이딩 시스템 RAG 구현 계획

> **상태**: 나중에 구현 예정 (백테스팅 충분히 쌓인 후)

---

## 목적

시장 상황별 최적 전략을 저장하고, 현재 시장과 유사한 과거 사례를 검색해서 Claude 분석에 활용

**예시**:
- "변동성 높은 하락장에서는 stop_loss 8%가 좋았다"
- "RSI 극단값 + 상승추세에서는 rsi_oversold 35가 효과적이었다"

---

## 구현 프롬프트

```
TQQQ 트레이딩 시스템에 RAG(Retrieval Augmented Generation)를 추가해줘.

## 목적
시장 상황별 최적 전략을 저장하고, 현재 시장과 유사한 과거 사례를 검색해서 Claude 분석에 활용

## 핵심 개념
- "변동성 높은 하락장에서는 stop_loss 8%가 좋았다" 같은 베스트 프랙티스 저장
- 현재 시장 상황과 유사한 과거 성공 사례 자동 검색
- Claude에게 과거 사례를 컨텍스트로 제공

## 구현 요구사항

### 1. Vector DB 설정 (ChromaDB 로컬)
- ChromaDB를 로컬에 설치하고 data/vectordb/ 폴더에 저장
- 컬렉션: market_conditions (시장 상황별 전략 성과)

### 2. 임베딩할 데이터 구조
각 strategy_change 발생 시 다음을 벡터화해서 저장:

{
    "market_vector": [
        rsi_normalized,           # 0-1 (원래 0-100)
        volatility_normalized,    # ATR / price
        volume_ratio,             # 이미 비율
        trend_score,              # bullish=1, neutral=0.5, bearish=0
        above_sma200,             # 1 or 0
    ],
    "strategy_params": {
        "rsi_oversold": 30,
        "rsi_overbought": 75,
        "stop_loss_pct": 0.08,
        "position_size_pct": 0.75
    },
    "performance": {
        "total_pnl": 84.29,
        "win_rate": 100.0,
        "max_drawdown": -4.93
    },
    "success_score": 0.85  # (win_rate/100 * 0.5) + (pnl > 0 ? 0.3 : 0) + (drawdown < 5% ? 0.2 : 0)
}

### 3. 검색 로직
현재 시장 상황의 market_vector로 유사도 검색:
- Top 5 유사 사례 검색
- success_score > 0.6인 것만 필터링
- 해당 사례들의 전략 파라미터와 성과를 Claude에 전달

### 4. Claude 프롬프트 확장
automation/claude_analyzer.py의 ANALYSIS_PROMPT_TEMPLATE에 추가:

## Historical Best Practices (RAG Retrieved)
다음은 현재와 유사한 시장 상황에서 성공했던 전략들입니다:

{rag_context}

위 과거 사례를 참고하여 현재 상황에 맞는 전략을 추천하세요.

### 5. 파일 구조
rag/
├── __init__.py
├── embeddings.py      # 시장 상황 → 벡터 변환
├── vectorstore.py     # ChromaDB 래퍼
├── retriever.py       # 유사 사례 검색
└── context_builder.py # Claude 프롬프트용 컨텍스트 생성

### 6. 통합 포인트
- backtest_runner.py: 백테스트 완료 후 결과를 Vector DB에 저장
- claude_analyzer.py: 분석 전 유사 사례 검색 후 프롬프트에 추가

### 7. 선행 조건
- 최소 50개 이상의 strategy_changes 데이터 축적
- 다양한 시장 상황(상승/하락/횡보, 고변동/저변동) 커버
```

---

## 현재 시스템에서 RAG에 활용 가능한 데이터

| 데이터 | 위치 | 용도 |
|--------|------|------|
| MarketCondition | reports/report_generator.py:22-34 | 시장 상황 벡터화 |
| strategy_changes | database/firestore.py:360-391 | 과거 사례 저장소 |
| PerformanceSummary | reports/report_generator.py:52-65 | 성과 점수 계산 |
| ANALYSIS_PROMPT | automation/claude_analyzer.py:45-102 | RAG 컨텍스트 주입 |

---

## 예상 효과

1. **일관성**: 유사 시장에서 검증된 전략 재사용
2. **학습**: 시간이 지날수록 추천 정확도 향상
3. **설명가능성**: "과거 이 조건에서 +3.2% 수익" 근거 제시
