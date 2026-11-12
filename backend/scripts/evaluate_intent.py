"""Model Evaluation Script for QueryMind AI 2.0 Intent Classification Engine.

Implements rigorous, leak-free Stratified Group-Aware Cross-Validation (StratifiedGroupKFold, K=3)
over 27 semantic template clusters across all 128 training queries.
"""

import sys
from collections import Counter
from typing import Dict, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    log_loss,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.preprocessing import label_binarize

# Path setup to import backend application services
sys.path.insert(0, r"c:\Users\OMEN\OneDrive\Desktop\STUDY\Projects\Nlp\QueryMind-AI\backend")
from app.services.intent_classifier import INTENT_CATEGORIES, TRAINING_DATA

# 27 semantic template groups across all 128 queries
GROUP_MAP: List[int] = [
    # AGGREGATE (indices 0..21) -> Groups 0..4
    0, 1, 2, 3, 4, 3, 0, 3, 4, 4, 1, 4, 2, 0, 3, 3, 1, 4, 3, 2, 3, 0,
    # RANKING (indices 22..41) -> Groups 5..8
    5, 6, 7, 5, 6, 8, 7, 8, 6, 5, 8, 8, 5, 6, 5, 8, 8, 7, 8, 6,
    # FILTER (indices 42..61) -> Groups 9..14
    9, 10, 11, 12, 13, 10, 13, 14, 14, 9, 11, 12, 13, 13, 14, 10, 13, 13, 12, 14,
    # COMPARISON (indices 62..75) -> Groups 15..17
    15, 16, 15, 16, 17, 16, 17, 15, 16, 17, 17, 17, 17, 15,
    # TREND (indices 76..93) -> Groups 18..20
    18, 19, 20, 19, 19, 18, 19, 18, 20, 18, 19, 18, 20, 19, 18, 19, 18, 19,
    # GENERAL_QUERY (indices 94..112) -> Groups 21..23
    21, 22, 22, 21, 23, 21, 22, 22, 23, 21, 22, 23, 23, 22, 21, 21, 22, 21, 23,
    # WHAT_IF (indices 113..127) -> Groups 24..26
    24, 25, 25, 24, 26, 25, 25, 24, 26, 24, 25, 25, 24, 24, 24,
]


def verify_group_invariants(texts: List[str], labels: List[str], group_map: List[int]) -> None:
    """Automated assertions validating group integrity, single-intent mapping, and coverage."""
    assert len(texts) == len(labels) == len(group_map) == 128, (
        f"Dataset size mismatch: texts={len(texts)}, labels={len(labels)}, group_map={len(group_map)}"
    )

    # 1. Group to intent mapping must be 1-to-1 (each group belongs to exactly one intent)
    group_to_intent: Dict[int, str] = {}
    for i, (text, label) in enumerate(zip(texts, labels)):
        grp = group_map[i]
        if grp not in group_to_intent:
            group_to_intent[grp] = label
        else:
            assert group_to_intent[grp] == label, (
                f"Group integrity violation: Group {grp} spans multiple intents ({group_to_intent[grp]} vs {label})"
            )

    assert len(group_to_intent) == 27, f"Expected exactly 27 groups, got {len(group_to_intent)}"
    assert set(group_to_intent.values()) == set(INTENT_CATEGORIES), "All 7 intent categories must be covered"
    print("✓ Automated Assertion Passed: Group assignments are consistent, non-overlapping across intents, and total 27.")


