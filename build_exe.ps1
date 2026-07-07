$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python -m pip install -r requirements.txt
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name CodexQuotaMonitor `
  --add-data "config.example.json;." `
  codex_quota_monitor/main.py

Write-Host "已生成：$ProjectRoot\dist\CodexQuotaMonitor\CodexQuotaMonitor.exe"
