#!/usr/bin/env python3
"""
Train gradient-boosted spread direction predictor.

Uses features built by build_features.py to train a LightGBM/XGBoost model
that predicts whether the spread will revert toward the mean.

Usage:
    python experiments/train_spread_model.py data/statarb/20260602_211358/features
    python experiments/train_spread_model.py features/ --target target_revert --model lightgbm
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.metrics import (
        accuracy_score, classification_report, f1_score,
        mean_absolute_error, mean_squared_error, roc_auc_score,
    )
    from sklearn.model_selection import TimeSeriesSplit
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

# Columns to exclude from features
NON_FEATURE_COLS = {
    "ts", "snapshot_idx", "p1", "p2", "bid1", "ask1", "bid2", "ask2",
    "vol1", "vol2", "spread", "target_revert", "target_spread_change",
    "target_narrowed",
}


def load_features(features_dir: str, pair_filter: str = None) -> dict[str, pd.DataFrame]:
    """Load all feature Parquet files from directory."""
    base = Path(features_dir)
    data = {}
    for f in sorted(base.glob("*.parquet")):
        if pair_filter and pair_filter not in f.stem:
            continue
        df = pd.read_parquet(f)
        data[f.stem] = df
    return data


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Get feature columns (exclude targets and metadata)."""
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def walk_forward_cv(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "target_revert",
    n_splits: int = 5,
    model_type: str = "sklearn",
) -> dict:
    """
    Walk-forward cross-validation for time series.
    """
    # Drop rows with NaN in target or any feature
    valid = df.dropna(subset=[target_col] + feature_cols).copy()
    if len(valid) < 100:
        return {"error": "Insufficient data", "rows": len(valid)}

    X = valid[feature_cols].values
    y = valid[target_col].values

    # Replace remaining NaN/inf in features
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    is_classification = target_col in ("target_revert", "target_narrowed")

    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_results = []

    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        if is_classification:
            if model_type == "lightgbm" and HAS_LGBM:
                model = lgb.LGBMClassifier(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    min_child_samples=20,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    verbose=-1,
                )
            else:
                model = GradientBoostingClassifier(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    min_samples_leaf=20,
                    subsample=0.8,
                )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None

            acc = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_prob) if y_prob is not None and len(np.unique(y_test)) > 1 else None

            fold_results.append({
                "fold": fold_idx,
                "train_size": len(X_train),
                "test_size": len(X_test),
                "accuracy": float(acc),
                "f1": float(f1),
                "auc": float(auc) if auc is not None else None,
                "baseline_acc": float(max(y_test.mean(), 1 - y_test.mean())),
            })
        else:
            if model_type == "lightgbm" and HAS_LGBM:
                model = lgb.LGBMRegressor(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    min_child_samples=20,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    verbose=-1,
                )
            else:
                model = GradientBoostingRegressor(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    min_samples_leaf=20,
                    subsample=0.8,
                )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            mae = mean_absolute_error(y_test, y_pred)
            rmse = mean_squared_error(y_test, y_pred, squared=False)
            # Directional accuracy
            dir_acc = ((y_pred > 0) == (y_test > 0)).mean()

            fold_results.append({
                "fold": fold_idx,
                "train_size": len(X_train),
                "test_size": len(X_test),
                "mae": float(mae),
                "rmse": float(rmse),
                "directional_accuracy": float(dir_acc),
            })

    # Get feature importance from last fold
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        fi = sorted(
            zip(feature_cols, importances),
            key=lambda x: x[1], reverse=True
        )
    else:
        fi = []

    return {
        "folds": fold_results,
        "feature_importance": [(name, float(imp)) for name, imp in fi[:20]],
        "n_features": len(feature_cols),
        "n_rows": len(valid),
        "target": target_col,
        "model_type": model_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Train spread prediction model")
    parser.add_argument("features_dir", help="Directory with feature Parquet files")
    parser.add_argument("--target", default="target_revert",
                        choices=["target_revert", "target_narrowed", "target_spread_change"],
                        help="Target variable")
    parser.add_argument("--model", default="sklearn",
                        choices=["sklearn", "lightgbm"],
                        help="Model backend")
    parser.add_argument("--folds", type=int, default=5,
                        help="Number of CV folds")
    parser.add_argument("--pair", type=str, default=None,
                        help="Filter to specific pair (substring match)")
    args = parser.parse_args()

    if not HAS_SKLEARN:
        print("ERROR: scikit-learn required. Install: pip install scikit-learn")
        sys.exit(1)
    if args.model == "lightgbm" and not HAS_LGBM:
        print("WARNING: LightGBM not installed. Falling back to sklearn.")
        args.model = "sklearn"

    print(f"=== Spread Prediction Model Training ===")
    print(f"  Features: {args.features_dir}")
    print(f"  Target: {args.target}")
    print(f"  Model: {args.model}")
    print(f"  CV folds: {args.folds}")
    print()

    # Load feature files
    data = load_features(args.features_dir, pair_filter=args.pair)
    if not data:
        print(f"ERROR: No Parquet files found in {args.features_dir}")
        sys.exit(1)

    print(f"  Loaded {len(data)} pair files")
    print()

    all_results = {}

    for pair_name, df in sorted(data.items()):
        feature_cols = get_feature_cols(df)
        if args.target not in df.columns:
            print(f"  {pair_name}: target '{args.target}' not found, skipping")
            continue

        print(f"  Training {pair_name} ({len(df)} rows, {len(feature_cols)} features)...")
        result = walk_forward_cv(
            df, feature_cols, target_col=args.target,
            n_splits=args.folds, model_type=args.model,
        )

        if "error" in result:
            print(f"    ERROR: {result['error']}")
            continue

        all_results[pair_name] = result

        # Print fold results
        is_classification = args.target in ("target_revert", "target_narrowed")
        if is_classification:
            accs = [f["accuracy"] for f in result["folds"]]
            aucs = [f["auc"] for f in result["folds"] if f["auc"] is not None]
            baselines = [f["baseline_acc"] for f in result["folds"]]
            print(f"    Accuracy: {np.mean(accs):.3f} ± {np.std(accs):.3f} (baseline: {np.mean(baselines):.3f})")
            if aucs:
                print(f"    AUC:      {np.mean(aucs):.3f} ± {np.std(aucs):.3f}")
            lift = np.mean(accs) - np.mean(baselines)
            print(f"    Lift over baseline: {lift:+.3f}")
        else:
            maes = [f["mae"] for f in result["folds"]]
            dir_accs = [f["directional_accuracy"] for f in result["folds"]]
            print(f"    MAE: {np.mean(maes):.3f} ± {np.std(maes):.3f}")
            print(f"    Directional accuracy: {np.mean(dir_accs):.3f}")

        # Top features
        if result["feature_importance"]:
            top5 = result["feature_importance"][:5]
            print(f"    Top features: {', '.join(f'{n}({v:.3f})' for n, v in top5)}")
        print()

    # Summary
    if all_results:
        print("=" * 70)
        print("=== SUMMARY ===")
        print()

        if is_classification:
            rows = []
            for name, r in sorted(all_results.items()):
                accs = [f["accuracy"] for f in r["folds"]]
                baselines = [f["baseline_acc"] for f in r["folds"]]
                aucs = [f["auc"] for f in r["folds"] if f["auc"] is not None]
                rows.append({
                    "pair": name,
                    "rows": r["n_rows"],
                    "acc": np.mean(accs),
                    "baseline": np.mean(baselines),
                    "lift": np.mean(accs) - np.mean(baselines),
                    "auc": np.mean(aucs) if aucs else None,
                    "top_feature": r["feature_importance"][0][0] if r["feature_importance"] else "N/A",
                })

            rows.sort(key=lambda x: x["lift"], reverse=True)
            print(f"  {'Pair':<35} {'Rows':>6} {'Acc':>6} {'Base':>6} {'Lift':>7} {'AUC':>6} Top Feature")
            print(f"  {'-'*35} {'---':>6} {'---':>6} {'---':>6} {'---':>7} {'---':>6} {'-'*20}")
            for r in rows:
                auc_str = f"{r['auc']:.3f}" if r['auc'] is not None else "N/A"
                print(f"  {r['pair']:<35} {r['rows']:>6} {r['acc']:.3f} {r['baseline']:.3f} {r['lift']:>+.3f} {auc_str:>6} {r['top_feature']}")

        # Save results
        output_path = os.path.join(args.features_dir, "model_results.json")
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
