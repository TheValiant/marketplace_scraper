#!/usr/bin/env bash
# catall.sh — Print every project source file with a header banner.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

files=(
  # ── Entry point ──
  main.py

  # ── Config / infra ──
  pylance.sh
  requirements.txt
  .github/copilot-instructions.md

  # ── Source: config ──
  src/__init__.py
  src/config/__init__.py
  src/config/settings.py
  src/config/logging_config.py
  src/config/selectors.json

  # ── Source: models ──
  src/models/__init__.py
  src/models/product.py
  src/models/price_snapshot.py

  # ── Source: filters ──
  src/filters/__init__.py
  src/filters/deduplicator.py
  src/filters/product_filter.py
  src/filters/product_validator.py
  src/filters/query_enhancer.py
  src/filters/query_parser.py

  # ── Source: scrapers ──
  src/scrapers/__init__.py
  src/scrapers/base_scraper.py
  src/scrapers/amazon_scraper.py
  src/scrapers/aster_scraper.py
  src/scrapers/binsina_scraper.py
  src/scrapers/iherb_scraper.py
  src/scrapers/life_pharmacy_scraper.py
  src/scrapers/lulu_scraper.py
  src/scrapers/noon_scraper.py
  src/scrapers/sephora_scraper.py
  src/scrapers/carrefour_scraper.py

  # ── Source: services ──
  src/services/__init__.py
  src/services/health_checker.py
  src/services/search_orchestrator.py

  # ── Source: storage ──
  src/storage/__init__.py
  src/storage/chart_exporter.py
  src/storage/file_manager.py
  src/storage/price_history_db.py
  src/storage/query_cache.py

  # ── Source: CLI ──
  src/cli/__init__.py
  src/cli/runner.py

  # ── Source: UI ──
  src/ui/__init__.py
  src/ui/app.py
  src/ui/styles.css

  # ── Tests ──
  tests/__init__.py
  tests/conftest.py
  tests/run_search_matrix.py
  tests/test_advanced_search.py
  tests/test_amazon_scraper.py
  tests/test_app.py
  tests/test_aster_scraper.py
  tests/test_base_scraper.py
  tests/test_binsina_scraper.py
  tests/test_chart_exporter.py
  tests/test_deduplicator.py
  tests/test_file_manager.py
  tests/test_health_checker.py
  tests/test_iherb_scraper.py
  tests/test_life_pharmacy_scraper.py
  tests/test_logging_config.py
  tests/test_noon_scraper.py
  tests/test_price_history_db.py
  tests/test_product_filter.py
  tests/test_product_model.py
  tests/test_product_validator.py
  tests/test_query_cache.py
  tests/test_query_enhancer.py
  tests/test_query_parser.py
  tests/test_search_orchestrator.py
  tests/test_settings.py
)

for f in "${files[@]}"; do
  filepath="$ROOT/$f"
  if [[ -f "$filepath" ]]; then
    echo "================================================================================"
    echo "FILE: $f"
    echo "================================================================================"
    cat "$filepath"
    echo ""
  fi
done
