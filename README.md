# Codex 额度监控

这是一个 Windows 桌面软件，用于实时显示 Codex 当前可用的额度窗口和可用重置次数。

当前版本：`V0.4`

## V0.4 新增

- 按接口返回的窗口时长识别 5 小时与每周额度，不再固定依赖 primary/secondary 字段。
- 当前只有周额度时，保留 5 小时行并显示 `-`，托盘图标自动改用周额度。
- 主窗口改为使用量卡片布局，显示额度进度、重置日期和可用重置次数。
- 解析重置额度列表及到期日期，接口失败时保留上一次成功结果。
- 重置列表采用只读布局，名称在左、到期日期在右，并支持折叠。
- 修复设置面板或重置列表收起后窗口偶尔不缩回的问题。

## V0.3 新增

- 刷新失败时额度显示 `--`，主窗口和托盘弹窗显示失败原因及累计失败时长。
- 重置次数刷新失败时保留上一次结果，不影响 5 小时和周额度更新。
- 自动刷新失败后指数退避，最长 15 分钟；手动刷新仍立即执行。
- 损坏或非法配置会自动备份并恢复默认值。
- 切换设置时保留旧结果，新请求成功后再替换，并丢弃过期请求结果。
- 只允许运行一个实例，重复启动会唤醒已有主窗口。
- 开机自启动仅对打包后的 EXE 开放。
- 修复设置面板展开后无法恢复窗口高度的问题。
- 完善退出清理、依赖锁定、自动化测试和 Windows CI 打包检查。

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

界面根据接口返回的窗口时长自动识别 5 小时窗口、周窗口和可用重置次数。
主窗口固定保留 5 小时额度行；接口暂时未返回该窗口时，额度与刷新时间显示为 `-`。

可确认的官方数据源：

- OpenAI API Usage / Costs API：可报告 API 组织用量和费用。
- Codex Enterprise Analytics API：企业/管理员场景下可报告 workspace Codex 用量。
- Codex Compliance API：企业/合规场景下可导出审计日志。

没有使用的内容：

- 没有保存 OpenAI 账号密码。
- 没有绕过登录、破解、非法抓包或读取网页私有会话。

## 功能

- 主窗口按卡片展示 5 小时和每周额度、剩余进度、重置日期及可用重置列表。
- 重置列表将名称放在左侧、到期日期放在右侧，保持只读展示。
- 剩余额度低于 20% 显示黄色提醒，低于 10% 显示红色提醒。
- 支持自动刷新：30 秒、60 秒、5 分钟、15 分钟。
- 支持“立即刷新”。
- 支持最小化到系统托盘。
- 托盘图标优先显示最短的可用额度窗口；当前只有周额度时自动显示周额度数字。
- 托盘弹窗按实际可用窗口调整标题、剩余百分比和刷新日期时间。
- 设置页支持刷新间隔、开机自启动、低额度提醒、系统通知。
- 只读使用 Codex 登录文件中的访问令牌，不把令牌写入本应用配置文件。
- 错误和日志展示会自动脱敏。

## 安装依赖

依赖清单在仓库的 `requirements.txt` 。安装依赖：

```powershell
git clone https://github.com/youziiiii/CodexQuotaMonitor.git
cd CodexQuotaMonitor
python -m pip install -r requirements.txt
```

开发、测试和打包依赖使用锁定版本：

```powershell
python -m pip install -r requirements-dev.txt
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

配置文件类型错误、刷新间隔非法或 JSON 损坏时，程序会在同目录生成
`config.invalid-<时间>.json` 备份，并恢复默认配置。

## 实时额度

实时接口返回 `used_percent`，程序显示 `100 - used_percent` 作为剩余百分比。程序读取每个窗口的 `limit_window_seconds` 判断它是 5 小时还是 1 周，不再假设 `primary_window` 或 `secondary_window` 具有固定含义。重置次数和到期日期来自 `rate-limit-reset-credits` 接口的 `available_count`、`credits[].title`、`credits[].status` 与 `credits[].expires_at`。

## 测试

```powershell
python -m pytest
```

GitHub Actions 会在 Windows 环境运行测试、打包 EXE，并执行启动冒烟检查。

## 安全策略

- 只读方式读取本机 Codex `auth.json`。
- 访问令牌只发送给 `chatgpt.com` 的额度接口。
- 不把 API Key 或 Token 明文写入配置文件。
- 不读取或展示原始 prompt / 日志正文。
- 不绕过登录，不抓取私有网页会话。
