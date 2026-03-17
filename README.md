<<<<<<< HEAD
# myself_mimotion
小米运动刷步数（微信支付宝）支持邮箱登录，自己用
=======
# MiMotion 自动刷步

该项目通过邮箱账号登录 Zepp（小米运动）并更新步数，支持 GitHub Actions 定时运行。

## 运行前准备

### 1) 克隆项目并安装依赖

```bash
pip install -r requirements.txt
```

### 2) 配置环境变量

必须设置 `MI_ACCOUNTS`，格式：

```
email:password;email:password
```

可选环境变量：

- `RUN_RANGES`：按当天第几次运行设置步数范围（默认 `1=8000-12000;2=12000-15000;3=15000-30000`）
- `RUN_STATE_PATH`：当天运行计数状态文件（默认 `.cache/run_state.json`，按账号分别记录并每日清零）
- `TOKEN_CACHE_PATH`：token 缓存路径（默认 `.cache/token_cache.json`）

Windows PowerShell 示例：

```powershell
$env:MI_ACCOUNTS = "a@b.com:pass1; c@d.com:pass2"
$env:RUN_RANGES = "1=8000-12000;2=12000-15000;3=15000-30000"
python "main_ mimotion.py"
```

## GitHub Actions 配置

### 1) 推送到 GitHub

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

### 2) 配置仓库 Secrets

在 GitHub 仓库：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

添加以下 secrets：

- `MI_ACCOUNTS`：`email:password;email:password`
- `RUN_RANGES`：例如 `1=8000-12000;2=12000-15000;3=15000-30000`

### 3) 运行方式

- 自动定时：`.github/workflows/run.yml` 默认北京时间 08:00、09:00、10:00 运行
- 手动触发：`Actions` → `run-mimotion` → `Run workflow`

## 说明

- token 会缓存到 `.cache/token_cache.json`，如果失效会自动重新登录。
- 运行计数会记录在 `.cache/run_state.json`，用于判断当天第几次运行。
- 默认执行时间为北京时间 08:00、09:00、10:00。
- `RUN_RANGES` 支持自定义更多运行次数，例如：`1=7000-9000;2=8000-12000;3=12000-15000;4=15000-30000`。
- 如需调整执行时间，请修改 `.github/workflows/run.yml` 的 cron。
>>>>>>> aa2664b (init)
