#!/usr/bin/env python3
"""
DuckDB inspection utility.
Lists schemas, tables, row counts, and previews sample rows.
Usage:
  python scripts/inspect_duckdb.py [DB_PATH] [--limit 10]
Defaults:
  DB_PATH = data/duckdb/extractions.db
"""
import argparse
import duckdb

DEFAULT_DB = 'data/duckdb/extractions.db'


def main():
    parser = argparse.ArgumentParser(description='Inspect DuckDB database contents.')
    parser.add_argument('db', nargs='?', default=DEFAULT_DB, help='Path to DuckDB database file')
    parser.add_argument('--limit', type=int, default=10, help='Preview row limit')
    args = parser.parse_args()

    con = duckdb.connect(args.db)

    print(f"Connected to: {args.db}")

    tables = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables ORDER BY table_schema, table_name"
    ).fetchall()

    if not tables:
        print("No tables found.")
        return

    print("\nTables:")
    for schema, table in tables:
        print(f"- {schema}.{table}")

    print("\nDetails:")
    for schema, table in tables:
        full = f"{schema}.{table}" if schema and schema != 'main' else table
        try:
            count_row = con.execute(f"SELECT COUNT(*) FROM {full}").fetchone()
            count = count_row[0] if count_row else 0
            print(f"\nTable: {full} | rows: {count}")
            print("Schema:")
            schema_df = con.execute(f"DESCRIBE {full}").fetchdf()
            print(schema_df.to_string(index=False))
            if count:
                preview = con.execute(f"SELECT * FROM {full} LIMIT {args.limit}").fetchdf()
                print("Sample:")
                print(preview.to_string(index=False))
        except Exception as e:
            print(f"Error inspecting {full}: {e}")


if __name__ == '__main__':
    main()
