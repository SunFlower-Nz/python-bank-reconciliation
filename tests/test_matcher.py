"""Tests for the reconciliation matcher engine."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.engine.matcher import ReconciliationEngine
from src.engine.models import (
    MatchConfidence,
    MatchStatus,
    Transaction,
    TransactionType,
)


def make_txn(
    id: str,
    date: str,
    amount: str,
    desc: str = "Test",
    source: str = "bank",
    ref: str = None,
) -> Transaction:
    """Helper to create test transactions."""
    amt = Decimal(amount)
    return Transaction(
        id=id,
        date=datetime.strptime(date, "%Y-%m-%d"),
        amount=amt,
        description=desc,
        type=TransactionType.CREDIT if amt >= 0 else TransactionType.DEBIT,
        reference=ref,
        source=source,
    )


class TestExactMatching:
    """Test exact matching logic."""

    def test_exact_match_same_date_and_amount(self):
        engine = ReconciliationEngine()
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-15", "1000.00", source="internal")]

        results, summary = engine.reconcile(bank, internal)

        matched = [r for r in results if r.is_matched]
        assert len(matched) == 1
        assert matched[0].status == MatchStatus.EXACT
        assert matched[0].confidence == MatchConfidence.HIGH
        assert summary.match_rate == 100.0

    def test_exact_match_with_reference(self):
        engine = ReconciliationEngine()
        bank = [make_txn("B1", "2025-01-15", "500.00", ref="REF001", source="bank")]
        internal = [make_txn("I1", "2025-01-15", "500.00", ref="REF001", source="internal")]

        results, _ = engine.reconcile(bank, internal)
        matched = [r for r in results if r.is_matched]
        assert len(matched) == 1
        assert "reference" in matched[0].match_reason

    def test_no_match_different_date(self):
        engine = ReconciliationEngine(date_tolerance_days=0)
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-20", "1000.00", source="internal")]

        results, summary = engine.reconcile(bank, internal)
        matched = [r for r in results if r.is_matched]
        assert len(matched) == 0

    def test_no_match_different_amount(self):
        engine = ReconciliationEngine(amount_threshold=0.0)
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-15", "1001.00", source="internal")]

        results, summary = engine.reconcile(bank, internal)
        exact = [r for r in results if r.status == MatchStatus.EXACT]
        assert len(exact) == 0


class TestFuzzyMatching:
    """Test fuzzy matching with tolerances."""

    def test_fuzzy_match_within_date_tolerance(self):
        engine = ReconciliationEngine(date_tolerance_days=3)
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-17", "1000.00", source="internal")]

        results, _ = engine.reconcile(bank, internal)
        matched = [r for r in results if r.is_matched]
        assert len(matched) == 1
        assert matched[0].status == MatchStatus.FUZZY
        assert matched[0].date_diff_days == 2

    def test_fuzzy_match_within_amount_threshold(self):
        engine = ReconciliationEngine(amount_threshold=0.05)
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-15", "1040.00", source="internal")]

        results, _ = engine.reconcile(bank, internal)
        matched = [r for r in results if r.is_matched]
        assert len(matched) == 1
        assert matched[0].status == MatchStatus.FUZZY

    def test_no_fuzzy_match_outside_tolerance(self):
        engine = ReconciliationEngine(date_tolerance_days=2, amount_threshold=0.01)
        bank = [make_txn("B1", "2025-01-15", "1000.00", source="bank")]
        internal = [make_txn("I1", "2025-01-20", "1050.00", source="internal")]

        results, summary = engine.reconcile(bank, internal)
        assert summary.total_matched == 0


class TestDuplicateDetection:
    """Test duplicate transaction detection."""

    def test_detect_bank_duplicates(self):
        engine = ReconciliationEngine()
        bank = [
            make_txn("B1", "2025-01-15", "500.00", source="bank"),
            make_txn("B2", "2025-01-15", "500.00", source="bank"),
        ]
        internal = [make_txn("I1", "2025-01-15", "500.00", source="internal")]

        results, summary = engine.reconcile(bank, internal)
        assert summary.total_duplicates >= 1

    def test_detect_internal_duplicates(self):
        engine = ReconciliationEngine()
        bank = [make_txn("B1", "2025-01-15", "500.00", source="bank")]
        internal = [
            make_txn("I1", "2025-01-15", "500.00", source="internal"),
            make_txn("I2", "2025-01-15", "500.00", source="internal"),
        ]

        results, summary = engine.reconcile(bank, internal)
        assert summary.total_duplicates >= 1


class TestMultipleTransactions:
    """Test with multiple transactions."""

    def test_multiple_exact_matches(self):
        engine = ReconciliationEngine()
        bank = [
            make_txn("B1", "2025-01-10", "100.00", source="bank"),
            make_txn("B2", "2025-01-15", "200.00", source="bank"),
            make_txn("B3", "2025-01-20", "300.00", source="bank"),
        ]
        internal = [
            make_txn("I1", "2025-01-10", "100.00", source="internal"),
            make_txn("I2", "2025-01-15", "200.00", source="internal"),
            make_txn("I3", "2025-01-20", "300.00", source="internal"),
        ]

        results, summary = engine.reconcile(bank, internal)
        assert summary.total_matched == 3
        assert summary.match_rate == 100.0

    def test_mixed_matched_and_unmatched(self):
        engine = ReconciliationEngine()
        bank = [
            make_txn("B1", "2025-01-10", "100.00", source="bank"),
            make_txn("B2", "2025-01-15", "999.99", source="bank"),
        ]
        internal = [
            make_txn("I1", "2025-01-10", "100.00", source="internal"),
            make_txn("I2", "2025-01-20", "555.55", source="internal"),
        ]

        results, summary = engine.reconcile(bank, internal)
        assert summary.total_matched == 1
        assert summary.total_unmatched_bank == 1
        assert summary.total_unmatched_internal == 1

    def test_empty_inputs(self):
        engine = ReconciliationEngine()
        results, summary = engine.reconcile([], [])
        assert summary.total_matched == 0
        assert summary.match_rate == 0.0


class TestSummary:
    """Test summary statistics."""

    def test_summary_amounts(self):
        engine = ReconciliationEngine()
        bank = [
            make_txn("B1", "2025-01-10", "100.00", source="bank"),
            make_txn("B2", "2025-01-15", "200.00", source="bank"),
        ]
        internal = [
            make_txn("I1", "2025-01-10", "100.00", source="internal"),
        ]

        _, summary = engine.reconcile(bank, internal)
        assert summary.total_bank_amount == Decimal("300.00")
        assert summary.total_internal_amount == Decimal("100.00")
        assert summary.matched_amount == Decimal("100.00")

    def test_match_rate_calculation(self):
        engine = ReconciliationEngine()
        bank = [
            make_txn("B1", "2025-01-10", "100.00", source="bank"),
            make_txn("B2", "2025-01-15", "200.00", source="bank"),
            make_txn("B3", "2025-01-20", "300.00", source="bank"),
            make_txn("B4", "2025-01-25", "400.00", source="bank"),
        ]
        internal = [
            make_txn("I1", "2025-01-10", "100.00", source="internal"),
            make_txn("I2", "2025-01-15", "200.00", source="internal"),
            make_txn("I3", "2025-01-20", "300.00", source="internal"),
        ]

        _, summary = engine.reconcile(bank, internal)
        assert summary.match_rate == 75.0
