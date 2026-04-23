from typing import Any, Dict, List
from app.models import Action, Reward


SEVERITY_WEIGHTS = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}

VALID_PATTERN_TYPES = {
    "data_exfiltration",
    "data_staging",
    "exfiltration",
    "staged_exfiltration",
    "unauthorized_data_transfer",
}


def check_severity_accuracy(action: Action, known_anomalies: List[Dict[str, Any]]) -> float:
    known_map = {a["log_index"]: a["severity"] for a in known_anomalies}
    if not known_map:
        return 1.0

    scores = []
    for anomaly in action.anomalies:
        if anomaly.log_index in known_map:
            expected = known_map[anomaly.log_index]
            actual = anomaly.severity
            if actual == expected:
                scores.append(1.0)
            else:
                expected_w = SEVERITY_WEIGHTS.get(expected, 0.5)
                actual_w = SEVERITY_WEIGHTS.get(actual, 0.5)
                distance = abs(expected_w - actual_w)
                scores.append(max(0.0, 1.0 - distance * 2))

    return sum(scores) / len(known_map) if scores else 0.0


def check_pattern_detection(action: Action, known_pattern: Dict[str, Any]) -> float:
    """Check if the action summary/descriptions mention the correct pattern type."""
    pattern_type = known_pattern["pattern_type"].lower()
    summary_lower = action.summary.lower()

    # Check if any valid pattern type keyword appears in summary or anomaly descriptions
    found_pattern = any(pt in summary_lower for pt in VALID_PATTERN_TYPES)
    if not found_pattern:
        for anomaly in action.anomalies:
            desc_lower = anomaly.description.lower()
            if any(pt in desc_lower for pt in VALID_PATTERN_TYPES):
                found_pattern = True
                break

    return 1.0 if found_pattern else 0.0


def generate_feedback(action: Action, task: Dict[str, Any]) -> str:
    known_anomalies = task["known_anomalies"]
    known_pattern = task.get("known_pattern", {})
    known_indices = {a["log_index"] for a in known_anomalies}
    detected_indices = {a.log_index for a in action.anomalies}

    missed = known_indices - detected_indices
    hallucinated = detected_indices - known_indices

    parts = []

    if not missed and not hallucinated:
        parts.append("All pattern-related anomalies correctly identified.")
    else:
        if missed:
            parts.append(
                f"Missed pattern logs at indices: {sorted(missed)}. "
                "Look for repeated writes to /tmp/.staging/ and the final exfiltration call."
            )
        if hallucinated:
            parts.append(f"False positives at log indices: {sorted(hallucinated)}.")

    # Pattern type feedback
    pattern_score = check_pattern_detection(action, known_pattern)
    if pattern_score < 1.0:
        parts.append(
            f"Pattern type not correctly identified. Expected: '{known_pattern.get('pattern_type', 'data_exfiltration')}'."
        )

    # Severity feedback
    known_map = {a["log_index"]: a["severity"] for a in known_anomalies}
    wrong_severity = []
    for anomaly in action.anomalies:
        if anomaly.log_index in known_map and anomaly.severity != known_map[anomaly.log_index]:
            wrong_severity.append(
                f"index {anomaly.log_index}: expected '{known_map[anomaly.log_index]}', got '{anomaly.severity}'"
            )
    if wrong_severity:
        parts.append(f"Severity mismatches: {'; '.join(wrong_severity)}.")

    return " ".join(parts) if parts else "Excellent pattern analysis."


def grade_task2(action: Action, task: Dict[str, Any]) -> Reward:
    known_anomalies = task["known_anomalies"]
    known_pattern = task.get("known_pattern", {})
    known_indices = {a["log_index"] for a in known_anomalies}

    detected_indices = {a.log_index for a in action.anomalies}

    # Precision
    tp = len(detected_indices & known_indices)
    precision = tp / len(detected_indices) if detected_indices else 0.0

    # Recall
    recall = tp / len(known_indices) if known_indices else 0.5

    # F1
    f1 = 2 * precision * recall / (precision + recall + 1e-9)

    # Severity accuracy
    severity_score = check_severity_accuracy(action, known_anomalies)

    # Pattern detection bonus/penalty
    pattern_score = check_pattern_detection(action, known_pattern)

    # Hallucination penalty
    hallucinated = len(detected_indices - known_indices)
    penalty = min(hallucinated * 0.1, 0.3)

    # Pattern type contributes to severity score component
    combined_quality = severity_score * 0.6 + pattern_score * 0.4

    raw = f1 * 0.7 + combined_quality * 0.3 - penalty
    score = max(0.001, min(0.999, raw))

    return Reward(
        score=round(score, 4),
        breakdown={
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "severity_score": round(severity_score, 3),
            "pattern_score": round(pattern_score, 3),
            "hallucinated": hallucinated,
            "penalty": round(penalty, 3),
        },
        feedback=generate_feedback(action, task),
    )
