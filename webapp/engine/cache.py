import hashlib
import json

from engine.db import get_connection


def _make_hash(url):
    return hashlib.sha256(url.encode()).hexdigest()


def get_cached(url):
    """Return cached result dict or None. Increments count on hit.

    `actual_simulations` is read from the row's num_simulations column
    rather than the JSON. set_cached has never persisted the field
    inside the JSON, so old cache entries load correctly without
    requiring a TRUNCATE / re-cache pass.
    """
    h = _make_hash(url)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT json, num_simulations FROM cache WHERE hash = %s', (h,))
    row = cursor.fetchone()
    if row:
        cursor.execute('UPDATE cache SET count = count + 1, last_used = NOW() WHERE hash = %s', (h,))
        conn.commit()
        cursor.close()
        conn.close()
        result = json.loads(row['json'])
        result['actual_simulations'] = row['num_simulations']
        return result
    cursor.close()
    conn.close()
    return None


def set_cached(url, hits_to_kill, num_simulations=20000):
    """Store simulation results for a URL."""
    h = _make_hash(url)
    data = {
        'avg_hits_to_kill': hits_to_kill['avg_hits_to_kill'],
        'distribution': hits_to_kill['distribution'],
        'injury': hits_to_kill['injury'],
        'injury_distribution': hits_to_kill['injury_distribution'],
        'resolve': hits_to_kill['resolve'],
        'resolve_distribution': hits_to_kill['resolve_distribution'],
        'fearsome': hits_to_kill['fearsome'],
        'fearsome_distribution': hits_to_kill['fearsome_distribution'],
        'damage_stats': hits_to_kill['damage_stats'],
    }
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'REPLACE INTO cache (hash, json, url, count, last_used, num_simulations) VALUES (%s, %s, %s, 1, NOW(), %s)',
        (h, json.dumps(data), url, num_simulations)
    )
    conn.commit()
    cursor.close()
    conn.close()
