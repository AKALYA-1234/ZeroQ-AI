"""Model-evaluation pipeline: metric correctness, leakage-safe splits, dataset versioning."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.intelligence.evaluation import (
    classification_report, calibration_report, grouped_template_folds, dataset_fingerprint,
    normalize_template,
)


def test_classification_report_matches_hand_computation():
    y_true = ["A", "A", "A", "B", "B", "C"]
    y_pred = ["A", "A", "B", "B", "C", "C"]
    r = classification_report(y_true, y_pred, labels=["A", "B", "C"])
    assert r["accuracy"] == round(4 / 6, 4)
    a = r["per_class"]["A"]
    assert (a["precision"], a["recall"], a["support"]) == (1.0, round(2 / 3, 4), 3)
    b = r["per_class"]["B"]
    assert (b["precision"], b["recall"]) == (0.5, 0.5)
    # false-positive rate for B: predicted B on 1 of the 4 non-B items
    assert b["false_positive_rate"] == 0.25
    assert b["false_negative_rate"] == 0.5
    assert r["confusion_matrix"]["matrix"] == [[2, 1, 0], [0, 1, 1], [0, 0, 1]]
    assert 0 < r["macro_f1"] < 1


def test_calibration_report_perfect_and_overconfident():
    perfect = calibration_report([1.0, 1.0, 0.0, 0.0], [True, True, False, False])
    assert perfect["ece"] == 0.0
    over = calibration_report([0.9] * 10, [True] * 5 + [False] * 5)
    assert abs(over["ece"] - 0.4) < 1e-6
    assert over["brier"] > perfect["brier"]


def test_selective_accuracy_reports_coverage():
    r = calibration_report([0.9, 0.8, 0.3, 0.2], [True, True, False, True], threshold=0.5)
    assert r["selective"]["coverage"] == 0.5
    assert r["selective"]["accuracy"] == 1.0


def test_grouped_folds_never_share_a_template_between_train_and_test():
    rows = [("Pack seal was found partially open after receipt.", "Poor Sealing")] * 30 + \
           [("PACK SEAL WAS FOUND PARTIALLY OPEN AFTER RECEIPT!", "Poor Sealing")] + \
           [(f"template {i} text", f"L{i % 4}") for i in range(12)]
    folds = grouped_template_folds(rows, n_folds=4)
    assert len(folds) == 4
    for train_idx, test_idx in folds:
        train_t = {normalize_template(rows[i][0]) for i in train_idx}
        test_t = {normalize_template(rows[i][0]) for i in test_idx}
        assert not train_t & test_t
    covered = sorted(i for _, test in folds for i in test)
    assert covered == list(range(len(rows)))


def test_dataset_fingerprint_is_order_independent_and_label_sensitive():
    a = [("x", "A", "seed"), ("y", "B", "historical")]
    assert dataset_fingerprint(a) == dataset_fingerprint(list(reversed(a)))
    assert dataset_fingerprint(a) != dataset_fingerprint([("x", "B", "seed"), ("y", "B", "historical")])


def test_fit_temperature_sharpens_underconfident_scores():
    import numpy as np
    from app.intelligence.evaluation import fit_temperature, softmax
    rng = np.random.default_rng(0)
    scores, labels = [], []
    for _ in range(200):
        true = int(rng.integers(0, 4))
        s = rng.normal(0, 0.1, 4)
        s[true] += 0.8          # always right, but small margins → underconfident at T=1
        scores.append(s); labels.append(true)
    t = fit_temperature(np.array(scores), np.array(labels))
    assert t < 0.5
    p1 = softmax(np.array(scores) / 1.0).max(axis=1).mean()
    pt = softmax(np.array(scores) / t).max(axis=1).mean()
    assert pt > p1


def test_temperature_changes_confidence_but_never_the_decision():
    import numpy as np
    from app.intelligence.classifier import decide
    classes = ["Poor Sealing", "Leakage", "Insect Presence"]   # Packaging, Packaging, Infestation
    scores = np.array([1.0, 1.0, 1.5])
    base = decide(classes, scores, temperature=1.0)
    sharp = decide(classes, scores, temperature=0.3)
    # At T=1 Packaging's two subcategories outweigh Infestation; naive sharpening would flip it.
    assert base["category"] == "Packaging Defect"
    assert (sharp["category"], sharp["subcategory"]) == (base["category"], base["subcategory"])
    assert sharp["category_confidence"] != base["category_confidence"]


def test_wilson_interval_known_values_and_small_sample_width():
    from app.intelligence.evaluation import wilson_interval
    assert wilson_interval(0, 0) is None
    lo, hi = wilson_interval(8, 10)               # 80% of 10: textbook Wilson ≈ [49.0, 94.3]
    assert abs(lo - 49.0) < 0.2 and abs(hi - 94.3) < 0.2
    lo2, hi2 = wilson_interval(80, 100)           # same rate, 10x the data → much tighter
    assert (hi2 - lo2) < (hi - lo) / 2
    assert wilson_interval(10, 10)[1] == 100.0 and wilson_interval(0, 10)[0] == 0.0
