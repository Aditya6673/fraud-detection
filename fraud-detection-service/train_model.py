"""
Model training script for fraud detection service.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Tuple, Dict  # Added missing type imports

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# Removed sys.path hack. Using absolute imports from the root.
from app.model.processor import TransactionFeatureProcessor
from app.model.loader import FraudDetectionModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_and_preprocess_data(data_path: str) -> Tuple:
    """
    Load and preprocess the creditcard.csv dataset.
    """
    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

    feature_cols = [f"V{i}" for i in range(1, 29)] + ["Time", "Amount"]
    X = df[feature_cols].values
    y = df["Class"].values

    logger.info(f"Loaded dataset: {X.shape[0]} samples, {X.shape[1]} features")
    logger.info(f"Class distribution: {np.bincount(y)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"Training set: {X_train.shape[0]} samples, Test set: {X_test.shape[0]} samples")

    # Handle class imbalance with SMOTE
    logger.info("Applying SMOTE to handle class imbalance...")
    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

    logger.info(f"After SMOTE: {X_train_resampled.shape[0]} samples")

    # Scale features
    logger.info("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_resampled)
    X_test_scaled = scaler.transform(X_test)

    # Create and fit feature processor
    feature_processor = TransactionFeatureProcessor()
    feature_processor.fit(X_train_scaled)

    return (
        X_train_scaled,
        X_test_scaled,
        y_train_resampled,
        y_test,
        feature_processor,
        scaler,
    )


def train_model(
        X_train: np.ndarray,
        y_train: np.ndarray,
        model_type: str = "random_forest",
) -> Tuple[Any, Dict]:
    """
    Train a fraud detection model.
    """
    logger.info(f"Training {model_type} model...")

    # Note: Removed class_weight="balanced" and scale_pos_weight because
    # SMOTE has already perfectly balanced the y_train dataset.
    if model_type == "logistic_regression":
        model = LogisticRegression(
            random_state=42,
            max_iter=1000,
            n_jobs=-1,
        )
    elif model_type == "random_forest":
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
        )
    elif model_type == "xgboost":
        model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            n_jobs=-1,
            eval_metric="logloss",
        )
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    model.fit(X_train, y_train)

    y_pred = model.predict(X_train)
    train_report = classification_report(y_train, y_pred, output_dict=True)

    logger.info(f"Training accuracy: {train_report['accuracy']:.4f}")
    logger.info(f"Training precision (fraud): {train_report['1']['precision']:.4f}")
    logger.info(f"Training recall (fraud): {train_report['1']['recall']:.4f}")
    logger.info(f"Training F1 (fraud): {train_report['1']['f1-score']:.4f}")

    metadata = {
        "model_type": model.__class__.__name__,
        "training_samples": int(X_train.shape[0]),
        "feature_count": int(X_train.shape[1]),
        "training_accuracy": float(train_report["accuracy"]),
        "training_precision": float(train_report["1"]["precision"]),
        "training_recall": float(train_report["1"]["recall"]),
        "training_f1": float(train_report["1"]["f1-score"]),
        "training_date": pd.Timestamp.now().isoformat(),
    }

    return model, metadata


def evaluate_model(
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
) -> dict:
    """
    Evaluate the trained model on test data.
    """
    logger.info("Evaluating model on test set...")

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True)
    cm = confusion_matrix(y_test, y_pred)

    logger.info(f"Test accuracy: {report['accuracy']:.4f}")
    logger.info(f"Test precision (fraud): {report['1']['precision']:.4f}")
    logger.info(f"Test recall (fraud): {report['1']['recall']:.4f}")
    logger.info(f"Test F1 (fraud): {report['1']['f1-score']:.4f}")
    logger.info(f"Confusion matrix:\n{cm}")

    report["confusion_matrix"] = cm.tolist()

    return report


def save_artifacts(
        model: Any,
        feature_processor: TransactionFeatureProcessor,
        scaler: StandardScaler,
        metadata: dict,
        model_dir: str,
        version: str = None,
) -> str:
    """
    Save model and preprocessing artifacts.
    """
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    model_file = model_path / f"model_v{version}.joblib" if version else model_path / "model_latest.joblib"
    joblib.dump(model, model_file)
    logger.info(f"Saved model to {model_file}")

    scaler_file = model_path / f"scaler_v{version}.joblib" if version else model_path / "scaler_latest.joblib"
    joblib.dump(scaler, scaler_file)
    logger.info(f"Saved scaler to {scaler_file}")

    processor_file = model_path / f"processor_v{version}.joblib" if version else model_path / "processor_latest.joblib"
    joblib.dump(feature_processor, processor_file)
    logger.info(f"Saved feature processor to {processor_file}")

    metadata_file = model_path / f"metadata_v{version}.joblib" if version else model_path / "metadata_latest.joblib"
    joblib.dump(metadata, metadata_file)
    logger.info(f"Saved metadata to {metadata_file}")

    if version is None:
        import re
        version_match = re.search(r"model_v(.+)\.joblib", str(model_file))
        version = version_match.group(1) if version_match else "1.0.0"

    return version


def main():
    parser = argparse.ArgumentParser(description="Train fraud detection model")
    parser.add_argument("--data", type=str, default="../creditcard.csv")
    parser.add_argument("--model-dir", type=str, default="./models")
    parser.add_argument("--model-type", type=str, default="random_forest", choices=["logistic_regression", "random_forest", "xgboost"])
    parser.add_argument("--version", type=str, default=None)

    args = parser.parse_args()

    try:
        X_train, X_test, y_train, y_test, feature_processor, scaler = load_and_preprocess_data(args.data)
        model, train_metadata = train_model(X_train, y_train, model_type=args.model_type)
        test_metadata = evaluate_model(model, X_test, y_test)

        metadata = {
            **train_metadata,
            **{f"test_{k}": v for k, v in test_metadata.items()},
            "model_type": args.model_type,
        }

        version = save_artifacts(
            model=model,
            feature_processor=feature_processor,
            scaler=scaler,
            metadata=metadata,
            model_dir=args.model_dir,
            version=args.version,
        )

        logger.info(f"Training completed successfully! Model version: {version}")

        # Fixed KeyError crash by accessing the '1' class dict
        print("\n" + "=" * 50)
        print("TRAINING SUMMARY")
        print("=" * 50)
        print(f"Model Type: {args.model_type}")
        print(f"Version: {version}")
        print(f"Training Samples: {train_metadata['training_samples']}")
        print(f"Test Accuracy: {test_metadata['accuracy']:.4f}")
        print(f"Test Precision: {test_metadata['1']['precision']:.4f}")
        print(f"Test Recall: {test_metadata['1']['recall']:.4f}")
        print(f"Test F1: {test_metadata['1']['f1-score']:.4f}")
        print(f"Model saved to: {args.model_dir}")
        print("=" * 50)

    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()