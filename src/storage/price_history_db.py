# src/storage/price_history_db.py

"""SQLite-backed price history store for long-term price tracking."""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from src.config.settings import Settings
from src.models.price_snapshot import PriceSnapshot
from src.models.product import Product

logger = logging.getLogger("ecom_search.price_history")

# Amazon / iHerb tracking params that vary per session
_TRACKING_PARAMS: frozenset[str] = frozenset({
    "ref", "dib", "dib_tag", "qid", "sr", "spc",
    "sp_csd", "xpid", "aref", "sp_cr", "psc",
    "keywords", "pd_rd_i", "pd_rd_r", "pd_rd_w",
    "pd_rd_wg", "pf_rd_i", "pf_rd_m", "pf_rd_p",
    "pf_rd_r", "pf_rd_s", "pf_rd_t", "th",
})

# Filename pattern: {source}_{query}_{YYYYmmdd_HHMMSS}.json
_FILENAME_RE = re.compile(
    r"^(.+?)_(\d{8}_\d{6})\.json$"
)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS products (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT    NOT NULL UNIQUE,
    title      TEXT    NOT NULL,
    source     TEXT    NOT NULL,
    first_seen TEXT    NOT NULL,
    is_starred INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL
               REFERENCES products(id) ON DELETE CASCADE,
    price      REAL    NOT NULL,
    currency   TEXT    NOT NULL DEFAULT 'AED',
    scraped_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_product_date
    ON price_snapshots(product_id, scraped_at);
"""


def normalize_url(raw_url: str) -> str:
    """Strip tracking/session query params to get a stable product URL."""
    parsed = urlparse(raw_url)

    # Strip Amazon path-based tracking (e.g. /ref=sr_1_243)
    path = re.sub(r"/ref=[^/]*", "", parsed.path)

    params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {
        k: v for k, v in params.items()
        if k.lower() not in _TRACKING_PARAMS
    }
    new_query = urlencode(cleaned, doseq=True) if cleaned else ""
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        new_query,
        "",  # drop fragment
    ))


class PriceHistoryDB:
    """SQLite-backed store for product price snapshots."""

    def __init__(
        self, db_path: Path | None = None,
    ) -> None:
        path = db_path or Settings.PRICE_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(path), check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        logger.debug(
            "PriceHistoryDB opened at %s", path,
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Recording ────────────────────────────────────────

    def record_snapshots(
        self,
        products: list[Product],
        scraped_at: datetime | None = None,
    ) -> int:
        """Insert a price snapshot for each product.

        Products are upserted by their normalised URL.
        Returns the number of snapshots inserted.
        """
        now = scraped_at or datetime.now()
        ts = now.isoformat()
        count = 0
        cur = self._conn.cursor()

        for p in products:
            if not p.url or p.price <= 0:
                continue
            url = normalize_url(p.url)

            cur.execute(
                "INSERT INTO products (url, title, source, first_seen) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET title=excluded.title",
                (url, p.title, p.source, ts),
            )
            product_id: int = cur.execute(
                "SELECT id FROM products WHERE url = ?",
                (url,),
            ).fetchone()[0]

            cur.execute(
                "INSERT INTO price_snapshots "
                "(product_id, price, currency, scraped_at) "
                "VALUES (?, ?, ?, ?)",
                (product_id, p.price, p.currency, ts),
            )
            count += 1

        self._conn.commit()
        if count:
            logger.info(
                "Recorded %d price snapshots at %s", count, ts,
            )
        return count

    # ── Querying ─────────────────────────────────────────

    def get_price_history(
        self, product_url: str,
    ) -> list[PriceSnapshot]:
        """Return all price snapshots for a product, oldest first."""
        url = normalize_url(product_url)
        rows = self._conn.execute(
            "SELECT p.url, p.title, s.price, s.currency, "
            "       p.source, s.scraped_at "
            "FROM price_snapshots s "
            "JOIN products p ON p.id = s.product_id "
            "WHERE p.url = ? "
            "ORDER BY s.scraped_at ASC",
            (url,),
        ).fetchall()
        return [
            PriceSnapshot(
                product_url=r[0],
                title=r[1],
                price=r[2],
                currency=r[3],
                source=r[4],
                scraped_at=datetime.fromisoformat(r[5]),
            )
            for r in rows
        ]

    def get_price_trends(
        self, product_urls: list[str],
    ) -> dict[str, list[PriceSnapshot]]:
        """Batch-fetch price history for multiple products.

        Returns a mapping from normalised URL to snapshot list.
        """
        result: dict[str, list[PriceSnapshot]] = {}
        for raw_url in product_urls:
            history = self.get_price_history(raw_url)
            if history:
                result[normalize_url(raw_url)] = history
        return result

    def get_trend_summary(
        self, product_url: str,
    ) -> dict[str, object] | None:
        """Compute min / max / avg / latest price for a product."""
        url = normalize_url(product_url)
        row = self._conn.execute(
            "SELECT MIN(s.price), MAX(s.price), "
            "       AVG(s.price), COUNT(s.id) "
            "FROM price_snapshots s "
            "JOIN products p ON p.id = s.product_id "
            "WHERE p.url = ?",
            (url,),
        ).fetchone()
        if row is None or row[3] == 0:
            return None
        latest_row = self._conn.execute(
            "SELECT s.price "
            "FROM price_snapshots s "
            "JOIN products p ON p.id = s.product_id "
            "WHERE p.url = ? "
            "ORDER BY s.scraped_at DESC LIMIT 1",
            (url,),
        ).fetchone()
        latest_price: float = (
            latest_row[0] if latest_row else 0.0
        )
        return {
            "min": row[0],
            "max": row[1],
            "avg": round(row[2], 2),
            "count": row[3],
            "latest": latest_price,
        }

    # ── Starring / watchlist ─────────────────────────────

    def toggle_star(self, product_url: str) -> bool:
        """Toggle star status for a product. Returns new state."""
        url = normalize_url(product_url)
        row = self._conn.execute(
            "SELECT id, is_starred FROM products WHERE url = ?",
            (url,),
        ).fetchone()
        if row is None:
            return False
        new_state = 0 if row[1] else 1
        self._conn.execute(
            "UPDATE products SET is_starred = ? WHERE id = ?",
            (new_state, row[0]),
        )
        self._conn.commit()
        return bool(new_state)

    def is_starred(self, product_url: str) -> bool:
        """Check if a product is starred."""
        url = normalize_url(product_url)
        row = self._conn.execute(
            "SELECT is_starred FROM products WHERE url = ?",
            (url,),
        ).fetchone()
        return bool(row[0]) if row else False

    def get_starred_products(
        self,
    ) -> list[dict[str, object]]:
        """Return all starred products with latest price + stats."""
        rows = self._conn.execute(
            "SELECT p.id, p.url, p.title, p.source, p.first_seen "
            "FROM products p WHERE p.is_starred = 1 "
            "ORDER BY p.title",
        ).fetchall()
        results: list[dict[str, object]] = []
        for r in rows:
            product_id: int = r[0]
            snap = self._conn.execute(
                "SELECT price, scraped_at "
                "FROM price_snapshots WHERE product_id = ? "
                "ORDER BY scraped_at DESC LIMIT 1",
                (product_id,),
            ).fetchone()
            stats = self._conn.execute(
                "SELECT MIN(price), MAX(price), "
                "       AVG(price), COUNT(id) "
                "FROM price_snapshots WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            results.append({
                "url": r[1],
                "title": r[2],
                "source": r[3],
                "first_seen": r[4],
                "latest_price": snap[0] if snap else 0.0,
                "last_scraped": snap[1] if snap else "",
                "min_price": stats[0] if stats else 0.0,
                "max_price": stats[1] if stats else 0.0,
                "avg_price": (
                    round(stats[2], 2) if stats else 0.0
                ),
                "snapshot_count": stats[3] if stats else 0,
            })
        return results

    # ── Legacy import ────────────────────────────────────

    def import_single_file(self, filepath: Path) -> int:
        """Import one JSON result file into the database.

        Parses the timestamp from the filename and inserts
        products as historical snapshots.  Returns the count.
        """
        match = _FILENAME_RE.match(filepath.name)
        if not match:
            logger.debug(
                "Skipping non-standard filename: %s",
                filepath.name,
            )
            return 0

        timestamp_str = match.group(2)
        try:
            scraped_at = datetime.strptime(
                timestamp_str, "%Y%m%d_%H%M%S",
            )
        except ValueError:
            logger.warning(
                "Bad timestamp in filename: %s",
                filepath.name,
            )
            return 0

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read %s: %s",
                filepath.name,
                exc,
            )
            return 0

        if not isinstance(data, list):
            return 0

        items: list[object] = cast(list[object], data)
        entries: list[dict[str, object]] = [
            e for e in items if isinstance(e, dict)
        ]
        products: list[Product] = []
        for row in entries:
            products.append(Product(
                title=str(row.get("title", "")),
                price=float(str(row.get("price", 0))),
                currency=str(row.get("currency", "AED")),
                rating=str(row.get("rating", "")),
                url=str(row.get("url", "")),
                source=str(row.get("source", "")),
            ))
        return self.record_snapshots(
            products, scraped_at=scraped_at,
        )

    def import_legacy_results(
        self,
        results_dir: Path | None = None,
    ) -> int:
        """Import all JSON result files from a directory.

        Returns the total number of snapshots imported.
        """
        directory = results_dir or Settings.RESULTS_DIR
        if not directory.exists():
            logger.warning(
                "Results directory not found: %s", directory,
            )
            return 0

        total = 0
        files = sorted(directory.glob("*.json"))
        for filepath in files:
            total += self.import_single_file(filepath)

        logger.info(
            "Legacy import complete: %d snapshots from %d files",
            total,
            len(files),
        )
        return total
