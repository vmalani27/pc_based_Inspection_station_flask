#!/usr/bin/env python
"""Schema management utility.

Features:
 1. View current tables and their column structures.
 2. Optionally drop (delete) selected tables.
 3. Optionally drop ALL tables (full reset) with double confirmation.
 4. Non‑interactive CLI flags for scripting (list / drop specific / drop all).

Environment:
  Uses SQLALCHEMY_DATABASE_URI from .env or environment variables.

Safety:
  - Requires confirmation for destructive actions unless --force supplied.
  - Provides a dry-run option.

Examples:
  python schema_manager.py --list
  python schema_manager.py --show measured_shafts
  python schema_manager.py --drop-table measured_shafts --force
  python schema_manager.py --drop-all  # (will prompt twice)
  python schema_manager.py --drop-all --force  # (dangerous – no prompt)

Interactive mode (no flags):
  Presents a menu to inspect or drop tables.
"""
from __future__ import annotations
import os
import sys
import argparse
from typing import List
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.engine import Engine

load_dotenv()

URI = os.getenv("SQLALCHEMY_DATABASE_URI")
if not URI:
    print("[ERROR] SQLALCHEMY_DATABASE_URI not set in environment or .env file.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_engine() -> Engine:
    return create_engine(URI)

def list_tables(engine: Engine) -> List[str]:
    insp = inspect(engine)
    return sorted(insp.get_table_names())

def describe_table(engine: Engine, table: str) -> str:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return f"Table '{table}' does not exist."
    cols = insp.get_columns(table)
    lines = [f"Structure for table '{table}':"]
    header = f"  {'Name':<25} {'Type':<20} {'Nullable':<8} {'Default':<10}".rstrip()
    lines.append(header)
    lines.append("  " + "-" * (len(header)-2))
    for c in cols:
        default = str(c.get('default', ''))
        lines.append(f"  {c['name']:<25} {str(c['type']):<20} {str(c['nullable']):<8} {default:<10}")
    insp_idx = insp.get_indexes(table)
    if insp_idx:
        lines.append("\n  Indexes:")
        for idx in insp_idx:
            lines.append(f"    {idx.get('name')} -> columns={idx.get('column_names')}")
    pks = insp.get_pk_constraint(table)
    if pks and pks.get('constrained_columns'):
        lines.append(f"\n  Primary Key: {pks['constrained_columns']}")
    fks = insp.get_foreign_keys(table)
    if fks:
        lines.append("\n  Foreign Keys:")
        for fk in fks:
            lines.append(f"    {fk.get('name')} -> {fk.get('constrained_columns')} references {fk.get('referred_table')}({fk.get('referred_columns')})")
    return "\n".join(lines)

def drop_table(engine: Engine, table: str, force: bool=False, dry_run: bool=False) -> str:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return f"[WARN] Table '{table}' does not exist."
    if not force:
        confirm = input(f"Type the table name '{table}' to confirm drop (or leave blank to cancel): ").strip()
        if confirm != table:
            return "[ABORTED] Mismatch confirmation."
    stmt = f"DROP TABLE IF EXISTS {table}"
    if URI.startswith("postgresql"):
        stmt += " CASCADE"
    if dry_run:
        return f"[DRY-RUN] Would execute: {stmt}"
    with engine.begin() as conn:
        conn.execute(text(stmt))
    return f"[OK] Dropped table '{table}'."

def drop_all(engine: Engine, force: bool=False, dry_run: bool=False) -> str:
    insp = inspect(engine)
    tables = insp.get_table_names()
    if not tables:
        return "[INFO] No tables to drop."
    if not force:
        print("Tables to be dropped:", ", ".join(tables))
        confirm1 = input("Type 'YES' to confirm dropping ALL tables: ").strip()
        if confirm1 != 'YES':
            return "[ABORTED] First confirmation failed."
        confirm2 = input("Type 'DROP ALL' to finalize: ").strip()
        if confirm2 != 'DROP ALL':
            return "[ABORTED] Second confirmation failed."
    if dry_run:
        return f"[DRY-RUN] Would drop tables: {', '.join(tables)}"
    # Use MetaData reflect then drop (safer across dialects)
    md = MetaData()
    md.reflect(bind=engine)
    md.drop_all(bind=engine)
    return "[OK] Dropped all tables."

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Database schema manager")
    g = p.add_mutually_exclusive_group()
    g.add_argument('--list', action='store_true', help='List tables')
    g.add_argument('--show', metavar='TABLE', help='Show structure for a table')
    g.add_argument('--drop-table', metavar='TABLE', help='Drop a single table')
    g.add_argument('--drop-all', action='store_true', help='Drop ALL tables')
    p.add_argument('--force', action='store_true', help='Skip confirmations for destructive actions')
    p.add_argument('--dry-run', action='store_true', help='Show what would happen without executing')
    return p

def interactive(engine: Engine):
    while True:
        print("\n=== Schema Manager (interactive) ===")
        tables = list_tables(engine)
        print("Current tables ({}): {}".format(len(tables), ", ".join(tables) or '<none>'))
        print("Options:")
        print("  1) Show table structure")
        print("  2) Drop a table")
        print("  3) Drop ALL tables")
        print("  4) Refresh list")
        print("  0) Exit")
        choice = input("Select option: ").strip()
        if choice == '1':
            name = input("Table name: ").strip()
            print(describe_table(engine, name))
        elif choice == '2':
            name = input("Table to drop: ").strip()
            print(drop_table(engine, name))
        elif choice == '3':
            print(drop_all(engine))
        elif choice == '4':
            continue
        elif choice == '0':
            break
        else:
            print("Invalid selection.")

def main():
    parser = build_parser()
    args = parser.parse_args()
    engine = get_engine()

    # Non-interactive paths
    if args.list:
        for t in list_tables(engine):
            print(t)
        return
    if args.show:
        print(describe_table(engine, args.show))
        return
    if args.drop_table:
        print(drop_table(engine, args.drop_table, force=args.force, dry_run=args.dry_run))
        return
    if args.drop_all:
        print(drop_all(engine, force=args.force, dry_run=args.dry_run))
        return

    # Default: interactive menu
    interactive(engine)

if __name__ == '__main__':
    main()
