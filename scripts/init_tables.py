#!/usr/bin/env python3
"""Initialize all Iceberg tables for Arbie.

Run this script via Tower:
    tower run local
"""

from arbie.db.schemas import ALL_TABLES, TABLE_SCHEMAS
from arbie.db.tables import init_tables


def main() -> None:
    """Initialize all Iceberg tables."""
    print(f"Initializing {len(ALL_TABLES)} Iceberg tables...")
    print("-" * 50)

    results = init_tables()

    success_count = sum(1 for v in results.values() if v)
    fail_count = len(results) - success_count

    print("-" * 50)
    for table_name, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {table_name}")

    print("-" * 50)
    print(f"Summary: {success_count} succeeded, {fail_count} failed")

    if fail_count > 0:
        print("\nFailed tables may already exist or have schema conflicts.")
        exit(1)

    print("\nAll tables initialized successfully!")


if __name__ == "__main__":
    main()
