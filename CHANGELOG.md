# Changelog

## V0.2

- 新增应用窗口图标和打包后的 EXE 图标。
- 托盘图标改为大数字，只显示 5 小时剩余额度数字。
- 托盘弹窗新增 5 小时剩余额度、5 小时刷新时间、本周剩余额度和周刷新日期时间。
- 托盘弹窗新增“立即刷新”按钮，点击弹窗外部会自动关闭。
- 刷新请求改为后台线程执行，避免网络慢或超时时卡住窗口。
- 改进 PyInstaller 打包脚本的 UTF-8 和中文路径输出兼容性。

## V0.1

- Initial Windows desktop quota monitor.
- Shows Codex 5-hour window, weekly window, reset time, and available reset credits.
