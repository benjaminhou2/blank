#!/bin/bash
# Helper script to launch DuckDB shell with the livestream database

DB_PATH="livestream.db"
DUCKDB_BIN="/Users/ben/.duckdb/cli/latest/duckdb"

if [ ! -f "$DUCKDB_BIN" ]; then
    # Fallback to local bin if symlink is on PATH
    DUCKDB_BIN="duckdb"
fi

echo "Launching DuckDB with database: $DB_PATH"
echo "You can query tables: rooms, gifts, comments."
echo "Type '.help' for help, '.tables' to see tables, and '.exit' to exit."
echo ""

$DUCKDB_BIN "$DB_PATH"
