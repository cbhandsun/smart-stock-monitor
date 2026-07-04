# Workspace GitOps Bridge 方案

## 目标

在飞书移动端通过 OpenClaw Agent，对 `/home/juhongtao/openclaw/config/workspace-dev` 下的项目完成：

```text
开发 -> 预览 -> 确认 -> Git 提交 -> GitHub 推送 -> Docker 部署 -> 飞书返回结果
```

同时保持权限边界清晰：

```text
OpenClaw 容器负责开发和编排
WSL 宿主机负责 GitHub 提交和 Docker 部署
项目目录不需要额外安装业务依赖
```

## 整体架构

```text
飞书指令
  -> OpenClaw 飞书 Agent
  -> OpenClaw Skill: workspace-gitops
  -> WSL GitOps Bridge
  -> /home/juhongtao/openclaw/config/workspace-dev/<project>
  -> git commit / git push / docker compose up -d --build
  -> 飞书返回提交和部署结果
```

## 核心原则

OpenClaw 容器不直接持有 GitHub 私钥，也不直接访问 Docker socket。

WSL 宿主机负责真正的提交和部署，因为它已经具备：

```text
git
GitHub SSH push 权限
docker
docker compose
```

## 适用项目范围

允许操作：

```text
/home/juhongtao/openclaw/config/workspace-dev/*
```

只允许该目录下的一级 Git 仓库，例如：

```text
workspace-dev/smart-stock-monitor
workspace-dev/another-project
```

禁止：

```text
跳出 workspace-dev
执行任意 shell 命令
提交 .env / 私钥 / token / .venv / node_modules / scratch / logs
未确认直接 push 或 deploy
```

## 飞书使用方式

示例：

```text
检查 smart-stock-monitor 变更
```

Agent 返回提交/部署预览。

```text
提交并部署 smart-stock-monitor，message: chore: update docker deployment
```

Agent 仍然先返回预览，不直接执行。

如果没有写 `message`，默认由 Agent 根据预览里的候选文件和 diff 摘要自动总结一个简短的 conventional commit message。例如你可以直接说：

```text
帮我提交并部署 smart-stock-monitor
```

Agent 应先生成类似下面的建议提交信息，并放进预览里：

```text
chore: harden docker deployment config
docs: update workspace gitops bridge guide
fix: handle cache cleanup race
```

```text
确认执行
```

WSL Bridge 才真正执行：

```bash
git add <白名单文件>
git commit -m "..."
git push origin <branch>
docker compose up -d --build
docker compose ps
```

## 预览内容

这里的预览不是网页 UI 预览，而是提交/部署预览，用来让移动端确认即将发生的动作。

预览应包含：

```text
项目名
项目路径
当前分支
Git remote
变更文件列表
将提交的文件
不会提交的文件
敏感信息检查结果
diff 摘要
验证命令
部署命令
预计访问地址
风险提示
建议提交信息
确认口令
```

示例返回：

```text
项目：smart-stock-monitor
路径：/home/juhongtao/openclaw/config/workspace-dev/smart-stock-monitor
分支：master
远端：git@github.com:cbhandsun/smart-stock-monitor.git

将提交：
M docker-compose.yml
M README.md
A .env.example

不会提交：
.env
.venv/
scratch/
*.bak
*.log

敏感检查：通过
Compose 校验：待执行

确认后将执行：
git commit
git push origin master
docker compose up -d --build
```

## WSL GitOps Bridge 功能

第一版建议支持这些动作：

```text
list_projects
status(project)
preview(project, message)
validate(project)
commit(project, message)
push(project)
deploy(project)
commit_push_deploy(project, message)
```

危险动作必须二次确认：

```text
commit
push
deploy
commit_push_deploy
```

## 项目级配置

每个项目可以选配：

```text
.agent-gitops.json
```

示例：

```json
{
  "name": "smart-stock-monitor",
  "defaultBranch": "master",
  "appUrl": "http://服务器IP:8502",
  "validate": [
    "docker compose config -q"
  ],
  "deploy": [
    "docker compose up -d --build",
    "docker compose ps"
  ],
  "allowFiles": [
    "**/*.py",
    "**/*.md",
    "Dockerfile",
    "docker-compose*.yml",
    ".dockerignore",
    ".env.example",
    "requirements.txt"
  ],
  "denyFiles": [
    ".env",
    ".env.*",
    "!.env.example",
    ".venv/**",
    "venv/**",
    "node_modules/**",
    "scratch/**",
    "*.bak",
    "*.log",
    "__pycache__/**"
  ]
}
```

没有配置文件时，Bridge 使用默认安全规则。

## 依赖策略

`workspace-dev` 下的项目不需要在 WSL 宿主机安装业务依赖。

Python、Node 等业务依赖都交给项目自己的 Dockerfile：

```text
Python: pip install -r requirements.txt
Node: npm ci / pnpm install
```

WSL 只需要：

```text
git
docker
docker compose
ssh
```

如果要跑测试，也优先用 Docker 跑：

```bash
docker compose run --rm app pytest
```

而不是污染 WSL 宿主机环境。

## 安全边界

必须禁止提交：

```text
.env
.env.local
私钥
token
API key
Bearer
cookie
.venv/
node_modules/
scratch/
logs/
cache/
*.bak
*.log
```

必须限制：

```text
commit message 长度
项目路径必须在 workspace-dev 内
只能操作 Git 仓库
只能执行白名单命令
deploy 只允许 docker compose
```

## 已落地位置

WSL 宿主机 Bridge：

```text
/home/juhongtao/openclaw/agent-tools/workspace-gitops/gitops_bridge.py
```

systemd user service：

```text
/home/juhongtao/.config/systemd/user/workspace-gitops.service
```

常用运维命令：

```bash
systemctl --user status workspace-gitops.service
systemctl --user restart workspace-gitops.service
```

OpenClaw 容器侧客户端：

```text
/home/node/.openclaw/scripts/workspace-gitops-client.mjs
```

OpenClaw Skill：

```text
/home/node/.openclaw/skills/workspace-gitops/SKILL.md
```

`smart-stock-monitor` 项目级配置：

```text
/home/juhongtao/openclaw/config/workspace-dev/smart-stock-monitor/.agent-gitops.json
```

## 最终体验

你在手机飞书里说：

```text
帮我提交并部署 smart-stock-monitor
```

OpenClaw 回复：

```text
这是预览，请确认。
建议提交信息：docs: update workspace gitops bridge guide
```

你说：

```text
确认执行
```

OpenClaw 回复：

```text
提交成功：2b00963
推送成功：origin/master
部署成功：smart-stock-monitor running
访问：http://服务器IP:8502
```

这套方案既能满足移动办公，又不会把 GitHub 私钥和 Docker 高权限直接塞进 OpenClaw 容器里。
