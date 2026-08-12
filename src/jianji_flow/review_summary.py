from __future__ import annotations


def build_review_summary(review: dict) -> dict:
    status = review.get("status")
    failures = list(review.get("failures", []))
    warnings = list(review.get("warnings", []))
    if status == "pass":
        return {
            "decision": "Usable rough cut",
            "reason": "All required artifacts passed automated checks.",
            "next_action": "Watch captions, product accuracy, and segment choices before publishing.",
        }
    if status == "warning":
        reason = warnings[0] if warnings else "Some segments need manual review."
        return {
            "decision": "Needs review",
            "reason": reason,
            "next_action": "Open the contact sheet and check low confidence segments before using the video.",
        }
    reason = failures[0] if failures else "The run did not pass required checks."
    return {
        "decision": "Do not use yet",
        "reason": reason,
        "next_action": "Fix the reported material or setup problem, then rerun quick.",
    }