def run_group_aware_evaluation(texts: List[str], labels: List[str], group_map: List[int]) -> Dict:
    """Executes 3-Fold StratifiedGroupKFold with zero vectorizer and template leakage."""
    classes = sorted(list(set(labels)))
    sgkf = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)

    oof_preds = [None] * len(texts)
    oof_probas = np.zeros((len(texts), len(classes)))

    print("\n" + "=" * 70)
    print("1. PRIMARY: GROUP-AWARE STRATIFIED 3-FOLD CROSS-VALIDATION")
    print("   (Zero Vectorizer Leakage: TF-IDF fit strictly per training fold)")
    print("=" * 70)

    for fold, (train_idx, val_idx) in enumerate(sgkf.split(texts, labels, groups=group_map)):
        train_groups = set(group_map[i] for i in train_idx)
        val_groups = set(group_map[i] for i in val_idx)

        # Automated Assertion: Strict Group Disjointness
        assert train_groups.isdisjoint(val_groups), (
            f"Fold {fold+1} group leakage detected! Overlapping groups: {train_groups & val_groups}"
        )

        X_train_raw = [texts[i] for i in train_idx]
        y_train = [labels[i] for i in train_idx]
        X_val_raw = [texts[i] for i in val_idx]
        y_val = [labels[i] for i in val_idx]

        # Automated Assertion: Class Completeness in Validation Fold
        assert len(set(y_val)) == 7, (
            f"Fold {fold+1} missing classes: {set(labels) - set(y_val)}"
        )

        # Fit vectorizer ONLY on training fold
        vec = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            lowercase=True,
            token_pattern=r"\b\w+\b",
        )
        X_train = vec.fit_transform(X_train_raw)
        X_val = vec.transform(X_val_raw)

        model = LogisticRegression(solver="lbfgs", max_iter=1000, random_state=42, C=5.0)
        model.fit(X_train, y_train)

        preds = model.predict(X_val)
        probas = model.predict_proba(X_val)

        # Class alignment
        class_indices = [classes.index(c) for c in model.classes_]
        for idx_in_val, orig_idx in enumerate(val_idx):
            oof_preds[orig_idx] = preds[idx_in_val]
            for prob_col, class_idx in enumerate(class_indices):
                oof_probas[orig_idx, class_idx] = probas[idx_in_val, prob_col]

        fold_acc = accuracy_score(y_val, preds)
        print(f"Fold {fold+1}: Train samples={len(train_idx)}, Val samples={len(val_idx)}, "
              f"Val groups={len(val_groups)}, Val classes={len(set(y_val))}, Val accuracy={fold_acc:.4f}")

    print("✓ Automated Assertion Passed: All 3 folds strictly disjoint with all 7 classes represented.")

    acc = accuracy_score(labels, oof_preds)
    print(f"\nOverall Group-Aware Out-of-Fold Accuracy: {acc:.4f} ({acc*100:.2f}%)")
    print("\nGroup-Aware Classification Report (Out-of-Fold):")
    print(classification_report(labels, oof_preds, target_names=classes, digits=4))

    print("Group-Aware Confusion Matrix (Classes: " + ", ".join(classes) + "):")
    cm = confusion_matrix(labels, oof_preds, labels=classes)
    print(cm)

    eps = 1e-15
    oof_probas_clipped = np.clip(oof_probas, eps, 1 - eps)
    oof_probas_clipped /= oof_probas_clipped.sum(axis=1, keepdims=True)
    ll = log_loss(labels, oof_probas_clipped, labels=classes)
    print(f"\nGroup-Aware Out-of-Fold Multi-Class Log Loss: {ll:.4f}")

    Y_bin = label_binarize(labels, classes=classes)
    brier_scores = [brier_score_loss(Y_bin[:, i], oof_probas[:, i]) for i in range(len(classes))]
    mean_brier = float(np.mean(brier_scores))
    per_class_brier = dict(zip(classes, [round(float(b), 4) for b in brier_scores]))
    print(f"Group-Aware Per-Class Brier Scores: {per_class_brier}")
    print(f"Group-Aware Mean Multi-Class Brier Score: {mean_brier:.4f}")

    return {
        "accuracy": acc,
        "log_loss": ll,
        "mean_brier": mean_brier,
        "per_class_brier": per_class_brier,
        "confusion_matrix": cm,
    }


