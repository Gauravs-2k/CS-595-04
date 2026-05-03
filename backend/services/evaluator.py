import re
from dataclasses import dataclass


_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "were", "was",
    "are", "not", "but", "have", "has", "had", "been", "patient", "summary",
    "discharge", "history", "care", "plan", "list", "include", "includes", "no",
}

_GT_CATEGORY_MAP = {
    "medication": "medication",
    "diagnosis": "diagnosis",
    "follow-up": "follow-up",
    "lab": "lab",
    "instruction": "instruction",
}


@dataclass
class EvalItem:
    category: str
    text: str


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return {tok for tok in raw if len(tok) > 2 and tok not in _STOP}


def _jaccard(a: str, b: str) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _pred_category(gap: dict) -> str:
    title = (gap.get("title") or "").lower()
    category = (gap.get("category") or "").lower()
    if "medication" in title or "regimen" in title:
        return "medication"
    if "diagnosis" in title or "problem" in title:
        return "diagnosis"
    if "lab" in title or "result" in title or "pending" in title:
        return "lab"
    if "referral" in title or "follow-up" in title or "follow up" in title:
        return "follow-up"
    if category == "changed":
        return "medication"
    if category == "action_needed":
        return "follow-up"
    return "instruction"


def _to_pred_item(gap: dict) -> EvalItem:
    blob = " ".join(
        [
            str(gap.get("title") or ""),
            str(gap.get("description") or ""),
            str(gap.get("source_text") or ""),
        ]
    )
    return EvalItem(category=_pred_category(gap), text=blob)


def _to_gt_item(item: dict) -> EvalItem:
    cat = _GT_CATEGORY_MAP.get((item.get("category") or "").lower(), "instruction")
    blob = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("evidence_in_summary") or ""),
            str(item.get("suggested_correction") or ""),
        ]
    )
    return EvalItem(category=cat, text=blob)


def score_detected_vs_ground_truth(detected_gaps: list[dict], ground_truth: list[dict]) -> dict:
    pred = [_to_pred_item(g) for g in detected_gaps]
    gt = [_to_gt_item(g) for g in ground_truth]

    used_pred: set[int] = set()
    tp = 0

    for gt_item in gt:
        best_idx = None
        best_sim = 0.0
        for idx, pred_item in enumerate(pred):
            if idx in used_pred:
                continue
            if pred_item.category != gt_item.category:
                continue
            sim = _jaccard(pred_item.text, gt_item.text)
            if sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx is not None and best_sim >= 0.2:
            used_pred.add(best_idx)
            tp += 1

    fp = max(0, len(pred) - tp)
    fn = max(0, len(gt) - tp)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0

    return {
        "counts": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "predicted_total": len(pred),
            "ground_truth_total": len(gt),
        },
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
    }
