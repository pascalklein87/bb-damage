"""
Central database connection for bb-damage (the damage calculator).

Uses MySQL (MariaDB) via pymysql. Connection config is read from
environment variables with defaults matching the production server.

Connects to the app's own `bb_damage` database, which holds only what
the shared `bb_data` extraction does not carry: the curated weapon
identity (`weapon`), calculator display text + mastery show-set
(`weapon_skill_display`), the enemy tables, `attacker_buff`, and the
result `cache`. Weapon stats, skill mechanics, and weapon->skill
connections are read from `bb_data` at runtime (see engine/data.py).
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
