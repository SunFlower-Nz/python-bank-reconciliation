"""Tests for the OFX parser."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.parsers.ofx_parser import OFXParser
from src.engine.models import TransactionType


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestOFXParser:
    """Test OFX/QFX parsing functionality."""

    def test_parse_sample_ofx(self):
        """Test parsing a valid OFX file returns transactions."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        assert len(transactions) == 3
        assert all(t.source == "bank" for t in transactions)

    def test_transaction_amounts(self):
        """Test that amounts are parsed correctly as Decimal."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        amounts = sorted([t.amount for t in transactions])
        assert Decimal("-200.00") in amounts or Decimal("-200") in amounts
        assert Decimal("500.00") in amounts or Decimal("500") in amounts
        assert Decimal("1500.00") in amounts or Decimal("1500") in amounts

    def test_transaction_dates(self):
        """Test that dates are parsed correctly."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        dates = sorted([t.date.date() for t in transactions])
        assert dates[0] == datetime(2025, 1, 10).date()
        assert dates[1] == datetime(2025, 1, 15).date()
        assert dates[2] == datetime(2025, 1, 20).date()

    def test_transaction_types(self):
        """Test credit/debit type detection."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        credits = [t for t in transactions if t.type == TransactionType.CREDIT]
        debits = [t for t in transactions if t.type == TransactionType.DEBIT]

        assert len(credits) == 2
        assert len(debits) == 1

    def test_transaction_descriptions(self):
        """Test that memo/description is captured."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        descriptions = [t.description for t in transactions]
        assert any("Test deposit" in d for d in descriptions)
        assert any("Test withdrawal" in d for d in descriptions)

    def test_transaction_references(self):
        """Test that check numbers are parsed as references."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        refs = [t.reference for t in transactions if t.reference]
        assert "CHK001" in refs
        assert "CHK003" in refs

    def test_transaction_ids(self):
        """Test that FITIDs are used as transaction IDs."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        ids = [t.id for t in transactions]
        assert "FIX001" in ids
        assert "FIX002" in ids
        assert "FIX003" in ids

    def test_file_not_found(self):
        """Test FileNotFoundError for missing file."""
        parser = OFXParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.ofx")

    def test_unsupported_format(self, tmp_path):
        """Test ValueError for unsupported file extension."""
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some data")

        parser = OFXParser()
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(txt_file)

    def test_parse_multiple(self):
        """Test parsing multiple OFX files."""
        parser = OFXParser()
        sample = FIXTURES_DIR / "sample.ofx"
        transactions = parser.parse_multiple([sample, sample])

        # Should get double the transactions
        assert len(transactions) == 6

    def test_invalid_ofx_content(self, tmp_path):
        """Test ValueError for corrupted OFX file."""
        bad_file = tmp_path / "bad.ofx"
        bad_file.write_text("this is not valid OFX content")

        parser = OFXParser()
        with pytest.raises(ValueError, match="Failed to parse"):
            parser.parse(bad_file)

    def test_raw_data_contains_account_info(self):
        """Test that raw_data includes account metadata."""
        parser = OFXParser()
        transactions = parser.parse(FIXTURES_DIR / "sample.ofx")

        for txn in transactions:
            assert "account_id" in txn.raw_data
