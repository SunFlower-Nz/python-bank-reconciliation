"""
Demo script for the Bank Reconciliation Engine.

Run this script to see the reconciliation tool in action using the
example files in the examples/ directory.

Usage:
    python demo.py
"""

import logging
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.engine.matcher import ReconciliationEngine
from src.parsers.csv_parser import CSVParser
from src.parsers.ofx_parser import OFXParser
from src.reports.excel_report import ExcelReportGenerator


def main():
    """Run the bank reconciliation demo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    examples_dir = project_root / "examples"
    bank_file = examples_dir / "bank_statement.ofx"
    internal_file = examples_dir / "internal_records.csv"
    output_file = examples_dir / "reconciliation_report.xlsx"

    print("=" * 60)
    print("  BANK RECONCILIATION ENGINE - DEMO")
    print("=" * 60)

    # Verify example files exist
    if not bank_file.exists():
        print(f"\n  ERROR: Bank statement not found: {bank_file}")
        sys.exit(1)
    if not internal_file.exists():
        print(f"\n  ERROR: Internal records not found: {internal_file}")
        sys.exit(1)

    # Step 1: Parse bank statement (OFX)
    print(f"\n  [1/4] Parsing bank statement: {bank_file.name}")
    ofx_parser = OFXParser()
    try:
        bank_transactions = ofx_parser.parse(bank_file)
    except Exception as e:
        print(f"  ERROR parsing OFX: {e}")
        sys.exit(1)
    print(f"        Found {len(bank_transactions)} bank transactions")
    for txn in bank_transactions:
        print(f"        - {txn.date.strftime('%Y-%m-%d')} | {txn.amount:>10} | {txn.description[:40]}")

    # Step 2: Parse internal records (CSV)
    print(f"\n  [2/4] Parsing internal records: {internal_file.name}")
    csv_parser = CSVParser()
    try:
        internal_transactions = csv_parser.parse(internal_file)
    except Exception as e:
        print(f"  ERROR parsing CSV: {e}")
        sys.exit(1)
    print(f"        Found {len(internal_transactions)} internal transactions")
    for txn in internal_transactions:
        print(f"        - {txn.date.strftime('%Y-%m-%d')} | {txn.amount:>10} | {txn.description[:40]}")

    # Step 3: Reconcile
    print("\n  [3/4] Running reconciliation engine...")
    engine = ReconciliationEngine(
        date_tolerance_days=3,
        amount_threshold=0.02,
    )
    results, summary = engine.reconcile(bank_transactions, internal_transactions)

    # Step 4: Generate report
    print(f"\n  [4/4] Generating Excel report: {output_file.name}")
    report_gen = ExcelReportGenerator()
    output_path = report_gen.generate(results, summary, str(output_file))

    # Print summary
    print("\n" + "=" * 60)
    print("  RECONCILIATION SUMMARY")
    print("=" * 60)
    print(f"  Bank Transactions:    {summary.total_bank_transactions}")
    print(f"  Internal Transactions:{summary.total_internal_transactions}")
    print(f"  Match Rate:           {summary.match_rate:.1f}%")
    print(f"  Total Matched:        {summary.total_matched}")
    print(f"    +-- Exact:          {summary.total_exact_matches}")
    print(f"    +-- Fuzzy:          {summary.total_fuzzy_matches}")
    print(f"  Unmatched (Bank):     {summary.total_unmatched_bank}")
    print(f"  Unmatched (Internal): {summary.total_unmatched_internal}")
    print(f"  Duplicates:           {summary.total_duplicates}")
    print(f"  Bank Amount:          {summary.total_bank_amount:>12,.2f}")
    print(f"  Internal Amount:      {summary.total_internal_amount:>12,.2f}")
    print(f"  Amount Difference:    {summary.amount_difference:>12,.2f}")
    print("=" * 60)

    # Print detailed results
    print("\n  DETAILED RESULTS:")
    print("-" * 60)
    for r in results:
        bank_desc = r.bank_transaction.description[:25] if r.bank_transaction else "N/A"
        int_desc = r.internal_transaction.description[:25] if r.internal_transaction else "N/A"
        status = r.status.value.upper()
        print(f"  [{status:>20}] Bank: {bank_desc:<25} | Internal: {int_desc:<25}")

    print(f"\n  Report saved to: {output_path.absolute()}")
    print("  Open the Excel file to see the formatted reconciliation report.\n")


if __name__ == "__main__":
    main()
