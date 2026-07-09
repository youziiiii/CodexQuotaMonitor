$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
[Console]::InputEncoding = [System.Text.UTF8Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
chcp.com 65001 | Out-Null
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python -m pip install -r requirements.txt
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name CodexQuotaMonitor `
  --add-data "config.example.json;." `
  --add-data "assets/app_icon.ico;assets" `
  --icon "assets/app_icon.ico" `
  codex_quota_monitor/main.py

Write-Host "Generated: $ProjectRoot\dist\CodexQuotaMonitor\CodexQuotaMonitor.exe"
