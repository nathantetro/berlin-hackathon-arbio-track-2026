"""Query and display table data.

Run with: tower run local
"""

import tower
from arbie.services.db.base import CATALOG_NAME, NAMESPACE


def main():
    """Query and display users table."""
    print("=" * 80)
    print("USERS TABLE")
    print("=" * 80)

    table = tower.tables("users", catalog=CATALOG_NAME, namespace=NAMESPACE).load()
    df = table.read()

    print(f"\nTotal rows: {len(df)}\n")
    print(df)

    return 0


if __name__ == "__main__":
    exit(main())