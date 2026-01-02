# TQQQ 트레이딩 시스템 RAG 구현 계획

> **상태**: 1단계 구현 완료 (TF-IDF 기반), Vector DB 업그레이드 예정

---

## 목적

시장 상황별 최적 전략을 저장하고, 현재 시장과 유사한 과거 사례를 검색해서 Claude 분석에 활용

**예시**:
- "변동성 높은 하락장에서는 stop_loss 8%가 좋았다"
- "RSI 극단값 + 상승추세에서는 rsi_oversold 35가 효과적이었다"

---

## 현재 구현 상태

### 구현 완료
- `strategy/rag_retriever.py`: TF-IDF 기반 유사도 검색
- `automation/claude_analyzer.py`: RAG 컨텍스트를 Claude 프롬프트에 주입
- Firestore에서 과거 세션 데이터 조회

### 현재 방식의 한계
| 항목 | 현재 | 문제점 |
|------|------|--------|
| 임베딩 | TF-IDF (텍스트) | 의미론적 유사성 못 잡음 |
| 저장소 | Firestore | 벡터 검색에 최적화 안됨 |
| 검색 | 전체 로드 후 계산 | 데이터 많아지면 느림 |
| 벡터화 | 텍스트 기반 | 수치 데이터 활용 부족 |

---

## 구현 우선순위

| 순위 | 작업 | 난이도 | 효과 | 상태 |
|------|------|--------|------|------|
| 1 | ChromaDB 설치 및 연동 | 낮음 | 높음 | 예정 |
| 2 | 수치 벡터 임베딩 구현 | 중간 | 높음 | 예정 |
| 3 | 백테스트 결과 자동 저장 | 낮음 | 중간 | 예정 |
| 4 | Semantic embedding 추가 | 중간 | 중간 | 예정 |
| 5 | 하이브리드 검색 | 높음 | 높음 | 예정 |

---

## 1단계: ChromaDB 설치 및 연동

### 설치
```bash
pip install chromadb
```

### 파일 구조
```
rag/
├── __init__.py
├── vectorstore.py     # ChromaDB 래퍼
├── embeddings.py      # 시장 상황 → 벡터 변환
├── retriever.py       # 유사 사례 검색 (기존 rag_retriever.py 대체)
└── context_builder.py # Claude 프롬프트용 컨텍스트 생성
```

### 구현 내용
- ChromaDB를 `data/vectordb/` 폴더에 로컬 저장
- 컬렉션: `market_conditions`
- 기존 Firestore 데이터를 ChromaDB로 마이그레이션

---

## 2단계: 수치 벡터 임베딩 구현

### 임베딩 데이터 구조
```python
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
    "success_score": 0.85
}
```

### Success Score 계산
```python
success_score = (
    (win_rate / 100) * 0.5 +      # 승률 기여
    (0.3 if pnl > 0 else 0) +     # 수익 여부
    (0.2 if drawdown < 5 else 0)  # 낮은 드로다운
)
```

---

## 3단계: 백테스트 결과 자동 저장

### 통합 포인트
- `backtest_runner.py`: 백테스트 완료 후 Vector DB에 자동 저장
- `strategy/regime.py`: 시장 상황 분류 결과 포함

### 저장 시점
1. 백테스트 완료 시
2. strategy_change 발생 시
3. 주간 리포트 생성 시

---

## 4단계: Semantic Embedding 추가

### 목적
텍스트 설명("변동성 높은 하락장")의 의미론적 유사성 검색

### 구현
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
text_embedding = model.encode("변동성 높은 하락장, RSI 과매도 구간")
```

### 설치
```bash
pip install sentence-transformers
```

---

## 5단계: 하이브리드 검색

### 개념
수치 벡터 + 텍스트 임베딩을 결합한 검색

### 구현
```python
def hybrid_search(market_vector, text_query, alpha=0.7):
    """
    alpha: 수치 벡터 가중치 (1-alpha: 텍스트 가중치)
    """
    numeric_results = search_by_vector(market_vector)
    semantic_results = search_by_text(text_query)

    # 가중치 결합
    final_score = alpha * numeric_score + (1-alpha) * semantic_score
    return sorted_by_final_score
```

### 검색 로직
1. 현재 시장 상황의 market_vector로 유사도 검색
2. Top 5 유사 사례 검색
3. success_score > 0.6인 것만 필터링
4. 해당 사례들의 전략 파라미터와 성과를 Claude에 전달

---

## Claude 프롬프트 확장

`automation/claude_analyzer.py`의 ANALYSIS_PROMPT_TEMPLATE에 추가:

```
## Historical Best Practices (RAG Retrieved)
다음은 현재와 유사한 시장 상황에서 성공했던 전략들입니다:

{rag_context}

위 과거 사례를 참고하여 현재 상황에 맞는 전략을 추천하세요.
```

---

## 현재 시스템에서 RAG에 활용 가능한 데이터

| 데이터 | 위치 | 용도 |
|--------|------|------|
| MarketCondition | reports/report_generator.py:22-34 | 시장 상황 벡터화 |
| strategy_changes | database/firestore.py:360-391 | 과거 사례 저장소 |
| PerformanceSummary | reports/report_generator.py:52-65 | 성과 점수 계산 |
| ANALYSIS_PROMPT | automation/claude_analyzer.py:45-102 | RAG 컨텍스트 주입 |
| RAGRetriever | strategy/rag_retriever.py | 현재 TF-IDF 기반 검색 |

---

## 선행 조건

- [x] 기본 RAG 구조 구현 (TF-IDF)
- [ ] 최소 50개 이상의 strategy_changes 데이터 축적
- [ ] 다양한 시장 상황(상승/하락/횡보, 고변동/저변동) 커버

---

## 예상 효과

1. **속도**: Vector DB로 밀리초 단위 검색 (현재: 전체 스캔)
2. **정확도**: 수치 벡터로 정확한 시장 유사도 계산
3. **일관성**: 유사 시장에서 검증된 전략 재사용
4. **학습**: 시간이 지날수록 추천 정확도 향상
5. **설명가능성**: "과거 이 조건에서 +3.2% 수익" 근거 제시
