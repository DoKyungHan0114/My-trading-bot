#!/usr/bin/env python3
"""
Backfill market metadata for existing sessions in Firestore.
Adds regime classification, volatility, and other market conditions.
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.firestore import FirestoreClient
from strategy.regime import RegimeClassifier


def extract_date_from_session(session: dict) -> tuple[str, str]:
    """
    Extract start/end dates from session.
    Sessions store 'date' which is the backtest run date, not the period.
    We need to look at trades or infer from session_id.
    """
    # The date field is when backtest was run, not the period
    # We need to get this from trades or session metadata
    session_date = session.get("date")

    if session_date:
        if hasattr(session_date, 'strftime'):
            # It's a datetime object
            end_date = session_date.strftime("%Y-%m-%d")
        else:
            end_date = str(session_date)[:10]

        # Assume 7-day period (standard backtest)
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=7)
            return start_dt.strftime("%Y-%m-%d"), end_date
        except:
            pass

    return None, None


def backfill_sessions():
    """Backfill all sessions with market metadata."""
    print("=" * 60)
    print("Backfilling Market Metadata")
    print("=" * 60)

    fs = FirestoreClient()
    classifier = RegimeClassifier()

    # Get all sessions
    sessions = fs.get_recent_sessions(limit=500)
    print(f"Found {len(sessions)} sessions to process")

    success = 0
    skipped = 0
    errors = 0

    for i, session in enumerate(sessions):
        session_id = session.get("session_id")

        # Check if already has metadata
        if session.get("market_condition"):
            print(f"[{i+1}/{len(sessions)}] {session_id[:8]}... SKIP (already has metadata)")
            skipped += 1
            continue

        session_date = session.get("date")
        if not session_date:
            print(f"[{i+1}/{len(sessions)}] {session_id[:8]}... SKIP (no date)")
            skipped += 1
            continue

        # Use session date as end, go back 7 days for start
        start_date, end_date = extract_date_from_session(session)

        if not start_date or not end_date:
            print(f"[{i+1}/{len(sessions)}] {session_id[:8]}... SKIP (can't determine dates)")
            skipped += 1
            continue

        print(f"[{i+1}/{len(sessions)}] {session_id[:8]}... {start_date}~{end_date}", end=" ", flush=True)

        try:
            # Classify market conditions
            condition = classifier.classify("TQQQ", start_date, end_date)

            if condition:
                # Update Firestore
                metadata = condition.to_dict()
                metadata["embedding_text"] = condition.to_embedding_text()
                metadata["period_start"] = start_date
                metadata["period_end"] = end_date

                fs._collection("sessions").document(session_id).update({
                    "market_condition": metadata
                })

                print(f"→ {condition.regime.value} ({condition.period_return:+.1f}%)")
                success += 1
            else:
                print("→ SKIP (insufficient data)")
                skipped += 1

        except Exception as e:
            print(f"→ ERROR: {e}")
            errors += 1

        # Rate limit
        time.sleep(0.1)

    print("\n" + "=" * 60)
    print(f"Complete! Success: {success}, Skipped: {skipped}, Errors: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    backfill_sessions()
