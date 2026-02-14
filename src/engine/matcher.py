"""Core reconciliation matching engine."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.engine.models import (
    MatchConfidence,
    MatchResult,
    MatchStatus,
    ReconciliationSummary,
    Transaction,
)


class ReconciliationEngine:
    """
    Reconciliation engine that matches bank transactions against internal records.

    Matching Strategy:
    1. Exact Match: Same date, same amount, same reference (if available)
    2. Fuzzy Match: Date within tolerance, amount within threshold
    3. Duplicate Detection: Multiple transactions with same amount on same/close dates
    """

    def __init__(
        self,
        date_tolerance_days: int = 3,
        amount_threshold: float = 0.02,
    ):
        """
        Initialize the reconciliation engine.

        Args:
            date_tolerance_days: Maximum number of days difference for fuzzy matching.
            amount_threshold: Maximum relative amount difference for fuzzy matching (0.02 = 2%).
        """
        self.date_tolerance = timedelta(days=date_tolerance_days)
        self.amount_threshold = Decimal(str(amount_threshold))

    def reconcile(
        self,
        bank_transactions: List[Transaction],
        internal_transactions: List[Transaction],
    ) -> Tuple[List[MatchResult], ReconciliationSummary]:
        """
        Perform reconciliation between bank and internal transactions.

        Args:
            bank_transactions: Transactions from bank statement.
            internal_transactions: Transactions from internal records.

        Returns:
            Tuple of (list of match results, summary statistics).
        """
        results: List[MatchResult] = []
        matched_internal: set = set()

        # Build index for faster lookup
        internal_index = self._build_amount_index(internal_transactions)

        # Phase 1: Exact matches
        for bank_txn in bank_transactions:
            match = self._find_exact_match(bank_txn, internal_index, matched_internal)
            if match:
                results.append(match)
                matched_internal.add(match.internal_transaction.id)

        # Phase 2: Fuzzy matches for remaining
        unmatched_bank = [
            txn for txn in bank_transactions
            if not any(r.bank_transaction.id == txn.id and r.is_matched for r in results)
        ]

        for bank_txn in unmatched_bank:
            match = self._find_fuzzy_match(bank_txn, internal_transactions, matched_internal)
            if match:
                results.append(match)
                matched_internal.add(match.internal_transaction.id)
            else:
                results.append(MatchResult(
                    bank_transaction=bank_txn,
                    internal_transaction=None,
                    status=MatchStatus.UNMATCHED_BANK,
                    confidence=MatchConfidence.LOW,
                    match_reason="No matching internal transaction found",
                ))

        # Phase 3: Unmatched internal transactions
        for int_txn in internal_transactions:
            if int_txn.id not in matched_internal:
                results.append(MatchResult(
                    bank_transaction=None,
                    internal_transaction=int_txn,
                    status=MatchStatus.UNMATCHED_INTERNAL,
                    confidence=MatchConfidence.LOW,
                    match_reason="No matching bank transaction found",
                ))

        # Phase 4: Detect duplicates
        duplicates = self._detect_duplicates(bank_transactions, internal_transactions)
        results.extend(duplicates)

        # Generate summary
        summary = self._generate_summary(results, bank_transactions, internal_transactions)

        return results, summary

    def _build_amount_index(
        self, transactions: List[Transaction]
    ) -> Dict[Decimal, List[Transaction]]:
        """Build an index of transactions by absolute amount for fast lookup."""
        index: Dict[Decimal, List[Transaction]] = defaultdict(list)
        for txn in transactions:
            index[txn.abs_amount].append(txn)
        return index

    def _find_exact_match(
        self,
        bank_txn: Transaction,
        internal_index: Dict[Decimal, List[Transaction]],
        matched: set,
    ) -> Optional[MatchResult]:
        """Find an exact match for a bank transaction."""
        candidates = internal_index.get(bank_txn.abs_amount, [])

        for int_txn in candidates:
            if int_txn.id in matched:
                continue

            # Check exact date match
            if bank_txn.date.date() != int_txn.date.date():
                continue

            # Check reference match (if both have references)
            if (
                bank_txn.reference
                and int_txn.reference
                and bank_txn.reference != int_txn.reference
            ):
                continue

            return MatchResult(
                bank_transaction=bank_txn,
                internal_transaction=int_txn,
                status=MatchStatus.EXACT,
                confidence=MatchConfidence.HIGH,
                date_diff_days=0,
                amount_diff=Decimal("0"),
                match_reason="Exact match: same date, amount" + (
                    ", and reference" if bank_txn.reference and int_txn.reference else ""
                ),
            )

        return None

    def _find_fuzzy_match(
        self,
        bank_txn: Transaction,
        internal_transactions: List[Transaction],
        matched: set,
    ) -> Optional[MatchResult]:
        """Find a fuzzy match within date and amount tolerances."""
        best_match: Optional[MatchResult] = None
        best_score = float("inf")

        for int_txn in internal_transactions:
            if int_txn.id in matched:
                continue

            # Check date tolerance
            date_diff = abs((bank_txn.date.date() - int_txn.date.date()).days)
            if date_diff > self.date_tolerance.days:
                continue

            # Check amount tolerance
            amount_diff = abs(bank_txn.abs_amount - int_txn.abs_amount)
            if bank_txn.abs_amount == Decimal("0") and int_txn.abs_amount == Decimal("0"):
                amount_diff_pct = Decimal("0")
            elif bank_txn.abs_amount == Decimal("0"):
                continue
            else:
                amount_diff_pct = amount_diff / bank_txn.abs_amount

            if amount_diff_pct > self.amount_threshold:
                continue

            # Score: lower is better (prefer closer dates and amounts)
            score = date_diff + float(amount_diff_pct) * 100

            if score < best_score:
                best_score = score
                best_match = MatchResult(
                    bank_transaction=bank_txn,
                    internal_transaction=int_txn,
                    status=MatchStatus.FUZZY,
                    confidence=MatchConfidence.MEDIUM if date_diff <= 1 else MatchConfidence.LOW,
                    date_diff_days=date_diff,
                    amount_diff=abs(bank_txn.amount - int_txn.amount),
                    match_reason=(
                        f"Fuzzy match: {date_diff}d date diff, "
                        f"{amount_diff_pct:.2%} amount diff"
                    ),
                )

        return best_match

    def _detect_duplicates(
        self,
        bank_transactions: List[Transaction],
        internal_transactions: List[Transaction],
    ) -> List[MatchResult]:
        """Detect potential duplicate transactions."""
        duplicates: List[MatchResult] = []

        # Check for duplicates within bank transactions
        bank_by_key: Dict[str, List[Transaction]] = defaultdict(list)
        for txn in bank_transactions:
            key = f"{txn.date.date()}|{txn.abs_amount}"
            bank_by_key[key].append(txn)

        for key, txns in bank_by_key.items():
            if len(txns) > 1:
                for txn in txns[1:]:  # Flag all but the first as duplicates
                    duplicates.append(MatchResult(
                        bank_transaction=txn,
                        internal_transaction=None,
                        status=MatchStatus.DUPLICATE,
                        confidence=MatchConfidence.MEDIUM,
                        match_reason=f"Potential duplicate: {len(txns)} bank transactions "
                                     f"with same date and amount",
                    ))

        # Check for duplicates within internal transactions
        internal_by_key: Dict[str, List[Transaction]] = defaultdict(list)
        for txn in internal_transactions:
            key = f"{txn.date.date()}|{txn.abs_amount}"
            internal_by_key[key].append(txn)

        for key, txns in internal_by_key.items():
            if len(txns) > 1:
                for txn in txns[1:]:
                    duplicates.append(MatchResult(
                        bank_transaction=None,
                        internal_transaction=txn,
                        status=MatchStatus.DUPLICATE,
                        confidence=MatchConfidence.MEDIUM,
                        match_reason=f"Potential duplicate: {len(txns)} internal transactions "
                                     f"with same date and amount",
                    ))

        return duplicates

    def _generate_summary(
        self,
        results: List[MatchResult],
        bank_transactions: List[Transaction],
        internal_transactions: List[Transaction],
    ) -> ReconciliationSummary:
        """Generate reconciliation summary statistics."""
        summary = ReconciliationSummary(
            total_bank_transactions=len(bank_transactions),
            total_internal_transactions=len(internal_transactions),
        )

        for result in results:
            if result.status == MatchStatus.EXACT:
                summary.total_matched += 1
                summary.total_exact_matches += 1
                if result.bank_transaction:
                    summary.matched_amount += result.bank_transaction.abs_amount
            elif result.status == MatchStatus.FUZZY:
                summary.total_matched += 1
                summary.total_fuzzy_matches += 1
                if result.bank_transaction:
                    summary.matched_amount += result.bank_transaction.abs_amount
            elif result.status == MatchStatus.UNMATCHED_BANK:
                summary.total_unmatched_bank += 1
                if result.bank_transaction:
                    summary.unmatched_bank_amount += result.bank_transaction.abs_amount
            elif result.status == MatchStatus.UNMATCHED_INTERNAL:
                summary.total_unmatched_internal += 1
                if result.internal_transaction:
                    summary.unmatched_internal_amount += result.internal_transaction.abs_amount
            elif result.status == MatchStatus.DUPLICATE:
                summary.total_duplicates += 1

        summary.total_bank_amount = sum(t.abs_amount for t in bank_transactions)
        summary.total_internal_amount = sum(t.abs_amount for t in internal_transactions)

        return summary
