# Python Bank Reconciliation Engine

Automated bank reconciliation system that matches OFX bank statements against CSV/Excel internal records, identifies discrepancies, and generates detailed Excel reports.

## Features

- **OFX Parsing**: Parse bank statements in OFX/QFX format
- **CSV Parsing**: Parse internal accounting records from CSV/Excel with flexible column mapping
- **Smart Matching**: Exact match, fuzzy match (date tolerance + amount threshold), and duplicate detection
- **Excel Reports**: Professional 5-tab Excel reports with formatting, conditional highlighting, and summary dashboards
- **CLI Interface**: Simple command-line usage for automation pipelines
- **i18n Support**: Handles Brazilian date/number formats and Portuguese terms
- **Extensible**: Easy to add new parsers and matching strategies

## Quick Demo

Run the demo script to see the tool in action with example data:

```bash
pip install -r requirements.txt
python demo.py
```

This will parse the example files in `examples/` and generate `examples/reconciliation_report.xlsx`.

## Architecture

```
src/
├── parsers/
│   ├── ofx_parser.py      # Bank statement parser (OFX/QFX)
│   └── csv_parser.py       # Internal records parser (CSV/Excel)
├── engine/
│   ├── matcher.py           # Core reconciliation logic
│   └── models.py            # Data models (Transaction, Match, etc.)
├── reports/
│   └── excel_report.py      # Excel report generator
└── main.py                  # CLI entry point

examples/
├── bank_statement.ofx       # Sample OFX bank statement
├── internal_records.csv     # Sample internal records
└── reconciliation_report.xlsx  # Generated report (after running demo)

tests/
├── test_ofx_parser.py
├── test_csv_parser.py
├── test_matcher.py
├── test_excel_report.py
└── fixtures/
    ├── sample.ofx
    └── sample_internal.csv
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Basic reconciliation
python -m src.main --bank statements/bank.ofx --internal records/accounting.csv --output report.xlsx

# With custom tolerance
python -m src.main --bank bank.ofx --internal records.csv --output report.xlsx --date-tolerance 3 --amount-threshold 0.02

# Multiple bank files
python -m src.main --bank bank_jan.ofx --bank bank_feb.ofx --internal records.csv --output report.xlsx

# With custom column mapping for CSV
python -m src.main --bank bank.ofx --internal records.csv --output report.xlsx --date-col "Data" --amount-col "Valor" --desc-col "Descricao"
```

## Report Tabs

| Tab | Description |
|-----|-------------|
| **Summary** | KPIs: total matched, unmatched, match rate %, total amounts |
| **Matched** | All successfully matched transactions with match confidence |
| **Bank Only** | Transactions in bank statement but not in internal records |
| **Internal Only** | Transactions in internal records but not in bank statement |
| **Duplicates** | Potential duplicate transactions flagged for review |

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Tech Stack

- **Python 3.11+**
- **Pandas** - Data manipulation
- **ofxparse** - OFX file parsing
- **openpyxl** - Excel report generation
- **pytest** - Testing
- **click** - CLI interface

## Real-World Impact

This tool was inspired by a real project where manual bank reconciliation took **40+ hours/month**. The automated solution reduced this to **under 5 minutes**, with higher accuracy and complete audit trail.

## License

MIT
