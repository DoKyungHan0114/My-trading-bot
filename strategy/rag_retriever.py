"""
RAG Retriever for trading strategy optimization.
Uses TF-IDF for similarity matching on market conditions.
"""
import numpy as np
from typing import Optional
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.firestore import FirestoreClient


@dataclass
class SimilarSession:
    """A similar historical session."""
    session_id: str
    similarity_score: float
    period_start: str
    period_end: str
    total_pnl: float
    win_rate: float
    trade_count: int
    market_condition: dict
    strategy_params: dict


class RAGRetriever:
    """
    Retrieves similar historical sessions based on market conditions.
    Uses TF-IDF vectorization for text similarity matching.
    """

    def __init__(self):
        self.fs = FirestoreClient()
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),  # Capture "BULL_HIGH" as single token
            token_pattern=r'[A-Za-z0-9_]+|[+-]?\d+\.?\d*%?',
        )
        self._sessions_cache = None
        self._vectors_cache = None

    def _load_sessions(self, limit: int = 500) -> list[dict]:
        """Load sessions from Firestore."""
        if self._sessions_cache is None:
            sessions = self.fs.get_recent_sessions(limit=limit)
            # Filter to only sessions with market_condition
            self._sessions_cache = [
                s for s in sessions
                if s.get('market_condition') and s.get('market_condition', {}).get('embedding_text')
            ]
        return self._sessions_cache

    def _build_vectors(self):
        """Build TF-IDF vectors for all sessions."""
        if self._vectors_cache is not None:
            return

        sessions = self._load_sessions()
        if not sessions:
            self._vectors_cache = None
            return

        # Extract embedding texts
        texts = [s['market_condition']['embedding_text'] for s in sessions]

        # Fit and transform
        self._vectors_cache = self.vectorizer.fit_transform(texts)

    def find_similar(
        self,
        current_condition_text: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> list[SimilarSession]:
        """
        Find similar historical sessions based on market condition.

        Args:
            current_condition_text: Embedding text for current market condition
            top_k: Number of similar sessions to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of SimilarSession objects, sorted by similarity (highest first)
        """
        self._build_vectors()

        if self._vectors_cache is None:
            return []

        sessions = self._load_sessions()

        # Transform current condition
        query_vector = self.vectorizer.transform([current_condition_text])

        # Calculate similarities
        similarities = cosine_similarity(query_vector, self._vectors_cache)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # Get more to filter

        results = []
        for idx in top_indices:
            if similarities[idx] < min_similarity:
                continue

            session = sessions[idx]
            mc = session.get('market_condition', {})

            # Get strategy parameters from the session
            strategy_params = self._get_strategy_params(session)

            results.append(SimilarSession(
                session_id=session.get('session_id', ''),
                similarity_score=float(similarities[idx]),
                period_start=session.get('period_start', 'N/A'),
                period_end=session.get('period_end', 'N/A'),
                total_pnl=session.get('total_pnl', 0),
                win_rate=session.get('win_rate', 0),
                trade_count=session.get('trade_count', 0),
                market_condition=mc,
                strategy_params=strategy_params,
            ))

            if len(results) >= top_k:
                break

        return results

    def _get_strategy_params(self, session: dict) -> dict:
        """Extract strategy parameters from session."""
        strategy_id = session.get('strategy_id')
        if not strategy_id:
            return {}

        # Get strategy details
        try:
            strategy = self.fs.get_strategy(strategy_id)
            if strategy:
                return strategy.get('parameters', {})
        except Exception:
            pass

        return {}

    def find_similar_by_regime(
        self,
        regime: str,
        volatility: str,
        top_k: int = 10,
    ) -> list[SimilarSession]:
        """
        Find similar sessions by regime and volatility.

        Args:
            regime: Market regime (e.g., "BULL_HIGH_VOL", "BEAR_LOW_VOL")
            volatility: Volatility level ("LOW", "MEDIUM", "HIGH")
            top_k: Number of sessions to return

        Returns:
            List of matching sessions, sorted by PnL (best first)
        """
        sessions = self._load_sessions()

        matching = []
        for session in sessions:
            mc = session.get('market_condition', {})
            if mc.get('regime') == regime or mc.get('volatility') == volatility:
                strategy_params = self._get_strategy_params(session)
                matching.append(SimilarSession(
                    session_id=session.get('session_id', ''),
                    similarity_score=1.0 if mc.get('regime') == regime else 0.5,
                    period_start=session.get('period_start', 'N/A'),
                    period_end=session.get('period_end', 'N/A'),
                    total_pnl=session.get('total_pnl', 0),
                    win_rate=session.get('win_rate', 0),
                    trade_count=session.get('trade_count', 0),
                    market_condition=mc,
                    strategy_params=strategy_params,
                ))

        # Sort by PnL (best performing first)
        matching.sort(key=lambda x: x.total_pnl, reverse=True)
        return matching[:top_k]

    def get_regime_performance_summary(self) -> dict:
        """
        Get performance summary grouped by market regime.

        Returns:
            Dict mapping regime to performance stats
        """
        sessions = self._load_sessions()

        regime_stats = {}
        for session in sessions:
            mc = session.get('market_condition', {})
            regime = mc.get('regime', 'UNKNOWN')

            if regime not in regime_stats:
                regime_stats[regime] = {
                    'count': 0,
                    'total_pnl': 0,
                    'winning': 0,
                    'avg_win_rate': 0,
                    'pnl_list': [],
                }

            stats = regime_stats[regime]
            stats['count'] += 1
            stats['total_pnl'] += session.get('total_pnl', 0)
            stats['pnl_list'].append(session.get('total_pnl', 0))
            stats['avg_win_rate'] += session.get('win_rate', 0)
            if session.get('total_pnl', 0) > 0:
                stats['winning'] += 1

        # Calculate averages
        for regime, stats in regime_stats.items():
            if stats['count'] > 0:
                stats['avg_pnl'] = stats['total_pnl'] / stats['count']
                stats['avg_win_rate'] = stats['avg_win_rate'] / stats['count']
                stats['regime_win_rate'] = stats['winning'] / stats['count'] * 100
                stats['median_pnl'] = float(np.median(stats['pnl_list']))
                stats['std_pnl'] = float(np.std(stats['pnl_list']))
            del stats['pnl_list']  # Remove raw list

        return regime_stats

    def get_rag_context(
        self,
        current_condition_text: str,
        current_regime: str,
        current_volatility: str,
    ) -> str:
        """
        Generate RAG context for Claude analyzer.

        Args:
            current_condition_text: Current market condition embedding text
            current_regime: Current market regime
            current_volatility: Current volatility level

        Returns:
            Formatted context string for Claude prompt
        """
        # Get similar sessions
        similar = self.find_similar(current_condition_text, top_k=5)

        # Get regime-specific performance
        regime_stats = self.get_regime_performance_summary()
        current_stats = regime_stats.get(current_regime, {})

        # Build context
        context_parts = []

        # Overall regime statistics
        context_parts.append("## Historical Performance by Regime")
        for regime, stats in sorted(regime_stats.items()):
            context_parts.append(
                f"- {regime}: {stats['count']} sessions, "
                f"Avg PnL: {stats.get('avg_pnl', 0):+.2f}%, "
                f"Win Rate: {stats.get('regime_win_rate', 0):.1f}%"
            )

        # Current regime specific
        if current_stats:
            context_parts.append(f"\n## Current Regime: {current_regime}")
            context_parts.append(
                f"Based on {current_stats['count']} historical sessions with similar conditions:\n"
                f"- Average PnL: {current_stats.get('avg_pnl', 0):+.2f}%\n"
                f"- Median PnL: {current_stats.get('median_pnl', 0):+.2f}%\n"
                f"- Std Dev: {current_stats.get('std_pnl', 0):.2f}%\n"
                f"- Win Rate: {current_stats.get('regime_win_rate', 0):.1f}%"
            )

        # Similar sessions with their parameters
        if similar:
            context_parts.append("\n## Most Similar Historical Sessions")
            for i, s in enumerate(similar, 1):
                mc = s.market_condition
                params_str = ""
                if s.strategy_params:
                    p = s.strategy_params
                    params_str = (
                        f" | RSI: {p.get('rsi_oversold', 'N/A')}/{p.get('rsi_overbought', 'N/A')}, "
                        f"SL: {p.get('stop_loss_pct', 'N/A')}%"
                    )

                context_parts.append(
                    f"{i}. [{s.period_start}~{s.period_end}] "
                    f"Similarity: {s.similarity_score:.2f} | "
                    f"PnL: {s.total_pnl:+.2f}% | "
                    f"WR: {s.win_rate:.1f}% | "
                    f"{mc.get('regime', 'N/A')}{params_str}"
                )

        # Best performing strategies for this regime
        best_for_regime = self.find_similar_by_regime(current_regime, current_volatility, top_k=3)
        if best_for_regime:
            context_parts.append("\n## Best Performing Strategies for This Regime")
            for i, s in enumerate(best_for_regime, 1):
                if s.strategy_params:
                    p = s.strategy_params
                    context_parts.append(
                        f"{i}. PnL: {s.total_pnl:+.2f}% | "
                        f"RSI: {p.get('rsi_oversold', 10)}/{p.get('rsi_overbought', 90)}, "
                        f"Stop: {p.get('stop_loss_pct', 5)}%, "
                        f"Trail: {p.get('trailing_stop_pct', 'N/A')}%"
                    )

        return "\n".join(context_parts)

    def refresh_cache(self):
        """Clear caches to reload fresh data."""
        self._sessions_cache = None
        self._vectors_cache = None


if __name__ == "__main__":
    # Test the retriever
    from strategy.regime import RegimeClassifier

    retriever = RAGRetriever()
    classifier = RegimeClassifier()

    # Get current market condition
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    condition = classifier.classify("TQQQ", start_date, end_date)

    if condition:
        print(f"Current Condition: {condition.regime.value}")
        print(f"Embedding: {condition.to_embedding_text()}")
        print("\n" + "="*60)

        # Get RAG context
        context = retriever.get_rag_context(
            condition.to_embedding_text(),
            condition.regime.value,
            condition.volatility.value,
        )
        print("\nRAG Context for Claude:")
        print(context)
    else:
        print("Could not classify current market condition")

        # Show regime stats anyway
        print("\nRegime Performance Summary:")
        stats = retriever.get_regime_performance_summary()
        for regime, s in sorted(stats.items()):
            print(f"  {regime}: {s['count']} sessions, Avg: {s.get('avg_pnl', 0):+.2f}%")
