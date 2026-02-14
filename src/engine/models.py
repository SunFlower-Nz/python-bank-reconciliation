"""Data models for the reconciliation engine."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class TransactionType(Enum):
    """Transaction type classification."""
    CREDIT = "credit"
    DEBIT = "debit"


class MatchStatus(Enum):
    """Status of a reconciliation match."""
    EXACT = "exact"
    FUZZY = "fuzzy"
    UNMATCHED_BANK = "unmatched_bank"
    UNMATCHED_INTERNAL = "unmatched_internal"
    DUPLICATE = "duplicate"


class MatchConfidence(Enum):
    """Confidence level of a match."""
    HIGH = "high"        # Exact match on all fields
    MEDIUM = "medium"    # Fuzzy match within tolerance
    LOW = "low"          # Partial match, needs review


@dataclass
class Transaction:
    """Represents a single financial transaction."""
    id: str
    date: datetime
    amount: Decimal
    description: str
    type: TransactionType
    reference: Optional[str] = None
    source: str = ""  # "bank" or "internal"
    raw_data: dict = field(default_factory=dict)

    @property
    def abs_amount(self) -> Decimal:
        """Return absolute value of transaction amount."""
        return abs(self.amount)

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, date={self.date.strftime('%Y-%m-%d')}, "
            f"amount={self.amount}, desc={self.description[:30]!r})"
        )


@dataclass
class MatchResult:
    """Result of matching two transactions."""
    bank_transaction: Optional[Transaction]
    internal_transaction: Optional[Transaction]
    status: MatchStatus
    confidence: MatchConfidence
    date_diff_days: int = 0
    amount_diff: Decimal = Decimal("0")
    match_reason: str = ""

    @property
    def is_matched(self) -> bool:
        """Check if transactions were matched."""
        return self.status in (MatchStatus.EXACT, MatchStatus.FUZZY)


@dataclass
class ReconciliationSummary:
    """Summary statistics for a reconciliation run."""
    total_bank_transactions: int = 0
    total_internal_transactions: int = 0
    total_matched: int = 0
    total_exact_matches: int = 0
    total_fuzzy_matches: int = 0
    total_unmatched_bank: int = 0
    total_unmatched_internal: int = 0
    total_duplicates: int = 0
    total_bank_amount: Decimal = Decimal("0")
    total_internal_amount: Decimal = Decimal("0")
    matched_amount: Decimal = Decimal("0")
    unmatched_bank_amount: Decimal = Decimal("0")
    unmatched_internal_amount: Decimal = Decimal("0")

    @property
    def match_rate(self) -> float:
        """Calculate match rate as percentage."""
        total = self.total_bank_transactions
        if total == 0:
            return 0.0
        return (self.total_matched / total) * 100

    @property
    def amount_difference(self) -> Decimal:
        """Calculate total amount difference."""
        return self.total_bank_amount - self.total_internal_amount
