# MiMotion 自动刷步

该项目通过邮箱账号登录 Zepp（小米运动）并更新步数，支持 GitHub Actions 定时运行。

## 当前运行规则

- 每天北京时间 **06:00** 自动运行 1 次。
- 每次运行都会重新登录（不使用 token 缓存）。
- 刷新步数范围由环境变量 `STEP_RANGE` 控制（例如 `10000-15000`）。

## 运行前准备

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 配置环境变量

必须设置 `MI_ACCOUNTS`，格式：

```text
email:password;email:password
```

可选环境变量：

- `STEP_RANGE`：步数范围，格式 `min-max`（默认 `10000-15000`）
- `WECHAT_WEBHOOK_KEY`：企业微信机器人 webhook key（可选，用于推送结果）

Windows PowerShell 示例：

```powershell
$env:MI_ACCOUNTS = "a@b.com:pass1;c@d.com:pass2"
$env:STEP_RANGE = "12000-16000"
$env:WECHAT_WEBHOOK_KEY = "你的企业微信机器人key"
python "main_ mimotion.py"
```

## GitHub Actions 配置

### 1) 推送代码到 GitHub

```bash
git add .
git commit -m "update workflow and docs"
git push
```

### 2) 配置仓库 Secrets

在 GitHub 仓库：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

新增：

- `MI_ACCOUNTS`：`email:password;email:password`
- `STEP_RANGE`：步数范围，格式 `min-max`（例如 `12000-16000`，可选）
- `WECHAT_WEBHOOK_KEY`：企业微信机器人 webhook key（可选）

### 3) 运行方式

- 自动定时：`.github/workflows/run.yml`（北京时间 06:00）
- 手动触发：`Actions` → `run-mimotion` → `Run workflow`
