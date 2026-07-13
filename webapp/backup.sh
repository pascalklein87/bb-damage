#!/bin/bash
# Database backup. Run before any risky DB change.
#
# Maintains two files in backups/:
#   current.sql  — freshly dumped database
#   stable.sql   — previous current.sql, one rotation back
#
# Each run rotates current.sql -> stable.sql, then dumps a new current.sql.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUPS="$SCRIPT_DIR/backups"
mkdir -p "$BACKUPS"

if [ -f "$BACKUPS/current.sql" ]; then
    mv "$BACKUPS/current.sql" "$BACKUPS/stable.sql"
fi

if command -v mysqldump >/dev/null 2>&1; then
    DUMP=mysqldump
else
    DUMP="/c/Program Files/MariaDB 12.2/bin/mysqldump.exe"
fi

MYSQL_PWD="${DB_PASSWORD:-Kx7#mP2\$vQ9nL4wR}" \
"$DUMP" \
    -h "${DB_HOST:-localhost}" \
    -u "${DB_USER:-root}" \
    "${DB_NAME:-bb_wiki}" \
    > "$BACKUPS/current.sql"

echo "Backup created: $BACKUPS/current.sql"
