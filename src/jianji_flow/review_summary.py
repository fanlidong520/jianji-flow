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
        reason = _primary_warning(warnings)
        if "preflight skipped" in reason:
            next_action = "Fix source preflight or inspect source diagnostics before using; automated source-frame checks did not complete."
        elif "same source video" in reason or "voiceover shell" in reason:
            next_action = "Open remix.mp4 and compare it with the original before using; add more distinct assets if it still feels unchanged."
        elif "Story support is weak" in reason:
            story_next_action = review.get("story_support", {}).get("next_action")
            if story_next_action:
                next_action = str(story_next_action)
            elif "talking-head story" in reason:
                next_action = "Open the contact sheet and confirm the talking-head story has clear topic, claim, explanation, evidence, and conclusion before using the video."
            else:
                next_action = "Open the contact sheet and confirm the product story has a clear hook, pain, feature, evidence, and CTA before using the video."
        elif "filename only" in reason:
            next_action = "Open the contact sheet and confirm each role-labeled clip visually matches its caption before using the video."
        elif "platform UI" in reason or "original subtitles" in reason:
            next_action = "Check the warned segments for old subtitles or platform UI; crop tighter or replace those source clips before publishing."
        else:
            next_action = "Open the contact sheet and check low confidence segments before using the video."
        return {
            "decision": "Needs review",
            "reason": reason,
            "next_action": next_action,
        }
    reason = failures[0] if failures else "The run did not pass required checks."
    return {
        "decision": "Do not use yet",
        "reason": reason,
        "next_action": "Fix the reported material or setup problem, then rerun quick.",
    }


def _primary_warning(warnings: list[str]) -> str:
    if not warnings:
        return "Some segments need manual review."
    priorities = (
        ("platform UI", "original subtitles", "source frame", "preflight skipped"),
        ("same source video", "voiceover shell"),
        ("Story support is weak",),
        ("filename only",),
        ("low confidence",),
    )
    for group in priorities:
        for warning in warnings:
            if any(marker in warning for marker in group):
                return warning
    return warnings[0]
