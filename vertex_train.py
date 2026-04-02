#!/usr/bin/env python3
"""
Lazarus Vertex AI — Model Training

PURPOSE:
  Trains an XGBoost binary classifier to predict whether a trade will be
  profitable, based on entry-time features from the scanner.

WHY XGBOOST:
  - Best-in-class for small tabular datasets (161 rows)
  - Fast training (seconds, not hours)
  - Interpretable (feature importance reveals what drives wins)
  - Lightweight model file (~50KB) loads instantly at bot startup
  - Neural nets would overfit on this dataset size

PIPELINE:
  1. Load features.csv (from vertex_feature_extract.py)
  2. Split into train/test (80/20, stratified to preserve win/loss ratio)
  3. Train XGBoost with class weighting (handles 30/70 imbalance)
  4. Evaluate: accuracy, precision, recall, F1, confusion matrix
  5. Print feature importance (what the model learned)
  6. Save model to disk (lazarus_model.json)
  7. Optionally upload to GCS for Cloud Run to fetch

USAGE:
  Local training:
    python vertex_train.py --input features.csv

  Upload to GCS after training:
    python vertex_train.py --input features.csv --upload-gcs gs://moss-lane-models/lazarus/

  Full pipeline (extract + train):
    python vertex_feature_extract.py --sqlite-path ./lazarus.db --output features.csv
    python vertex_train.py --input features.csv --upload-gcs gs://moss-lane-models/lazarus/
"""

import argparse
import csv
import json
import os
import sys
import subprocess
from typing import List, Dict, Tuple

# Model filename — loaded by vertex_predict.py at bot startup
MODEL_FILENAME = "lazarus_model.json"
METADATA_FILENAME = "lazarus_model_meta.json"

FEATURE_COLUMNS = [
    "score", "chg_pct", "mc", "liq", "hourly",
    "hour_utc", "day_of_week", "smart_money_confirmed", "rug_risk_enc", "source_enc",
    "liq_mc_ratio", "vol_liq_ratio", "trading_session",
]


SOURCE_MAP = {
    "dexscreener_momentum": 0,
    "smart_money": 1,
    "combined": 2,
}


def load_csv(path: str) -> Tuple[List[List[float]], List[int]]:
    """Load features.csv into X (features) and y (labels).

    Handles both pre-encoded CSVs (from vertex_feature_extract.py) and
    raw CSVs exported directly from SQLite (rug_risk as text, source as text).
    """
    X, y = [], []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Encode rug_risk: "high" → 1, anything else → 0
            if "rug_risk_enc" in row:
                rug_enc = float(row["rug_risk_enc"])
            else:
                rug_enc = 1.0 if row.get("rug_risk", "low") == "high" else 0.0

            # Encode source: map string to int
            if "source_enc" in row:
                src_enc = float(row["source_enc"])
            else:
                src_enc = float(SOURCE_MAP.get(row.get("source", ""), 0))

            # Encode target: profitable if pnl_pct > 0
            if "profitable" in row:
                target = int(row["profitable"])
            else:
                target = 1 if float(row.get("pnl_pct", 0)) > 0 else 0

            mc = float(row.get("mc", 0))
            liq = float(row.get("liq", 0))
            hourly = float(row.get("hourly", 0))
            hour_utc = int(float(row.get("hour_utc", 0)))

            # Derived features — compute from raw values if not in CSV
            if "liq_mc_ratio" in row:
                liq_mc = float(row["liq_mc_ratio"])
            else:
                liq_mc = liq / mc if mc > 0 else 0

            if "vol_liq_ratio" in row:
                vol_liq = float(row["vol_liq_ratio"])
            else:
                vol_liq = hourly / liq if liq > 0 else 0

            if "trading_session" in row:
                session = float(row["trading_session"])
            else:
                # 0=Asia(0-7), 1=Europe(8-13), 2=US(14-21), 3=Off(22-23)
                if hour_utc < 8:
                    session = 0
                elif hour_utc < 14:
                    session = 1
                elif hour_utc < 22:
                    session = 2
                else:
                    session = 3

            features = [
                float(row.get("score", 0)),
                float(row.get("chg_pct", 0)),
                mc,
                liq,
                hourly,
                float(hour_utc),
                float(row.get("day_of_week", 0)),
                float(row.get("smart_money_confirmed", 0)),
                rug_enc,
                src_enc,
                liq_mc,
                vol_liq,
                session,
            ]
            X.append(features)
            y.append(target)
    return X, y


