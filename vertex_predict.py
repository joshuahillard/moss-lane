#!/usr/bin/env python3
"""
Lazarus Vertex AI — Prediction Integration

PURPOSE:
  Loads the trained XGBoost model and scores incoming trade candidates.
  Designed to plug into the SignalAggregator in lazarus.py as a score
  adjustment — boost high-confidence signals, suppress low-confidence ones.

HOW IT WORKS:
  1. On startup, loads the model from disk or GCS
  2. When a candidate passes the 9-point filter, score_candidate() is called
  3. The model returns a probability (0.0 to 1.0) of profitability
  4. The SignalAggregator adjusts the candidate's score:
     - probability > 0.6 → boost score by 20% (model says likely winner)
     - probability < 0.3 → penalize score by 30% (model says likely loser)
     - 0.3 to 0.6 → no adjustment (model is uncertain, defer to filters)

FEATURE FLAG:
  Set VERTEX_AI_ENABLED=True to activate. Default is False.
  The bot runs identically with or without the model — it's additive, not
  a replacement for the 9-point filter cascade.

USAGE:
  # In lazarus.py or signal aggregator:
  from vertex_predict import predictor

  if predictor.enabled:
      adjusted_score = predictor.adjust_score(candidate_dict, original_score)

  # candidate_dict must have keys matching FEATURE_COLUMNS:
  # score, chg_pct, mc, liq, hourly, hour_utc, day_of_week,
  # smart_money_confirmed, rug_risk, source
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Dict, Optional

log = logging.getLogger("fort_v2")

MODEL_FILENAME = "lazarus_model.json"
METADATA_FILENAME = "lazarus_model_meta.json"

FEATURE_COLUMNS = [
    "score", "chg_pct", "mc", "liq", "hourly",
    "hour_utc", "day_of_week", "smart_money", "rug_risk_enc", "source_enc",
    "liq_mc_ratio", "vol_liq_ratio", "trading_session",
]

SOURCE_MAP = {
    "dexscreener_momentum": 0,
    "smart_money": 1,
    "combined": 2,
}

# Score adjustment thresholds
BOOST_THRESHOLD = 0.6       # probability above this → boost signal score
PENALIZE_THRESHOLD = 0.3    # probability below this → penalize signal score
BOOST_FACTOR = 1.20         # +20% score boost for high-confidence predictions
PENALIZE_FACTOR = 0.70      # -30% score penalty for low-confidence predictions


class LazarusPredictor:
    """
    Loads the trained model and scores trade candidates.

    Feature-flagged: does nothing when VERTEX_AI_ENABLED != True.
    Fails gracefully: if the model can't load, predictions are skipped
    and the bot runs on filters alone.
    """

    def __init__(self):
        self.enabled = os.environ.get("VERTEX_AI_ENABLED", "false").lower() == "true"
        self.model = None
        self.metadata = None

        if not self.enabled:
            log.info("Vertex AI predictor: disabled (set VERTEX_AI_ENABLED=True to activate)")
            return

        self._load_model()

    def _load_model(self):
        """Load model from local disk or GCS."""
        # Check local first
        model_path = os.environ.get("VERTEX_MODEL_PATH", MODEL_FILENAME)
        meta_path = model_path.replace(".json", "_meta.json")

        # If path is a GCS URI, download first
        if model_path.startswith("gs://"):
            model_path, meta_path = self._download_from_gcs(model_path)
            if not model_path:
                self._disable("GCS download failed")
                return

        if not os.path.exists(model_path):
            self._disable(f"model file not found: {model_path}")
            return

        try:
            import xgboost as xgb
            import numpy as np
            self._np = np

            self.model = xgb.XGBClassifier()
            self.model.load_model(model_path)
            log.info(f"Vertex AI predictor: model loaded from {model_path}")

            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    self.metadata = json.load(f)
                metrics = self.metadata.get("metrics", {})
                log.info(f"Vertex AI predictor: F1={metrics.get('f1', '?'):.3f} "
                         f"accuracy={metrics.get('accuracy', '?'):.3f} "
                         f"trained on {metrics.get('train_size', '?')} trades")

        except ImportError:
            self._disable("xgboost not installed")
        except Exception as e:
            self._disable(f"model load error: {e}")

    def _download_from_gcs(self, gcs_model_path: str):
        """Download model files from GCS to a temp directory."""
        try:
            tmpdir = tempfile.mkdtemp(prefix="lazarus_model_")
            gcs_meta_path = gcs_model_path.replace(".json", "_meta.json")

            for gcs_path, filename in [
                (gcs_model_path, MODEL_FILENAME),
                (gcs_meta_path, METADATA_FILENAME),
            ]:
                local_path = os.path.join(tmpdir, filename)
                result = subprocess.run(
                    ["gsutil", "cp", gcs_path, local_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    log.warning(f"GCS download failed for {gcs_path}: {result.stderr}")
                    return None, None

            return (
                os.path.join(tmpdir, MODEL_FILENAME),
                os.path.join(tmpdir, METADATA_FILENAME),
            )
        except Exception as e:
            log.warning(f"GCS download error: {e}")
            return None, None

    def _disable(self, reason: str):
        """Gracefully disable predictions with a log message."""
        self.enabled = False
        self.model = None
        log.warning(f"Vertex AI predictor: disabled — {reason}")

    def predict_probability(self, candidate: Dict) -> Optional[float]:
        """
        Predict probability of profitability for a trade candidate.

        Args:
            candidate: dict with keys from the scanner signal
                Required: score, chg_pct, mc, liq, hourly
                Optional: hour_utc, day_of_week, smart_money_confirmed,
                         rug_risk, source

        Returns:
            Float 0.0-1.0 (probability of profit), or None if prediction fails
        """
        if not self.enabled or self.model is None:
            return None

        try:
            features = self._extract_features(candidate)
            X = self._np.array([features])
            prob = self.model.predict_proba(X)[0][1]  # probability of class 1 (profitable)
            return float(prob)
        except Exception as e:
            log.warning(f"Vertex AI prediction error: {e}")
            return None

    def _extract_features(self, candidate: Dict) -> list:
        """Convert a candidate dict to a feature vector."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mc = float(candidate.get("mc", 0))
        liq = float(candidate.get("liq", 0))
        hourly = float(candidate.get("hourly", 0))
        hour_utc = int(candidate.get("hour_utc", now.hour))

        # Trading session: 0=Asia(0-7), 1=Europe(8-13), 2=US(14-21), 3=Off(22-23)
        if hour_utc < 8:
            session = 0
        elif hour_utc < 14:
            session = 1
        elif hour_utc < 22:
            session = 2
        else:
            session = 3

        return [
            float(candidate.get("score", 0)),
            float(candidate.get("chg_pct", 0)),
            mc,
            liq,
            hourly,
            hour_utc,
            int(candidate.get("day_of_week", now.weekday())),
            int(candidate.get("smart_money_confirmed", 0)),
            1 if candidate.get("rug_risk", "low") == "high" else 0,
            SOURCE_MAP.get(candidate.get("source", "dexscreener_momentum"), 0),
            liq / mc if mc > 0 else 0,         # liq_mc_ratio
            hourly / liq if liq > 0 else 0,    # vol_liq_ratio
            session,                             # trading_session
        ]

    def adjust_score(self, candidate: Dict, original_score: float) -> float:
        """
        Adjust a candidate's signal score based on model prediction.

        This is the integration point for SignalAggregator. The model
        nudges scores up or down — it doesn't override the filter cascade.

        Args:
            candidate: dict with scanner signal data
            original_score: the score from the filter cascade

        Returns:
            Adjusted score (boosted, penalized, or unchanged)
        """
        prob = self.predict_probability(candidate)
        if prob is None:
            return original_score

        if prob >= BOOST_THRESHOLD:
            adjusted = original_score * BOOST_FACTOR
            log.info(f"  Vertex AI: {prob:.2f} confidence → BOOST "
                     f"({original_score:.2f} → {adjusted:.2f})")
            return adjusted

        elif prob <= PENALIZE_THRESHOLD:
            adjusted = original_score * PENALIZE_FACTOR
            log.info(f"  Vertex AI: {prob:.2f} confidence → PENALIZE "
                     f"({original_score:.2f} → {adjusted:.2f})")
            return adjusted

        else:
            log.info(f"  Vertex AI: {prob:.2f} confidence → NO CHANGE "
                     f"(uncertain range {PENALIZE_THRESHOLD}-{BOOST_THRESHOLD})")
            return original_score


# ── Global singleton ─────────────────────────────────────────────────────────
# Import this in lazarus.py: from vertex_predict import predictor
# It initializes once at import time and does nothing if disabled.
predictor = LazarusPredictor()
