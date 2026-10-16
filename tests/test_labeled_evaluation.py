"""
Evaluates the ExchangeWatch AI pipeline against the 35-sample labeled dataset.
Verifies category classification accuracy, publication policy adherence,
and false positive / false negative rates.
"""

import pytest
from tests.fixtures.labeled_dataset import LABELED_FILINGS
from app.ai.importance import compute_importance
from app.ai.taxonomy import classify_to_taxonomy, CATEGORY_DEFAULT_PRIORITY


def test_labeled_dataset_category_classification_metrics():
    """
    Computes category classification accuracy across all 35 labeled filings.
    Reports per-category breakdown and overall accuracy.
    """
    correct = 0
    total = len(LABELED_FILINGS)
    mismatches = []

    for item in LABELED_FILINGS:
        release = {
            "title": item["title"],
            "category": item["category"],
            "exchange": "NSE",
        }
        computed = compute_importance(
            release=release,
            content_text=item["content"]
        )
        predicted = computed["event_type"]
        expected = item["expected_category"]

        if predicted == expected:
            correct += 1
        else:
            mismatches.append({
                "id": item["id"],
                "title": item["title"],
                "expected": expected,
                "predicted": predicted,
            })

    accuracy = (correct / total) * 100
    print(f"\n[EVALUATION] Classification Accuracy: {correct}/{total} ({accuracy:.1f}%)")
    if mismatches:
        for m in mismatches:
            print(f"  Mismatch in {m['id']}: expected {m['expected']} got {m['predicted']}")

    assert accuracy >= 95.0, f"Classification accuracy below 95%: {accuracy:.1f}%"


def test_labeled_dataset_publication_policy_and_falses():
    """
    Tests publication policy against expected decisions:
    - True Positives (TP): Important events correctly published
    - True Negatives (TN): Routine / non-material events correctly suppressed
    - False Positives (FP): Routine events incorrectly published to Telegram
    - False Negatives (FN): Important events incorrectly suppressed from Telegram
    """
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    fp_items = []
    fn_items = []

    for item in LABELED_FILINGS:
        release = {
            "title": item["title"],
            "category": item["category"],
            "exchange": "NSE",
        }
        computed = compute_importance(
            release=release,
            content_text=item["content"]
        )
        actual_publish = computed["should_publish"]
        expected_publish = item["expected_publish"]

        if expected_publish and actual_publish:
            tp += 1
        elif not expected_publish and not actual_publish:
            tn += 1
        elif not expected_publish and actual_publish:
            fp += 1
            fp_items.append(item["id"])
        elif expected_publish and not actual_publish:
            fn += 1
            fn_items.append(item["id"])

    total = len(LABELED_FILINGS)
    precision = (tp / (tp + fp)) * 100 if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) * 100 if (tp + fn) else 0.0
    specificity = (tn / (tn + fp)) * 100 if (tn + fp) else 0.0

    print(f"\n[PUBLICATION METRICS]")
    print(f"  Total items: {total}")
    print(f"  True Positives (TP): {tp}")
    print(f"  True Negatives (TN): {tn}")
    print(f"  False Positives (FP): {fp} ({fp_items})")
    print(f"  False Negatives (FN): {fn} ({fn_items})")
    print(f"  Precision: {precision:.1f}%")
    print(f"  Recall (Sensitivity): {recall:.1f}%")
    print(f"  Specificity: {specificity:.1f}%")

    # Strict guards: zero false positives (no spam to Telegram) and zero false negatives on critical items
    assert fp == 0, f"False positives detected: {fp_items}"
    assert fn == 0, f"False negatives detected: {fn_items}"
    assert precision == 100.0
    assert recall == 100.0


def test_routine_filings_all_suppressed():
    """All routine low-priority filings MUST have should_publish=False and priority=LOW."""
    routine_filings = [f for f in LABELED_FILINGS if f["expected_category"] == "ROUTINE_LOW_PRIORITY"]
    assert len(routine_filings) >= 14

    for item in routine_filings:
        release = {
            "title": item["title"],
            "category": item["category"],
            "exchange": "BSE",
        }
        computed = compute_importance(release=release, content_text=item["content"])
        assert computed["should_publish"] is False, f"Routine filing {item['id']} was not suppressed"
        assert computed["priority"] == "LOW", f"Routine filing {item['id']} had non-LOW priority: {computed['priority']}"
        assert computed["event_type"] == "ROUTINE_LOW_PRIORITY"
        assert computed["importance_score"] < 40


def test_critical_filings_all_published():
    """All CRITICAL filings MUST have should_publish=True and importance_score >= 75."""
    critical_filings = [f for f in LABELED_FILINGS if f["expected_priority"] == "CRITICAL"]
    assert len(critical_filings) >= 8

    for item in critical_filings:
        release = {
            "title": item["title"],
            "category": item["category"],
            "exchange": "NSE",
        }
        computed = compute_importance(release=release, content_text=item["content"])
        assert computed["should_publish"] is True, f"Critical filing {item['id']} was not published"
        assert computed["importance_score"] >= 75, f"Critical score too low for {item['id']}: {computed['importance_score']}"
