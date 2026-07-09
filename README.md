# Codex 额度监控

这是一个 Windows 桌面软件，用于实时显示 Codex 5 小时窗口、周窗口和可用重置次数。

当前版本：`V0.2`

## V0.2 新增

- 新增应用窗口图标和 EXE 图标。
- 托盘图标改为大数字显示 5 小时剩余额度。
- 托盘弹窗显示 5 小时剩余额度、5 小时刷新时间、本周剩余额度和周刷新日期时间。
- 托盘弹窗支持“立即刷新”，点击弹窗外部会自动关闭。
- 刷新请求改为后台执行，避免网络慢或超时时卡住窗口。
- 打包脚本增强中文路径和 UTF-8 输出兼容性。

## 数据来源

当前版本默认使用 Codex 登录文件读取访问令牌：

```text
C:\Users\<你的用户名>\.codex\auth.json
```

只请求 ChatGPT 官方后端实时额度接口：

```text
https://chatgpt.com/backend-api/wham/usage
https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
```

界面显示的是该接口返回的 5 小时窗口、周窗口和可用重置次数；

可确认的官方数据源：

- OpenAI API Usage / Costs API：可报告 API 组织用量和费用。
- Codex Enterprise Analytics API：企业/管理员场景下可报告 workspace Codex 用量。
- Codex Compliance API：企业/合规场景下可导出审计日志。

没有使用的内容：

- 没有保存 OpenAI 账号密码。
- 没有绕过登录、破解、非法抓包或读取网页私有会话。

## 功能

- 小面板显示 5 小时剩余百分比、1 周剩余百分比、重置时间、可用重置次数。
- 剩余额度低于 20% 显示黄色提醒，低于 10% 显示红色提醒。
- 支持自动刷新：30 秒、60 秒、5 分钟、15 分钟。
- 支持“立即刷新”。
- 支持最小化到系统托盘。
- 托盘图标大数字显示 5 小时剩余额度，托盘悬浮提示显示 5 小时剩余、刷新时间和本周剩余。
- 托盘弹窗显示 5 小时剩余、5 小时刷新时间、本周剩余和周刷新日期时间。
- 设置页支持刷新间隔、开机自启动、低额度提醒、系统通知。
- API Key / Token 通过 Windows Credential Manager 保存，不写入 JSON 配置文件。
- 错误和日志展示会自动脱敏。

## 安装依赖

依赖清单在仓库的 `requirements.txt` 。安装依赖：

```powershell
git clone https://github.com/youziiiii/CodexQuotaMonitor.git
cd CodexQuotaMonitor
python -m pip install -r requirements.txt
```

## 从源码运行

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

也可以直接运行：

```powershell
python -m codex_quota_monitor.main
```

## 打包 EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

输出位置：

```text
dist\CodexQuotaMonitor\CodexQuotaMonitor.exe
```

## 配置文件

运行时配置位于：

```text
%APPDATA%\CodexQuotaMonitor\config.json
```

示例配置见：

```text
config.example.json
```

不要把 API Key 或 Token 写进 JSON 配置文件。

## 实时额度

实时接口返回 `used_percent`，程序显示 `100 - used_percent` 作为剩余百分比。5 小时窗口使用 `primary_window`，周窗口使用 `secondary_window`。重置次数来自 `rate_limit_reset_credits.available_count`。

## 测试

```powershell
python -m pytest
```

## 安全策略

- 只读方式读取本机 Codex `auth.json`。
- 不上传任何个人数据。
- 不把 API Key 或 Token 明文写入配置文件。
- 不读取或展示原始 prompt / 日志正文。
- 不绕过登录，不抓取私有网页会话。
