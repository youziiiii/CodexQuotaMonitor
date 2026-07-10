from pathlib import Path

import codex_quota_monitor


def test_package_version_is_0_3():
    assert codex_quota_monitor.__version__ == "0.3"


def test_readme_and_changelog_document_v0_3_features():
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert "当前版本：`V0.3`" in readme
    assert "## V0.3" in changelog
    assert "托盘图标" in changelog
    assert "5 小时" in changelog
    assert "周刷新" in changelog
