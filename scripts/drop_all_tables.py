#!/usr/bin/env python3
"""Drop all Iceberg tables to reset corrupted schema.

This script deletes all tables in the arbie namespace so they can be
recreated with the correct schema on next use via create_if_not_exists().

WARNING: This will delete all existing data!

Usage:
    tower run local scripts/drop_all_tables.py
"""

import tower

from arbie.db.schemas import ALL_TABLES

CATALOG = "arbie-properties"
NAMESPACE = "arbie"


def drop_all_tables():
    """Drop all Iceberg tables."""
    print(f"Dropping {len(ALL_TABLES)} tables from {CATALOG}.{NAMESPACE}...")
    print()

    dropped = 0
    failed = 0

    for table_name in ALL_TABLES:
        try:
            table = tower.tables(table_name, catalog=CATALOG, namespace=NAMESPACE)
            table.drop()
            print(f"  ✓ Dropped: {table_name}")
            dropped += 1
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                print(f"  - Skipped: {table_name} (does not exist)")
            else:
                print(f"  ✗ Failed: {table_name} - {e}")
                failed += 1

    print()
    print(f"Summary: {dropped} dropped, {failed} failed, {len(ALL_TABLES) - dropped - failed} skipped")
    print()
    print("Tables will be recreated with correct schema on next access.")


if __name__ == "__main__":
    drop_all_tables()
