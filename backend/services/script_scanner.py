"""Fast, offline scam-script pattern scanner."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from ..schemas import ScriptResult
except ImportError:  # Supports execution from the backend directory.
    from schemas import ScriptResult

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompiledPattern:
    """A validated YAML pattern ready for repeated searches."""

    identifier: str
    weight: float
    category: str
    expression: re.Pattern[str]


class ScriptScannerService:
    """Load scam indicators from YAML and score every transcript segment."""

    def __init__(self, patterns_path: Path | None = None) -> None:
        self.patterns_path = patterns_path or (
            Path(__file__).resolve().parents[1] / "data" / "script_patterns.yaml"
        )
        self.patterns = self._load_patterns(self.patterns_path)
        weights = sorted((pattern.weight for pattern in self.patterns), reverse=True)
        self.max_possible_weight_sum = sum(weights[:5]) or 1.0
        LOGGER.info(
            "Loaded %d script patterns; top-five normalization weight %.2f",
            len(self.patterns),
            self.max_possible_weight_sum,
        )

    @staticmethod
    def _load_patterns(path: Path) -> list[CompiledPattern]:
        if not path.exists():
            raise FileNotFoundError(f"Script pattern file not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            payload: Any = yaml.safe_load(handle)
        raw_patterns = payload.get("patterns", []) if isinstance(payload, dict) else []
        if not isinstance(raw_patterns, list):
            raise ValueError("script_patterns.yaml must contain a patterns list")
        compiled: list[CompiledPattern] = []
        for raw in raw_patterns:
            if not isinstance(raw, dict):
                LOGGER.warning("Ignoring malformed script pattern entry: %r", raw)
                continue
            try:
                identifier = str(raw["id"])
                weight = float(raw["weight"])
                category = str(raw["category"])
                expression = re.compile(str(raw["regex"]))
                if weight < 0:
                    raise ValueError("pattern weight cannot be negative")
            except (KeyError, TypeError, ValueError, re.error) as exc:
                LOGGER.warning("Ignoring malformed script pattern %r: %s", raw, exc)
                continue
            compiled.append(
                CompiledPattern(
                    identifier=identifier,
                    weight=weight,
                    category=category,
                    expression=expression,
                )
            )
        if not compiled:
            raise ValueError("No valid script patterns were loaded")
        return compiled

    def scan(self, transcript: str) -> ScriptResult:
        """Scan one transcript and normalize five or more strong matches to 100."""

        if not transcript or len(transcript.strip()) < 3:
            return ScriptResult(script_score=0.0)
        matched_patterns: list[str] = []
        matched_categories: list[str] = []
        matched_weight = 0.0
        for pattern in self.patterns:
            if pattern.expression.search(transcript):
                matched_patterns.append(pattern.identifier)
                matched_categories.append(pattern.category)
                matched_weight += pattern.weight
        score = min(100.0, (matched_weight * 100.0) / self.max_possible_weight_sum)
        return ScriptResult(
            script_score=round(score, 2),
            matched_patterns=matched_patterns,
            matched_categories=list(dict.fromkeys(matched_categories)),
        )
