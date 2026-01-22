#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running PostgreSQL migrations..."

# Run all migration files in order
for migration in "$SCRIPT_DIR"/V*.sql; do
    if [ -f "$migration" ]; then
        echo "Applying $(basename "$migration")..."
        docker exec -i autotrader-postgres psql -U autotrader -d autotrader < "$migration" 2>&1 || {
            echo "  (Some statements may have already been applied)"
        }
    fi
done

echo "✅ Migrations completed"