def run_historical_comparisons(texts: List[str], labels: List[str]) -> None:
    """Documents and reproduces the two historical 5-fold StratifiedKFold configurations."""
    classes = sorted(list(set(labels)))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print("\n" + "=" * 70)
    print("2. HISTORICAL COMPARISON A: PER-FOLD TF-IDF + STRATIFIED 5-FOLD CV")
    print("   (Standard SKF with fold-isolated vectorizer, but template leakage)")
    print("=" * 70)

    oof_preds_a = [None] * len(texts)
    oof_probas_a = np.zeros((len(texts), len(classes)))

    for train_idx, val_idx in skf.split(texts, labels):
        X_train_raw = [texts[i] for i in train_idx]
        y_train = [labels[i] for i in train_idx]
        X_val_raw = [texts[i] for i in val_idx]
        y_val = [labels[i] for i in val_idx]

        vec = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            lowercase=True,
            token_pattern=r"\b\w+\b",
        )
        X_train = vec.fit_transform(X_train_raw)
        X_val = vec.transform(X_val_raw)

        model = LogisticRegression(solver="lbfgs", max_iter=1000, random_state=42, C=5.0)
        model.fit(X_train, y_train)

        preds = model.predict(X_val)
        probas = model.predict_proba(X_val)
        class_indices = [classes.index(c) for c in model.classes_]

        for idx_in_val, orig_idx in enumerate(val_idx):
            oof_preds_a[orig_idx] = preds[idx_in_val]
            for prob_col, class_idx in enumerate(class_indices):
                oof_probas_a[orig_idx, class_idx] = probas[idx_in_val, prob_col]

    acc_a = accuracy_score(labels, oof_preds_a)
    ll_a = log_loss(labels, oof_probas_a, labels=classes)
    Y_bin = label_binarize(labels, classes=classes)
    brier_a = float(np.mean([brier_score_loss(Y_bin[:, i], oof_probas_a[:, i]) for i in range(len(classes))]))
    print(f"Historical A (Per-Fold TF-IDF) Accuracy : {acc_a:.4f} ({acc_a*100:.2f}%)")
    print(f"Historical A Multi-Class Log Loss       : {ll_a:.4f}")
    print(f"Historical A Mean Multi-Class Brier     : {brier_a:.4f}")

    print("\n" + "=" * 70)
    print("3. HISTORICAL COMPARISON B: GLOBAL PRE-FIT TF-IDF + STRATIFIED 5-FOLD CV")
    print("   (Earlier script audit_intent.py using pre-vectorized matrix X)")
    print("=" * 70)
    vec_global = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
        token_pattern=r"\b\w+\b",
    )
    X_global = vec_global.fit_transform(texts)
    oof_preds_b = [None] * len(texts)
    oof_probas_b = np.zeros((len(texts), len(classes)))

    for train_idx, val_idx in skf.split(X_global, labels):
        X_train = X_global[train_idx]
        y_train = [labels[i] for i in train_idx]
        X_val = X_global[val_idx]

        model = LogisticRegression(solver="lbfgs", max_iter=1000, random_state=42, C=5.0)
        model.fit(X_train, y_train)

        preds = model.predict(X_val)
        probas = model.predict_proba(X_val)
        class_indices = [classes.index(c) for c in model.classes_]

        for idx_in_val, orig_idx in enumerate(val_idx):
            oof_preds_b[orig_idx] = preds[idx_in_val]
            for prob_col, class_idx in enumerate(class_indices):
                oof_probas_b[orig_idx, class_idx] = probas[idx_in_val, prob_col]

    acc_b = accuracy_score(labels, oof_preds_b)
    ll_b = log_loss(labels, oof_probas_b, labels=classes)
    brier_b = float(np.mean([brier_score_loss(Y_bin[:, i], oof_probas_b[:, i]) for i in range(len(classes))]))
    print(f"Historical B (Global Pre-Fit TF-IDF) Accuracy : {acc_b:.4f} ({acc_b*100:.2f}%)")
    print(f"Historical B Multi-Class Log Loss             : {ll_b:.4f}")
    print(f"Historical B Mean Multi-Class Brier           : {brier_b:.4f}")


def main() -> None:
    texts = [t[0] for t in TRAINING_DATA]
    labels = [t[1] for t in TRAINING_DATA]

    verify_group_invariants(texts, labels, GROUP_MAP)
    run_group_aware_evaluation(texts, labels, GROUP_MAP)
    run_historical_comparisons(texts, labels)


if __name__ == "__main__":
    main()

