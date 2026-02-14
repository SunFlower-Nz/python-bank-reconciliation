"""CSV/Excel internal records parser."""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd

from src.engine.models import Transaction, TransactionType

logger = logging.getLogger(__name__)


class CSVParser:
    """Parse CSV/Excel internal accounting records into Transaction objects."""

    # Default column mapping
    DEFAULT_MAPPING: Dict[str, str] = {
        "date": "date",
        "amount": "amount",
        "description": "description",
        "reference": "reference",
        "type": "type",
    }

    # Common date formats to try
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    def __init__(self, column_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize parser with optional custom column mapping.

        Args:
            column_mapping: Dict mapping our field names to CSV column names.
                          Example: {"date": "Data", "amount": "Valor"}
        """
        self.column_mapping = column_mapping or self.DEFAULT_MAPPING

    def parse(self, file_path: str | Path, **kwargs) -> List[Transaction]:
        """
        Parse a CSV or Excel file into Transaction objects.

        Args:
            file_path: Path to the CSV/Excel file.
            **kwargs: Additional arguments passed to pandas read function.

        Returns:
            List of Transaction objects.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If required columns are missing.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = self._read_file(file_path, **kwargs)
        self._validate_columns(df)
        return self._convert_dataframe(df)

    def _read_file(self, file_path: Path, **kwargs) -> pd.DataFrame:
        """Read file based on extension."""
        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            return pd.read_csv(file_path, **kwargs)
        elif suffix in (".xlsx", ".xls"):
            return pd.read_excel(file_path, **kwargs)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Use .csv, .xlsx, or .xls")

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """
        Validate that required columns exist in the dataframe.

        Raises:
            ValueError: If required columns are missing.
        """
        required = ["date", "amount"]
        missing = []

        for field in required:
            col_name = self.column_mapping.get(field, field)
            if col_name not in df.columns:
                missing.append(f"{field} (expected column: '{col_name}')")

        if missing:
            available = ", ".join(df.columns.tolist())
            raise ValueError(
                f"Missing required columns: {', '.join(missing)}. "
                f"Available columns: {available}. "
                f"Use column_mapping parameter to map your columns."
            )

    def _convert_dataframe(self, df: pd.DataFrame) -> List[Transaction]:
        """Convert a DataFrame to list of Transaction objects."""
        transactions: List[Transaction] = []

        for idx, row in df.iterrows():
            try:
                txn = self._convert_row(row, idx)
                transactions.append(txn)
            except (ValueError, InvalidOperation) as e:
                # Log warning but continue processing
                logger.warning("Skipping row %s: %s", idx, e)

        return transactions

    def _convert_row(self, row: pd.Series, idx: int) -> Transaction:
        """Convert a single row to a Transaction object."""
        # Parse date
        date_col = self.column_mapping.get("date", "date")
        txn_date = self._parse_date(row[date_col])

        # Parse amount
        amount_col = self.column_mapping.get("amount", "amount")
        amount = self._parse_amount(row[amount_col])

        # Parse description
        desc_col = self.column_mapping.get("description", "description")
        description = str(row.get(desc_col, "")) if desc_col in row.index else ""

        # Parse reference
        ref_col = self.column_mapping.get("reference", "reference")
        reference = str(row.get(ref_col, "")) if ref_col in row.index else None

        # Determine transaction type
        type_col = self.column_mapping.get("type", "type")
        if type_col in row.index and pd.notna(row.get(type_col)):
            txn_type = self._parse_type(str(row[type_col]))
        else:
            txn_type = TransactionType.CREDIT if amount >= 0 else TransactionType.DEBIT

        return Transaction(
            id=f"INT-{idx:06d}",
            date=txn_date,
            amount=amount,
            description=description,
            type=txn_type,
            reference=reference if reference and reference != "nan" else None,
            source="internal",
            raw_data=row.to_dict(),
        )

    def _parse_date(self, value) -> datetime:
        """Parse date from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()

        str_value = str(value).strip()

        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(str_value, fmt)
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {value!r}")

    def _parse_amount(self, value) -> Decimal:
        """Parse amount handling various number formats."""
        if isinstance(value, (int, float)):
            return Decimal(str(value))

        str_value = str(value).strip()

        # Handle Brazilian format: 1.234,56
        if "," in str_value and "." in str_value:
            if str_value.rindex(",") > str_value.rindex("."):
                str_value = str_value.replace(".", "").replace(",", ".")

        # Handle comma as decimal separator: 1234,56
        elif "," in str_value:
            str_value = str_value.replace(",", ".")

        # Remove currency symbols and whitespace
        str_value = str_value.replace("R$", "").replace("$", "").strip()

        return Decimal(str_value)

    def _parse_type(self, value: str) -> TransactionType:
        """Parse transaction type from string."""
        normalized = value.lower().strip()
        credit_words = {"credit", "crédito", "credito", "c", "entrada", "receipt"}
        debit_words = {"debit", "débito", "debito", "d", "saída", "saida", "payment"}

        if normalized in credit_words:
            return TransactionType.CREDIT
        elif normalized in debit_words:
            return TransactionType.DEBIT
        else:
            raise ValueError(f"Unknown transaction type: {value!r}")