def train_model(X_train, y_train, X_test, y_test):
    """Train XGBoost and return the model + metrics."""
    try:
        import xgboost as xgb
        import numpy as np
    except ImportError:
        print("ERROR: Missing dependencies. Run:")
        print("  pip install xgboost numpy scikit-learn")
        sys.exit(1)

    from sklearn.model_selection import cross_val_score
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        confusion_matrix, classification_report,
    )

    X_train = np.array(X_train)
    y_train = np.array(y_train)
    X_test = np.array(X_test)
    y_test = np.array(y_test)

    # Class weight: compensate for 30/70 win/loss imbalance
    # scale_pos_weight = count(negative) / count(positive)
    n_pos = sum(y_train)
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)

    print(f"\nTraining XGBoost classifier...")
    print(f"  Train set: {len(X_train)} rows ({sum(y_train)} wins, {len(y_train) - sum(y_train)} losses)")
    print(f"  Test set:  {len(X_test)} rows ({sum(y_test)} wins, {len(y_test) - sum(y_test)} losses)")
    print(f"  scale_pos_weight: {scale_pos_weight:.2f} (compensates for class imbalance)")

    model = xgb.XGBClassifier(
        n_estimators=100,           # 100 trees (plenty for 161 rows)
        max_depth=3,                # shallow trees prevent overfitting on small data
        learning_rate=0.1,          # standard step size
        scale_pos_weight=scale_pos_weight,  # handle 30/70 imbalance
        eval_metric="logloss",
        random_state=42,            # reproducible results
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Predictions
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    # Metrics
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "win_rate_actual": float(sum(y_test)) / len(y_test),
    }

    print(f"\n{'='*60}")
    print(f"  MODEL EVALUATION")
    print(f"{'='*60}")
    print(f"  Accuracy:  {metrics['accuracy']:.3f}")
    print(f"  Precision: {metrics['precision']:.3f}  (of predicted wins, how many were real)")
    print(f"  Recall:    {metrics['recall']:.3f}  (of actual wins, how many did we catch)")
    print(f"  F1 Score:  {metrics['f1']:.3f}  (harmonic mean of precision and recall)")
    print(f"\n  Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"                    Predicted Loss  Predicted Win")
    print(f"    Actual Loss     {cm[0][0]:>12}  {cm[0][1]:>12}")
    print(f"    Actual Win      {cm[1][0]:>12}  {cm[1][1]:>12}")

    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["loss", "win"]))

    # Feature importance
    importance = model.feature_importances_
    ranked = sorted(zip(FEATURE_COLUMNS, importance), key=lambda x: x[1], reverse=True)
    print(f"  Feature Importance (what the model learned):")
    for feat, imp in ranked:
        bar = "█" * int(imp * 50)
        print(f"    {feat:.<20} {imp:.4f}  {bar}")

    # Cross-validation (more robust than single split)
    cv_scores = cross_val_score(model, np.vstack([X_train, X_test]),
                                np.concatenate([y_train, y_test]),
                                cv=5, scoring="f1")
    print(f"\n  5-Fold Cross-Validation F1: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    metrics["cv_f1_mean"] = float(cv_scores.mean())
    metrics["cv_f1_std"] = float(cv_scores.std())

    return model, metrics, ranked


def save_model(model, metrics: Dict, importance: list, output_dir: str = "."):
    """Save model and metadata to disk."""
    model_path = os.path.join(output_dir, MODEL_FILENAME)
    meta_path = os.path.join(output_dir, METADATA_FILENAME)

    model.save_model(model_path)
    print(f"\n  Model saved: {model_path}")

    metadata = {
        "model_file": MODEL_FILENAME,
        "features": FEATURE_COLUMNS,
        "target": "profitable",
        "metrics": metrics,
        "feature_importance": {feat: float(imp) for feat, imp in importance},
        "training_note": "XGBoost binary classifier for trade profitability prediction",
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata saved: {meta_path}")

    return model_path, meta_path


def upload_to_gcs(model_path: str, meta_path: str, gcs_prefix: str):
    """Upload model files to Google Cloud Storage."""
    for local_path in [model_path, meta_path]:
        dest = gcs_prefix.rstrip("/") + "/" + os.path.basename(local_path)
        print(f"\n  Uploading {local_path} → {dest}")
        result = subprocess.run(
            ["gsutil", "cp", local_path, dest],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}")
            return False
        print(f"  Uploaded successfully")
    return True


def main():
    parser = argparse.ArgumentParser(description="Train Lazarus profitability model")
    parser.add_argument("--input", required=True, help="Path to features.csv")
    parser.add_argument("--output-dir", default=".", help="Directory to save model files")
    parser.add_argument("--upload-gcs", default="", help="GCS path to upload model (e.g., gs://bucket/prefix/)")
    parser.add_argument("--test-split", type=float, default=0.2, help="Test set fraction (default 0.2)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    # Load data
    X, y = load_csv(args.input)
    print(f"Loaded {len(X)} trades with {len(FEATURE_COLUMNS)} features")

    if len(X) < 30:
        print("WARNING: Very small dataset (<30 trades). Model may not generalize well.")

    # Stratified split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_split, random_state=42, stratify=y
    )

    # Train
    model, metrics, importance = train_model(X_train, y_train, X_test, y_test)

    # Save
    model_path, meta_path = save_model(model, metrics, importance, args.output_dir)

    # Upload to GCS if requested
    if args.upload_gcs:
        upload_to_gcs(model_path, meta_path, args.upload_gcs)

    print(f"\n{'='*60}")
    print(f"  Training complete. Model ready for integration.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
