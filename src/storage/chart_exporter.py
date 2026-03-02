# src/storage/chart_exporter.py

"""Generate interactive Plotly HTML charts from price history."""

import importlib
import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from src.config.settings import Settings
from src.models.price_snapshot import PriceSnapshot
from src.storage.price_history_db import PriceHistoryDB

logger = logging.getLogger("ecom_search.chart")

_CHARTS_DIR: Path = Settings.DATA_DIR / "charts"


def _get_plotly_go() -> ModuleType:
    """Import plotly.graph_objects lazily."""
    return importlib.import_module("plotly.graph_objects")


def _ensure_charts_dir() -> Path:
    """Create charts directory if it doesn't exist."""
    _CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    return _CHARTS_DIR


def _build_single_chart(
    snapshots: list[PriceSnapshot],
    title: str,
) -> Any:
    """Build a Plotly line chart for one product."""
    go = _get_plotly_go()
    dates = [s.scraped_at for s in snapshots]
    prices = [s.price for s in snapshots]
    currency = snapshots[0].currency if snapshots else "AED"

    fig: Any = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=prices,
        mode="lines+markers",
        name=title[:50],
        hovertemplate=(
            "%{x|%Y-%m-%d %H:%M}<br>"
            f"Price: %{{y:.2f}} {currency}"
            "<extra></extra>"
        ),
    ))

    min_price = min(prices)
    max_price = max(prices)
    min_idx = prices.index(min_price)
    max_idx = prices.index(max_price)

    fig.add_annotation(
        x=dates[min_idx], y=min_price,
        text=f"Min: {min_price:.2f}",
        showarrow=True, arrowhead=2,
    )
    fig.add_annotation(
        x=dates[max_idx], y=max_price,
        text=f"Max: {max_price:.2f}",
        showarrow=True, arrowhead=2,
    )

    fig.update_layout(
        title=f"Price History — {title[:60]}",
        xaxis_title="Date",
        yaxis_title=f"Price ({currency})",
        hovermode="x unified",
        template="plotly_white",
    )
    return fig


def export_price_chart(
    product_url: str,
    db: PriceHistoryDB,
    open_browser: bool = True,
) -> Path | None:
    """Export a single product's price chart as HTML."""
    snapshots = db.get_price_history(product_url)
    if len(snapshots) < 2:
        logger.warning(
            "Not enough data points for chart: %s",
            product_url[:60],
        )
        return None

    fig = _build_single_chart(
        snapshots, snapshots[0].title,
    )

    charts_dir = _ensure_charts_dir()
    slug = (
        snapshots[0].title[:30]
        .replace(" ", "_")
        .replace("/", "_")
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = charts_dir / f"{slug}_{stamp}.html"
    fig.write_html(str(filepath))
    logger.info("Chart saved to %s", filepath)

    if open_browser:
        webbrowser.open(filepath.as_uri())

    return filepath


def export_comparison_chart(
    product_urls: list[str],
    db: PriceHistoryDB,
    open_browser: bool = True,
) -> Path | None:
    """Export an overlay chart comparing multiple products."""
    trends = db.get_price_trends(product_urls)
    if not trends:
        logger.warning("No trend data for comparison chart")
        return None

    go = _get_plotly_go()
    fig: Any = go.Figure()
    for _url, snapshots in trends.items():
        if len(snapshots) < 2:
            continue
        dates = [s.scraped_at for s in snapshots]
        prices = [s.price for s in snapshots]
        label = (
            f"{snapshots[0].title[:40]} "
            f"({snapshots[0].source})"
        )
        fig.add_trace(go.Scatter(
            x=dates,
            y=prices,
            mode="lines+markers",
            name=label,
            hovertemplate=(
                "%{x|%Y-%m-%d %H:%M}<br>"
                "Price: %{y:.2f}"
                "<extra></extra>"
            ),
        ))

    if not fig.data:
        return None

    fig.update_layout(
        title="Price Comparison",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "y": -0.15},
    )

    charts_dir = _ensure_charts_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = charts_dir / f"comparison_{stamp}.html"
    fig.write_html(str(filepath))
    logger.info("Comparison chart saved to %s", filepath)

    if open_browser:
        webbrowser.open(filepath.as_uri())

    return filepath


def export_watchlist_dashboard(
    db: PriceHistoryDB,
    open_browser: bool = True,
) -> Path | None:
    """Export a dashboard chart for all starred products."""
    starred = db.get_starred_products()
    if not starred:
        logger.warning("No starred products for dashboard")
        return None

    urls = [str(s["url"]) for s in starred]
    return export_comparison_chart(
        urls, db, open_browser=open_browser,
    )
