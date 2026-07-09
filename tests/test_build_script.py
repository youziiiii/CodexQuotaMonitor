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
