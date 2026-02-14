"""Tests for the CSV parser."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pandas as pd

from src.parsers.csv_parser import CSVParser
from src.engine.models import TransactionType


@pytest.fixture
def sample_csv(tmp_path) -> Path:
    """Create a sample CSV file for testing."""
    csv_content = """date,amount,description,reference,type
2025-01-10,1000.00,Payment from Client A,REF001,credit
2025-01-15,-500.00,Office supplies,REF002,debit
2025-01-20,2500.00,Invoice #1234,REF003,credit
2025-01-25,-150.00,Subscription fee,,debit
"""
    csv_file = tmp_path / "test_records.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def brazilian_csv(tmp_path) -> Path:
    """Create a CSV with Brazilian date/number format."""
    csv_content = """data,valor,descricao,referencia
10/01/2025,"1.000,50",Pagamento Cliente A,REF001
15/01/2025,"-500,00",Material escritorio,REF002
20/01/2025,"2.500,00",Fatura #1234,REF003
"""
    csv_file = tmp_path / "test_br.csv"
    csv_file.write_text(csv_content)
    return csv_file


class TestCSVParser:
    """Test CSV parsing functionality."""

    def test_parse_standard_csv(self, sample_csv):
        parser = CSVParser()
        transactions = parser.parse(sample_csv)

        assert len(transactions) == 4
        assert transactions[0].amount == Decimal("1000.00")
        assert transactions[0].type == TransactionType.CREDIT
        assert transactions[0].source == "internal"

    def test_parse_debit_transaction(self, sample_csv):
        parser = CSVParser()
        transactions = parser.parse(sample_csv)

        debit = transactions[1]
        assert debit.amount == Decimal("-500.00")
        assert debit.type == TransactionType.DEBIT
        assert debit.description == "Office supplies"

    def test_parse_with_column_mapping(self, brazilian_csv):
        parser = CSVParser(column_mapping={
            "date": "data",
            "amount": "valor",
            "description": "descricao",
            "reference": "referencia",
        })
        transactions = parser.parse(brazilian_csv)

        assert len(transactions) == 3
        assert transactions[0].amount == Decimal("1000.50")
        assert transactions[0].date == datetime(2025, 1, 10)

    def test_file_not_found(self):
        parser = CSVParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.csv")

    def test_missing_required_columns(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("name,value\ntest,123\n")

        parser = CSVParser()
        with pytest.raises(ValueError, match="Missing required columns"):
            parser.parse(csv_file)

    def test_unsupported_format(self, tmp_path):
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some data")

        parser = CSVParser()
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(txt_file)

    def test_empty_reference(self, sample_csv):
        parser = CSVParser()
        transactions = parser.parse(sample_csv)

        # Last transaction has no reference
        assert transactions[3].reference is None

    def test_date_formats(self, tmp_path):
        """Test various date formats are parsed correctly."""
        for fmt, date_str in [
            ("%Y-%m-%d", "2025-01-15"),
            ("%d/%m/%Y", "15/01/2025"),
            ("%d.%m.%Y", "15.01.2025"),
        ]:
            csv_file = tmp_path / f"test_{fmt.replace('%', '').replace('/', '_')}.csv"
            csv_file.write_text(f"date,amount\n{date_str},100.00\n")
            parser = CSVParser()
            txns = parser.parse(csv_file)
            assert txns[0].date.day == 15
            assert txns[0].date.month == 1
