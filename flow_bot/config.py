"""Configuration loader for Flow Bot.

Provides YAML-first loading with JSON fallback and helper utilities
for ticker-specific configuration merging.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None


DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Load configuration from YAML or JSON.

    If ``path`` is ``None``, the loader will look for ``config.yaml`` in the
    repository root. YAML is preferred; if PyYAML is not installed, a JSON
    file with the same structure can be used instead.
    """

    def _load_yaml(config_path: Path) -> Dict[str, Any]:
        if yaml is None:
            raise RuntimeError("PyYAML not installed; falling back to JSON")
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _load_json(config_path: Path) -> Dict[str, Any]:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    if config_path.suffix.lower() in {".yaml", ".yml"}:
        try:
            return _load_yaml(config_path)
        except RuntimeError:
            # Fall back to JSON with same stem if YAML unavailable
            json_path = config_path.with_suffix(".json")
            if json_path.exists():
                return _load_json(json_path)
            raise
    if config_path.suffix.lower() == ".json":
        return _load_json(config_path)

    # Attempt YAML then JSON based on default filenames
    try:
        return _load_yaml(config_path)
    except Exception:
        json_path = config_path.with_suffix(".json")
        if json_path.exists():
            return _load_json(json_path)
        raise


def get_ticker_config(global_cfg: Dict[str, Any], ticker: str, mode: str) -> Dict[str, Any]:
    """Merge mode/ticker specific overrides.

    Priority (lowest to highest):
    1. Base mode config (e.g., ``scalp``)
    2. Default ticker config under ``tickers.default``
    3. Ticker-specific overrides under ``tickers.overrides``
    4. Mode-specific overrides for that ticker
    """

    mode_cfg = dict(global_cfg.get(mode, {}))
    ticker_default = global_cfg.get("tickers", {}).get("default", {})
    ticker_override = global_cfg.get("tickers", {}).get("overrides", {}).get(ticker, {})

    merged = {**mode_cfg, **ticker_default}

    # Apply top-level ticker overrides
    merged.update({k: v for k, v in ticker_override.items() if k not in {"scalp", "day_trade", "swing"}})

    # Apply mode-specific ticker overrides
    mode_override = ticker_override.get(mode, {}) if isinstance(ticker_override, dict) else {}
    merged.update(mode_override)
    return merged
