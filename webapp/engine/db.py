"""
Central database connection for bb-wiki.

Uses MySQL (MariaDB) via pymysql. Connection config is read from
environment variables with defaults matching the production server.

bb-wiki uses its own custom database (bb_wiki) with a minimal subset
of BB-extracted data plus wiki-specific tables (cache,
guide_weapon_rankings). Source-of-truth BB data lives in a separate
DB; bb_wiki holds a denormalized, self-contained copy of only what
the public pages need. See bb-wiki/deployment.txt.
"""
import os
import pymysql
import pymysql.cursors


def get_connection():
    """Return a new MySQL connection with DictCursor."""
    return pymysql.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '3306')),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', 'Kx7#mP2$vQ9nL4wR'),
        database=os.environ.get('DB_NAME', 'bb_damage'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
