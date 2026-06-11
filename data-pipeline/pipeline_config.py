"""Loaders for NyayaDraft pipeline configuration and on-disk assets.

These functions read the central ``config.yaml``, the per-doc-type meta-prompt
specs, the scenario seed bank, and the value seeds (names/cities). They are the
single source of truth that ``generate.py`` and the test-suite fixtures build on
top of. Every loader returns plain, JSON-style data structures so callers can
treat the result as immutable inputs.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PIPELINE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PIPELINE_DIR / "config.yaml"
META_DIR = PIPELINE_DIR / "meta_prompts"
SEEDS_DIR = PIPELINE_DIR / "seeds"
SCENARIOS_PATH = SEEDS_DIR / "scenarios.json"
SYSTEM_PROMPT_PATH = PIPELINE_DIR / "system_prompt.txt"

# Value seeds consumed by variation.py. Keys are the seed names; values the file
# stems under seeds/. Kept explicit so a missing seed fails loudly.
SEED_FILES = {
    "names": "names.json",
    "cities": "cities.json",
}


def _read_json(path: Path) -> Any:
    """Read and parse a UTF-8 JSON file, raising a clear error if absent."""
    if not path.exists():
        raise FileNotFoundError(f"Expected asset not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# Each public loader resolves its default path BEFORE the cache is consulted and
# delegates to a private ``@lru_cache`` helper keyed on the resolved Path. This
# guarantees ``load_x()`` and ``load_x(DEFAULT_PATH)`` share a single cache entry
# instead of being stored under two distinct keys (None vs the resolved Path).
# The public functions re-export the helper's ``cache_clear`` so callers and
# tests can still invalidate the cache via the public API.


@lru_cache(maxsize=8)
def _load_config_cached(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{config_path.name} did not parse to a mapping")
    return data


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load the central generation config from ``config.yaml``."""
    return _load_config_cached(path or CONFIG_PATH)


load_config.cache_clear = _load_config_cached.cache_clear  # type: ignore[attr-defined]


@lru_cache(maxsize=8)
def _load_specs_cached(directory: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for spec_path in sorted(directory.glob("*.json")):
        spec = _read_json(spec_path)
        doc_type = spec.get("doc_type")
        if doc_type != spec_path.stem:
            raise ValueError(
                f"{spec_path.name}: doc_type '{doc_type}' != filename stem"
            )
        specs[doc_type] = spec
    if not specs:
        raise FileNotFoundError(f"No meta-prompt specs found in {directory}")
    return specs


def load_specs(meta_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load every meta-prompt spec, keyed by ``doc_type``."""
    return _load_specs_cached(meta_dir or META_DIR)


load_specs.cache_clear = _load_specs_cached.cache_clear  # type: ignore[attr-defined]


@lru_cache(maxsize=8)
def _load_scenarios_cached(path: Path) -> dict[str, list[dict[str, Any]]]:
    scenarios = _read_json(path)
    if not isinstance(scenarios, dict):
        raise ValueError("scenarios.json did not parse to a mapping")
    return scenarios


def load_scenarios(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load the scenario bank, keyed by ``doc_type``."""
    return _load_scenarios_cached(path or SCENARIOS_PATH)


load_scenarios.cache_clear = _load_scenarios_cached.cache_clear  # type: ignore[attr-defined]


@lru_cache(maxsize=8)
def _load_seeds_cached(directory: Path) -> dict[str, Any]:
    return {
        name: _read_json(directory / filename)
        for name, filename in SEED_FILES.items()
    }


def load_seeds(seeds_dir: Path | None = None) -> dict[str, Any]:
    """Load the value seeds (names, cities) used for fact synthesis."""
    return _load_seeds_cached(seeds_dir or SEEDS_DIR)


load_seeds.cache_clear = _load_seeds_cached.cache_clear  # type: ignore[attr-defined]


@lru_cache(maxsize=8)
def _load_system_prompt_cached(prompt_path: Path) -> str:
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def load_system_prompt(path: Path | None = None) -> str:
    """Load the fixed system prompt text."""
    return _load_system_prompt_cached(path or SYSTEM_PROMPT_PATH)


load_system_prompt.cache_clear = _load_system_prompt_cached.cache_clear  # type: ignore[attr-defined]


def display_names(specs: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map each ``doc_type`` to its human-facing display name."""
    return {
        doc_type: spec.get("display_name", doc_type)
        for doc_type, spec in specs.items()
    }
