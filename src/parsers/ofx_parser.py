"""OFX bank statement parser."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List
from uuid import uuid4

from ofxparse import OfxParser as OfxLib

from src.engine.models import Transaction, TransactionType


class OFXParser:
    """Parse OFX/QFX bank statement files into Transaction objects."""

    def parse(self, file_path: str | Path) -> List[Transaction]:
        """
        Parse an OFX file and return a list of Transaction objects.

        Args:
            file_path: Path to the OFX/QFX file.

        Returns:
            List of Transaction objects from the bank statement.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file cannot be parsed.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"OFX file not found: {file_path}")

        if file_path.suffix.lower() not in (".ofx", ".qfx"):
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        try:
            with open(file_path, "rb") as f:
                ofx = OfxLib.parse(f)
        except Exception as e:
            raise ValueError(f"Failed to parse OFX file: {e}") from e

        transactions: List[Transaction] = []

        for account in self._get_accounts(ofx):
            for stmt_txn in account.statement.transactions:
                txn = self._convert_transaction(stmt_txn, account)
                transactions.append(txn)

        return transactions

    def parse_multiple(self, file_paths: List[str | Path]) -> List[Transaction]:
        """
        Parse multiple OFX files and return combined transactions.

        Args:
            file_paths: List of paths to OFX/QFX files.

        Returns:
            Combined list of Transaction objects.
        """
        all_transactions: List[Transaction] = []
        for path in file_paths:
            all_transactions.extend(self.parse(path))
        return all_transactions

    def _get_accounts(self, ofx):
        """Extract accounts from parsed OFX data."""
        if hasattr(ofx, "accounts"):
            return ofx.accounts
        if hasattr(ofx, "account"):
            return [ofx.account]
        raise ValueError("No accounts found in OFX file")

    def _convert_transaction(self, stmt_txn, account) -> Transaction:
        """Convert an OFX statement transaction to our Transaction model."""
        amount = Decimal(str(stmt_txn.amount))

        txn_type = (
            TransactionType.CREDIT if amount >= 0
            else TransactionType.DEBIT
        )

        txn_date = stmt_txn.date
        if isinstance(txn_date, str):
            txn_date = datetime.strptime(txn_date[:8], "%Y%m%d")

        return Transaction(
            id=getattr(stmt_txn, "id", str(uuid4())),
            date=txn_date,
            amount=amount,
            description=getattr(stmt_txn, "memo", "") or getattr(stmt_txn, "payee", ""),
            type=txn_type,
            reference=getattr(stmt_txn, "checknum", None),
            source="bank",
            raw_data={
                "account_id": getattr(account, "account_id", ""),
                "bank_id": getattr(account, "routing_number", ""),
                "type": getattr(stmt_txn, "type", ""),
            },
        )
