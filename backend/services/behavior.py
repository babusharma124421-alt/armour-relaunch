"""Rolling behavioral risk scoring backed by a reproducible XGBoost model."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    from xgboost import XGBClassifier
except Exception as exc:  # pragma: no cover - fallback is for minimal environments
    XGBClassifier = None  # type: ignore[assignment,misc]
    logging.getLogger(__name__).warning("XGBoost unavailable; using sklearn fallback: %s", exc)

try:
    from sklearn.ensemble import GradientBoostingClassifier
except Exception:  # pragma: no cover
    GradientBoostingClassifier = None  # type: ignore[assignment,misc]

try:
    from ..schemas import BehaviorResult
except ImportError:  # Supports imports when running from backend/.
    from schemas import BehaviorResult

LOGGER = logging.getLogger(__name__)

FEATURE_NAMES = [
    "duration_seconds",
    "chunks_processed",
    "score_slope",
    "max_score_so_far",
    "avg_score_so_far",
    "caller_report_count",
    "community_report_count",
]


class BehaviorScoringService:
    """Train once at startup and score a session's rolling trajectory."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or (
            Path(__file__).resolve().parents[1] / "data" / "behavior_bootstrap.csv"
        )
        if not self.data_path.exists():
            generate_bootstrap_data(self.data_path)
        self.model = self._train_model()

    @staticmethod
    def _read_dataset(path: Path) -> tuple[np.ndarray, np.ndarray]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        if not rows:
            raise ValueError("Behavior bootstrap dataset is empty")
        features = np.array(
            [[float(row[name]) for name in FEATURE_NAMES] for row in rows],
            dtype=np.float32,
        )
        labels = np.array([int(row["label"]) for row in rows], dtype=np.int64)
        return features, labels

    def _train_model(self) -> Any:
        features, labels = self._read_dataset(self.data_path)
        if XGBClassifier is not None:
            model: Any = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                use_label_encoder=False,
                eval_metric="mlogloss",
                random_state=42,
                n_jobs=1,
            )
        elif GradientBoostingClassifier is not None:
            LOGGER.warning("Training sklearn GradientBoosting fallback instead of XGBoost")
            model = GradientBoostingClassifier(random_state=42, n_estimators=100, max_depth=4)
        else:
            raise RuntimeError("Neither xgboost nor scikit-learn is available")
        model.fit(features, labels)
        LOGGER.info("Behavior model trained on %d synthetic rows", len(labels))
        return model

    @staticmethod
    def _started_timestamp(session_state: dict[str, Any]) -> float:
        started_at = session_state.get("started_at")
        if isinstance(started_at, datetime):
            timestamp = started_at
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp.timestamp()
        if isinstance(started_at, (int, float)):
            return float(started_at)
        if isinstance(started_at, str):
            try:
                return datetime.fromisoformat(started_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
        return datetime.now(timezone.utc).timestamp()

    @staticmethod
    def _score_slope(scores: list[float]) -> float:
        recent = np.asarray(scores[-5:], dtype=np.float64)
        if recent.size < 2:
            return 0.0
        slope = float(np.polyfit(np.arange(recent.size), recent, 1)[0])
        return float(np.clip(slope, -10.0, 10.0))

    def _features_from_state(self, session_state: dict[str, Any]) -> np.ndarray:
        history = [float(value) for value in session_state.get("score_history", [])]
        caller_result = session_state.get("caller_result")
        if caller_result is None:
            caller_reports = 0.0
            community_reports = 0.0
        elif hasattr(caller_result, "report_count"):
            caller_reports = float(caller_result.report_count)
            community_reports = float(caller_result.community_report_count)
        else:
            caller_reports = float(caller_result.get("report_count", 0) or 0)
            community_reports = float(caller_result.get("community_report_count", 0) or 0)
        duration = max(0.0, datetime.now(timezone.utc).timestamp() - self._started_timestamp(session_state))
        return np.array(
            [
                duration,
                float(session_state.get("chunks_processed", 0)),
                self._score_slope(history),
                max(history) if history else 0.0,
                float(np.mean(history)) if history else 0.0,
                caller_reports,
                community_reports,
            ],
            dtype=np.float32,
        ).reshape(1, -1)

    def score(self, session_state: dict[str, Any]) -> BehaviorResult:
        """Predict behavioral risk from the current session state."""

        features = self._features_from_state(session_state)
        probabilities = np.asarray(self.model.predict_proba(features)[0], dtype=np.float64)
        classes = [int(value) for value in getattr(self.model, "classes_", range(len(probabilities)))]
        probability_by_class = {label: float(probabilities[index]) for index, label in enumerate(classes)}
        behavior_score = probability_by_class.get(1, 0.0) * 50.0 + probability_by_class.get(2, 0.0) * 100.0
        importances = np.asarray(getattr(self.model, "feature_importances_", np.zeros(len(FEATURE_NAMES))))
        top_indices = np.argsort(importances)[::-1][:3]
        top_features = [FEATURE_NAMES[int(index)] for index in top_indices]
        return BehaviorResult(
            behavior_score=round(float(np.clip(behavior_score, 0.0, 100.0)), 2),
            top_features=top_features,
        )



def generate_bootstrap_data(path: Path, rows: int = 200) -> Path:
    """Generate deterministic synthetic benign, suspicious, and critical rows."""

    if rows < 3:
        raise ValueError("rows must be at least three")
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    benign_count = rows // 3
    suspicious_count = rows // 3
    critical_count = rows - benign_count - suspicious_count
    records: list[list[float | int]] = []

    for _ in range(benign_count):
        records.append(
            [
                rng.uniform(10, 180),
                rng.integers(1, 80),
                rng.uniform(-0.25, 0.35),
                rng.uniform(2, 29),
                rng.uniform(2, 25),
                0,
                0,
                0,
            ]
        )
    for _ in range(suspicious_count):
        records.append(
            [
                rng.uniform(30, 260),
                rng.integers(2, 120),
                rng.uniform(0.05, 1.25),
                rng.uniform(30, 70),
                rng.uniform(28, 68),
                rng.integers(0, 5),
                rng.integers(0, 3),
                1,
            ]
        )
    for _ in range(critical_count):
        records.append(
            [
                rng.uniform(30, 360),
                rng.integers(4, 170),
                rng.uniform(0.35, 2.75),
                rng.uniform(70, 100),
                rng.uniform(55, 96),
                rng.integers(2, 11),
                rng.integers(1, 6),
                2,
            ]
        )
    rng.shuffle(records)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([*FEATURE_NAMES, "label"])
        writer.writerows(
            [
                [
                    f"{float(value):.6f}" if isinstance(value, (float, np.floating)) else int(value)
                    for value in row
                ]
                for row in records
            ]
        )
    return path


# NOTE: This model is bootstrapped on synthetic data.
# Retrain on real labeled call logs before any production
# accuracy claims. Feature engineering should also include
# call-type metadata when available.
