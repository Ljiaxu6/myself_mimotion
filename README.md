# MiMotion 自动刷步

该项目通过邮箱账号登录 Zepp（小米运动）并更新步数，支持 GitHub Actions 定时运行。

## 当前运行规则

- 每天北京时间 **01:00** 和 **14:00** 自动运行。
- 步数范围为固定规则：
  - 北京时间 `<= 12` 点：`10000-15000`
  - 北京时间 `> 12` 点：`15000-20000`

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

- `TOKEN_CACHE_PATH`：token 缓存路径（默认 `.cache/token_cache.json`）
- `WECHAT_WEBHOOK_KEY`：企业微信机器人 webhook key（可选，用于推送结果）

Windows PowerShell 示例：

```powershell
$env:MI_ACCOUNTS = "a@b.com:pass1;c@d.com:pass2"
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
- `WECHAT_WEBHOOK_KEY`：企业微信机器人 webhook key（可选）

### 3) 运行方式

- 自动定时：`.github/workflows/run.yml`（北京时间 01:00、14:00）
- 手动触发：`Actions` → `run-mimotion` → `Run workflow`

## 缓存说明（已检查）

工作流已配置 `.cache` 缓存，主要用于保存 `token_cache.json`，减少重复登录。

- 缓存目录：`.cache`
- 缓存 key：`mimotion-cache-${{ github.repository }}-${{ github.run_id }}`
- 恢复前缀：`mimotion-cache-${{ github.repository }}-`

这样可以在每次运行前恢复最新缓存，并在运行结束后保存新的缓存。