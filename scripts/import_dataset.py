"""
CLI script to import a question-answer dataset from JSON or CSV into MongoDB.

Usage:
    python scripts/import_dataset.py --file data/question_bank.json
    python scripts/import_dataset.py --file data/custom.csv --format csv
"""
import argparse
import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.services.question_service import question_service


async def run_import(filepath: str, file_format: str) -> None:
    print(f"\n[+] Starting dataset import from: {filepath}")
    if not os.path.exists(filepath):
        print(f"[!] Error: File does not exist at '{filepath}'")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    print("[*] Connecting to database...")
    await connect_to_mongo()

    try:
        fmt = file_format.lower()
        if fmt == "csv" or filepath.endswith(".csv"):
            result = await question_service.import_from_csv(content)
        else:
            result = await question_service.import_from_json(content)

        print("\n=== Dataset Import Summary ===")
        print(f"Total Records Processed: {result.total_processed}")
        print(f"Successfully Imported:   {result.imported}")
        print(f"Duplicates / Skipped:    {result.skipped_duplicates}")
        if result.invalid_records:
            print(f"Invalid Records ({len(result.invalid_records)}):")
            for err in result.invalid_records[:10]:
                print(f"  - {err}")
            if len(result.invalid_records) > 10:
                print(f"  ... and {len(result.invalid_records) - 10} more.")
        print("==============================\n")
    finally:
        await close_mongo_connection()


def main():
    parser = argparse.ArgumentParser(description="Import viva question bank dataset into MongoDB.")
    parser.add_argument("--file", "-f", default="data/question_bank.json", help="Path to JSON or CSV dataset file")
    parser.add_argument("--format", default="json", choices=["json", "csv"], help="Format of input file")

    args = parser.parse_args()
    asyncio.run(run_import(args.file, args.format))


if __name__ == "__main__":
    main()
