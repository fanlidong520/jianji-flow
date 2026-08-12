from pathlib import Path

from jianji_flow.quickstart import default_product_script, default_quick_work_dir


def test_default_product_script_has_five_short_lines():
    lines = default_product_script().splitlines()

    assert len(lines) == 5
    assert all(line.strip() for line in lines)
    assert all(len(line) <= 6 for line in lines)
    assert not any("保证" in line or "最低价" in line for line in lines)


def test_default_product_script_is_for_home_product_drafts():
    text = default_product_script()

    assert "家里" in text
    assert "刷" in text
    assert "下单" not in text


def test_default_quick_work_dir_uses_out_quick_prefix(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("jianji_flow.quickstart._timestamp", lambda: "20260812-010203")

    path = default_quick_work_dir(tmp_path)

    assert path == tmp_path / "out" / "quick-20260812-010203"
