from typing import Any, Dict, List
from app.models import Action, Reward


SEVERITY_WEIGHTS = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}

VALID_STRATEGIES = {
    "cleanup_disguise",
    "cleanup",
    "disguise",
    "cover_tracks",
    "log_tampering",
    "disguised_operations",
    "cleanup_and_disguise",
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


def check_strategy_detection(action: Action, known_adversarial: Dict[str, Any]) -> float:
    """Check if the cleanup/disguise strategy was identified."""
    strategy = known_adversarial.get("strategy", "").lower()
    summary_lower = action.summary.lower()

    found = any(s in summary_lower for s in VALID_STRATEGIES)
    if not found:
        for anomaly in action.anomalies:
            desc_lower = anomaly.description.lower()
            if any(s in desc_lower for s in VALID_STRATEGIES):
                found = True
                break
    # Also accept "disguised" or "cleanup" keywords
    if not found:
        keywords = ["disguised", "cleanup", "cover", "tamper", "fake", "mask", "hidden"]
        found = any(kw in summary_lower for kw in keywords)

    return 1.0 if found else 0.0


def check_agent_identified(action: Action, known_adversarial: Dict[str, Any]) -> float:
    """Check if the correct adversarial agent was identified."""
    target_agent = known_adversarial.get("agent_id", "agent_Z")
    detected_agents = {a.agent_id for a in action.anomalies}
    return 1.0 if target_agent in detected_agents else 0.0


def generate_feedback(action: Action, task: Dict[str, Any]) -> str:
    known_anomalies = task["known_anomalies"]
    known_adversarial = task.get("known_adversarial", {})
    known_indices = {a["log_index"] for a in known_anomalies}
    detected_indices = {a.log_index for a in action.anomalies}

    missed = known_indices - detected_indices
    hallucinated = detected_indices - known_indices

    parts = []

    agent_score = check_agent_identified(action, known_adversarial)
    if agent_score < 1.0:
        parts.append(
            f"Adversarial agent '{known_adversarial.get('agent_id')}' not correctly identified."
        )

    strategy_score = check_strategy_detection(action, known_adversarial)
    if strategy_score < 1.0:
        parts.append(
            "Disguise strategy not identified. Look for cleanup actions following each violation "
            "and metadata fields like 'disguised: true' or 'actual_destination'."
        )

    if not missed and not hallucinated:
        parts.append("All actual violations correctly exposed.")
    else:
        if missed:
            parts.append(
                f"Missed violations at indices: {sorted(missed)}. "
                "Examine metadata carefully — authorized=True can be spoofed."
            )
        if hallucinated:
            parts.append(f"False positives at indices: {sorted(hallucinated)}.")

    known_map = {a["log_index"]: a["severity"] for a in known_anomalies}
    wrong_severity = []
    for anomaly in action.anomalies:
        if anomaly.log_index in known_map and anomaly.severity != known_map[anomaly.log_index]:
            wrong_severity.append(
                f"index {anomaly.log_index}: expected '{known_map[anomaly.log_index]}', got '{anomaly.severity}'"
            )
    if wrong_severity:
        parts.append(f"Severity mismatches: {'; '.join(wrong_severity)}.")

    return " ".join(parts) if parts else "Outstanding adversarial detection."


def grade_task3(action: Action, task: Dict[str, Any]) -> Reward:
    known_anomalies = task["known_anomalies"]
    known_adversarial = task.get("known_adversarial", {})
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

    # Strategy detection
    strategy_score = check_strategy_detection(action, known_adversarial)

    # Agent identification
    agent_score = check_agent_identified(action, known_adversarial)

    # Hallucination penalty
    hallucinated = len(detected_indices - known_indices)
    penalty = min(hallucinated * 0.1, 0.3)

    # Combined quality: severity + strategy + agent identification
    combined_quality = severity_score * 0.4 + strategy_score * 0.3 + agent_score * 0.3

    raw = f1 * 0.7 + combined_quality * 0.3 - penalty
    score = max(0.001, min(0.999, raw))

    return Reward(
        score=round(score, 4),
        breakdown={
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "severity_score": round(severity_score, 3),
            "strategy_score": round(strategy_score, 3),
            "agent_score": round(agent_score, 3),
            "hallucinated": hallucinated,
            "penalty": round(penalty, 3),
        },
        feedback=generate_feedback(action, task),
    )
