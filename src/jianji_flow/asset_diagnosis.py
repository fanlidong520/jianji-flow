from __future__ import annotations

from pathlib import Path


ROLE_HINTS = {
    "hook": ("hook", "opening", "intro", "unbox", "result", "开头", "开箱", "效果"),
    "pain": ("pain", "problem", "dust", "dirty", "before", "痛点", "脏", "灰", "油污", "水垢", "清洁前"),
    "feature": ("feature", "product", "brush", "detail", "material", "size", "卖点", "产品", "刷", "材质", "尺寸", "细节"),
    "evidence": (
        "evidence",
        "demo",
        "use",
        "before-after",
        "after",
        "test",
        "scene",
        "演示",
        "使用",
        "对比",
        "实测",
        "教程",
        "场景",
        "清洁后",
    ),
    "cta": ("cta", "ending", "packshot", "order", "buy", "结尾", "下单", "购买", "优惠", "价格", "链接"),
}

ROLE_LABELS = {
    "hook": "开头",
    "pain": "痛点",
    "feature": "卖点",
    "evidence": "演示/证据",
    "cta": "收尾",
}

ROLE_EXAMPLES = {
    "hook": "01-hook-opening.mp4",
    "pain": "02-pain-before.mp4",
    "feature": "03-feature-product-detail.mp4",
    "evidence": "04-evidence-demo-after.mp4",
    "cta": "05-cta-packshot-buy.mp4",
}


def _asset_path(asset: dict) -> str:
    return str(asset.get("path", ""))


def _role_segment_duration(role: str, segments: list[dict]) -> int:
    for segment in segments:
        if segment.get("role") == role:
            return max(1, int(segment["end_ms"]) - int(segment["start_ms"]))
    return 0


def _matched_role_scores(asset: dict) -> dict[str, int]:
    name = Path(_asset_path(asset)).stem.casefold()
    return {
        role: sum(1 for hint in hints if hint.casefold() in name)
        for role, hints in ROLE_HINTS.items()
    }


def _asset_duration_ms(asset: dict) -> int:
    try:
        duration_ms = int(asset.get("duration_ms", 0))
    except (TypeError, ValueError):
        return 0
    return max(0, duration_ms)


def _assets_by_primary_role(assets: list[dict]) -> dict[str, list[dict]]:
    grouped = {role: [] for role in ROLE_HINTS}
    for asset in assets:
        role = primary_role_for_asset(asset)
        if role is not None:
            grouped[role].append(asset)
    return grouped


def _duplicate_media_groups(assets: list[dict]) -> list[dict]:
    by_digest: dict[str, list[str]] = {}
    for asset in assets:
        digest = str(asset.get("sha256", "")).strip().casefold()
        path = _asset_path(asset)
        if digest and path:
            by_digest.setdefault(digest, []).append(path)
    return [
        {"sha256": digest, "paths": paths}
        for digest, paths in by_digest.items()
        if len(paths) > 1
    ]


def primary_role_for_asset(asset: dict) -> str | None:
    name = Path(_asset_path(asset)).stem.casefold()
    direct_roles = [role for role in ROLE_HINTS if role.casefold() in name]
    if len(direct_roles) == 1:
        return direct_roles[0]
    scores = _matched_role_scores(asset)
    best_score = max(scores.values(), default=0)
    if best_score <= 0:
        return None
    best_roles = [role for role, score in scores.items() if score == best_score]
    if len(best_roles) != 1:
        return None
    return best_roles[0]


