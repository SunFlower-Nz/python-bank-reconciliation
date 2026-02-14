"""CLI entry point for bank reconciliation."""

import logging
import sys
from pathlib import Path
from typing import List

import click

from src.engine.matcher import ReconciliationEngine
from src.parsers.csv_parser import CSVParser
from src.parsers.ofx_parser import OFXParser
from src.reports.excel_report import ExcelReportGenerator

logger = logging.getLogger(__name__)


def validate_tolerance(ctx, param, value):
    """Validate date tolerance is non-negative."""
    if value < 0:
        raise click.BadParameter("Date tolerance must be non-negative.")
    return value


def validate_threshold(ctx, param, value):
    """Validate amount threshold is between 0 and 1."""
    if value < 0 or value > 1:
        raise click.BadParameter("Amount threshold must be between 0 and 1.")
    return value


@click.command()
@click.option(
    "--bank", "-b",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to bank statement file(s) in OFX/QFX format.",
)
@click.option(
    "--internal", "-i",
    required=True,
    type=click.Path(exists=True),
    help="Path to internal records file (CSV or Excel).",
)
@click.option(
    "--output", "-o",
    required=True,
    type=click.Path(),
    help="Path for the output Excel report.",
)
@click.option(
    "--date-tolerance", "-d",
    default=3,
    type=int,
    callback=validate_tolerance,
    help="Maximum days difference for fuzzy matching (default: 3).",
)
@click.option(
    "--amount-threshold", "-a",
    default=0.02,
    type=float,
    callback=validate_threshold,
    help="Maximum relative amount difference for fuzzy matching (default: 0.02 = 2%).",
)
@click.option(
    "--date-col",
    default="date",
    help="Date column name in internal records file.",
)
@click.option(
    "--amount-col",
    default="amount",
    help="Amount column name in internal records file.",
)
@click.option(
    "--desc-col",
    default="description",
    help="Description column name in internal records file.",
)
@click.option(
    "--ref-col",
    default="reference",
    help="Reference column name in internal records file.",
)
def main(
    bank: tuple,
    internal: str,
    output: str,
    date_tolerance: int,
    amount_threshold: float,
    date_col: str,
    amount_col: str,
    desc_col: str,
    ref_col: str,
) -> None:
    """
    Bank Reconciliation Tool

    Matches OFX bank statements against CSV/Excel internal records
    and generates a detailed Excel report.

    Example:
        python -m src.main --bank bank.ofx --internal records.csv --output report.xlsx
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    click.echo("=" * 60)
    click.echo("  BANK RECONCILIATION ENGINE")
    click.echo("=" * 60)

    try:
        # Step 1: Parse bank statements
        click.echo(f"\n  Parsing {len(bank)} bank statement(s)...")
        ofx_parser = OFXParser()
        bank_transactions = ofx_parser.parse_multiple([Path(p) for p in bank])
        click.echo(f"   Found {len(bank_transactions)} bank transactions")

        # Step 2: Parse internal records
        click.echo(f"\n  Parsing internal records: {internal}...")
        column_mapping = {
            "date": date_col,
            "amount": amount_col,
            "description": desc_col,
            "reference": ref_col,
        }
        csv_parser = CSVParser(column_mapping=column_mapping)
        internal_transactions = csv_parser.parse(Path(internal))
        click.echo(f"   Found {len(internal_transactions)} internal transactions")

        # Step 3: Reconcile
        click.echo(f"\n  Reconciling (tolerance: {date_tolerance}d, threshold: {amount_threshold:.0%})...")
        engine = ReconciliationEngine(
            date_tolerance_days=date_tolerance,
            amount_threshold=amount_threshold,
        )
        results, summary = engine.reconcile(bank_transactions, internal_transactions)

        # Step 4: Generate report
        click.echo(f"\n  Generating report: {output}...")
        report_gen = ExcelReportGenerator()
        output_path = report_gen.generate(results, summary, output)

        # Step 5: Print summary
        click.echo("\n" + "=" * 60)
        click.echo("  RECONCILIATION SUMMARY")
        click.echo("=" * 60)
        click.echo(f"  Match Rate:           {summary.match_rate:.1f}%")
        click.echo(f"  Total Matched:        {summary.total_matched}")
        click.echo(f"    +-- Exact:          {summary.total_exact_matches}")
        click.echo(f"    +-- Fuzzy:          {summary.total_fuzzy_matches}")
        click.echo(f"  Unmatched (Bank):     {summary.total_unmatched_bank}")
        click.echo(f"  Unmatched (Internal): {summary.total_unmatched_internal}")
        click.echo(f"  Duplicates:           {summary.total_duplicates}")
        click.echo(f"  Amount Difference:    {summary.amount_difference:,.2f}")
        click.echo("=" * 60)
        click.echo(f"\n  Report saved to: {output_path.absolute()}")

    except FileNotFoundError as e:
        click.echo(f"\n  ERROR: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"\n  ERROR: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error during reconciliation")
        click.echo(f"\n  UNEXPECTED ERROR: {e}", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
