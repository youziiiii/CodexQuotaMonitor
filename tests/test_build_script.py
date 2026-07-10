from pathlib import Path


def test_build_script_sets_utf8_console_output():
    script = Path("build_exe.ps1").read_text(encoding="utf-8")

    assert "$OutputEncoding" in script
    assert "[Console]::OutputEncoding" in script
    assert "[Console]::InputEncoding" in script
    assert "UTF8Encoding" in script
    assert "PYTHONUTF8" in script
    assert "PYTHONIOENCODING" in script
    assert "chcp.com 65001" in script
    assert "Generated:" in script


def test_dependencies_are_split_locked_and_used_by_ci():
    runtime = Path("requirements.txt").read_text(encoding="utf-8")
    development = Path("requirements-dev.txt").read_text(encoding="utf-8")
    build_script = Path("build_exe.ps1").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "PySide6==" in runtime
    assert ">=" not in runtime
    assert "-r requirements.txt" in development
    assert "pytest==" in development
    assert "pyinstaller==" in development.lower()
    assert "requirements-dev.txt" in build_script
    assert "python -m pytest -q" in workflow
    assert "Smoke test executable" in workflow