def diagnose_product_assets(assets: list[dict], segments: list[dict]) -> dict:
    roles: dict[str, dict] = {}
    actions: list[str] = []
    if not segments or any(_role_segment_duration(role, segments) <= 0 for role in ROLE_HINTS):
        return {
            "status": "fail",
            "roles": {},
            "actions": ["Segment plan is incomplete. Rebuild the draft plan before checking materials."],
        }
    if not assets:
        return {
            "status": "fail",
            "roles": {},
            "actions": ["No decodable video assets found. Add local .mp4 clips to the assets folder."],
        }

    duplicate_groups = _duplicate_media_groups(assets)
    for group in duplicate_groups:
        paths = ", ".join(Path(path).name for path in group["paths"])
        actions.append(
            f"Duplicate media detected: {paths} are byte-identical; different filenames do not prove independent footage."
        )

    assets_by_role = _assets_by_primary_role(assets)
    for role in ROLE_HINTS:
        needed_ms = _role_segment_duration(role, segments)
        candidates = assets_by_role[role]
        long_enough = [asset for asset in candidates if _asset_duration_ms(asset) >= needed_ms]
        if long_enough:
            roles[role] = {
                "status": "ready",
                "message": f"{role} clip passes filename and duration screening",
                "candidates": [_asset_path(item) for item in long_enough],
            }
        elif candidates:
            roles[role] = {
                "status": "weak",
                "message": f"{role} clip is too short",
                "candidates": [_asset_path(item) for item in candidates],
            }
            actions.append(f"Weak {role} clip: asset too short for the target segment.")
        else:
            roles[role] = {"status": "missing", "message": f"{role} clip is missing", "candidates": []}
            actions.append(f"Missing {role} clip: add a video for the {role} segment.")

    if any(item["status"] == "missing" for item in roles.values()):
        status = "fail"
    elif any(item["status"] == "weak" for item in roles.values()):
        status = "warning"
    elif duplicate_groups:
        status = "warning"
    else:
        status = "pass"
    return {"status": status, "roles": roles, "actions": actions, "duplicate_groups": duplicate_groups}


def format_asset_diagnosis(report: dict, *, visual_selection_supplied: bool = False) -> str:
    if visual_selection_supplied:
        lines = [
            "# Material diagnosis",
            "Visual selections were supplied; filename screening is not used as the final role decision.",
            "Review the selected frames and the final source-preflight result before publishing.",
            "",
        ]
        for role in report.get("roles", {}):
            role_label = f"{role} / {ROLE_LABELS.get(role, role)}"
            lines.append(f"- {role_label}: VISUAL REVIEW SUPPLIED - candidate frames will be checked before rendering.")
        for group in report.get("duplicate_groups", []):
            paths = ", ".join(Path(path).name for path in group.get("paths", []))
            lines.append(f"- DUPLICATE MEDIA: {paths} are byte-identical; different filenames do not prove independent footage.")
        lines.extend(
            [
                "",
                "下一步:",
                "- 打开 visual-candidate-sheet.png 或 review.html，确认每个角色的画面真的支持对应文案。",
                "- 如果源画面包含旧字幕或平台 UI，先替换或裁切素材，再重新运行。",
                "",
                "Visual selection supplied; continue with source and story review",
            ]
        )
        return "\n".join(lines) + "\n"

    lines = ["# Material diagnosis", "Filename and duration screening only; watch the video before publishing.", ""]
    for role, item in report.get("roles", {}).items():
        status = item.get("status", "unknown")
        label = "CANDIDATE" if status == "ready" else status.upper()
        role_label = f"{role} / {ROLE_LABELS.get(role, role)}"
        message = item.get("message", "")
        if status == "ready":
            message = f"{message}; not visual proof"
        lines.append(f"- {role_label}: {label} - {message}")
    for group in report.get("duplicate_groups", []):
        paths = ", ".join(Path(path).name for path in group.get("paths", []))
        lines.append(f"- DUPLICATE MEDIA: {paths} are byte-identical; different filenames do not prove independent footage.")
    actions = report.get("actions", [])
    if actions:
        lines.append("")
        lines.append("下一步:")
        for role, item in report.get("roles", {}).items():
            role_label = ROLE_LABELS.get(role, role)
            example = ROLE_EXAMPLES.get(role, f"{role}.mp4")
            if item.get("status") == "missing":
                lines.append(f"- 缺少{role_label}素材：添加类似 `{example}` 的视频。")
            elif item.get("status") == "weak":
                lines.append(f"- {role_label}素材太短：换一条更长的视频，文件名可参考 `{example}`。")
        if not report.get("roles"):
            lines.extend(f"- {action}" for action in actions)
    decision = {
        "pass": "Can run quick draft; inspect contact-sheet before publishing",
        "warning": "Can run, but review carefully",
        "fail": "Not ready",
    }.get(report.get("status"), "Not ready")
    lines.append("")
    lines.append(decision)
    return "\n".join(lines) + "\n"
