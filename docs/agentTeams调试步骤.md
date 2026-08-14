# AgentTeams 调试步骤（从安装到 Skill 链路打通）

> 目标：在**一台新电脑**上，从零跑通 AgentTeams，并验证"Skill 分发 → Worker 按 Skill 完成任务"链路。
> 本文档记录实际踩过的所有坑和对应解法，照做即可。
> 日期：2026-08-12

---

## 〇、环境约定

| 项 | 值（示例机器）| 备注 |
|----|--------------|------|
| 操作系统 | Windows 11（64 位）| 需要 WSL2 |
| Docker Desktop 安装目录 | `F:\Docker` | 自定义 |
| Docker WSL2 数据目录 | `F:\DockerData` | 自定义（避免占 C 盘）|
| AgentTeams 工作区 | `C:\Users\<用户名>\agentteams-manager` | 默认 |
| AgentTeams env 文件 | `C:\Users\<用户名>\agentteams-manager.env` | 关键 |

> ⚠️ 文档中的 `caozhenyang` 均换成你新电脑的实际用户名。

---

## 一、安装 Docker Desktop + WSL2

### 1.1 确认 WSL2

```bash
wsl --status          # 默认版本应为 2
wsl --list --verbose  # 应能列出发行版
```

> 若未启用 WSL2：管理员 PowerShell 运行 `wsl --install`，重启后 `wsl --set-default-version 2`。

### 1.2 安装 Docker Desktop（自定义目录到 F:）

```bash
# 下载安装程序
curl -fL -o "Docker Desktop Installer.exe" \
  "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"

# 静默安装（程序→F:\Docker，WSL2 数据→F:\DockerData）
"Docker Desktop Installer.exe" install --quiet --accept-license \
  --backend=wsl-2 \
  --installation-dir="F:\Docker" \
  --wsl-default-data-root="F:\DockerData"
```

> ⚠️ 安装后 `docker` 命令在**新开的终端**才有 PATH；老终端需 `export PATH="/f/Docker/resources/bin:$PATH"`。

---

## 二、安装 AgentTeams（Docker 方式）

### 2.1 运行官方安装脚本

PowerShell 执行（内联下载执行）：

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
$wc=New-Object Net.WebClient
$wc.Encoding=[Text.Encoding]::UTF8
iex $wc.DownloadString('https://raw.githubusercontent.com/agentscope-ai/AgentTeams/main/install/agentteams-install.ps1')
```

按提示配置：LLM 提供商（OpenAI 兼容 + DeepSeek）、API Key、管理员账号、端口等。

### 2.2 结果

安装完成会启动两个容器：

```
agentteams-controller   # 内嵌 Tuwunel/MinIO/Higress/Element Web/controller
agentteams-manager      # Manager Agent
```

---

## 三、⚠️ 坑 1：APPSERVICE token 缺失（必须处理）

### 3.1 现象

安装脚本卡在"Waiting for Manager Agent container... 300s 超时"，controller 报错：

```
panic: AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN is required when AppService mode is enabled;
       run install script or set env var
```

修复 AS token 后重启，还会再报：

```
panic: AGENTTEAMS_MATRIX_APPSERVICE_HS_TOKEN is required when AppService mode is enabled
```

### 3.2 根因

- 新版 `agentteams-embedded:latest` 镜像要求 **AS token + HS token**（Matrix AppService 成对令牌）
- 但官方安装脚本 **不生成也不传** 这两个变量（版本不同步的上游 bug）

### 3.3 修复：生成并写入两个 token

在 `agentteams-manager.env` 末尾追加：

```bash
# 生成两个 64 位随机 hex
TOKEN_AS=$(cat /dev/urandom | tr -dc 'a-f0-9' | head -c 64)
TOKEN_HS=$(cat /dev/urandom | tr -dc 'a-f0-9' | head -c 64)

# 追加到 env 文件
echo "AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN=$TOKEN_AS" >> "C:\Users\<用户名>\agentteams-manager.env"
echo "AGENTTEAMS_MATRIX_APPSERVICE_HS_TOKEN=$TOKEN_HS" >> "C:\Users\<用户名>\agentteams-manager.env"
```

> ⚠️ 两个 token 要**保留**（controller 用它向 Tuwunel 注册 appservice），重建容器时复用同一值。

---

## 四、⚠️ 坑 2：重建 controller 容器（MSYS CRLF 污染）

### 4.1 为什么必须重建

只改 env 文件不够——controller 容器的环境变量是**创建时注入**的，必须**删除重建**容器让它重新读 env。

### 4.2 ⚠️ 从 Git Bash 重建的隐藏坑

**现象**：用 `docker run ... -e "KEY=VALUE"` 逐个传参，容器里变量值会多一个 `\r`：

```bash
# 容器内检查（若值带 \r，`]` 会跑到下一行）
docker exec agentteams-controller sh -c 'printf "%s" "$AGENTTEAMS_MANAGER_ENABLED" | od -c'
# 期望: true
# 实际: true\r   ← MSYS 注入的回车符
```

**后果**：`AGENTTEAMS_MANAGER_ENABLED=true\r` 与字符串 `"true"` 不相等 → controller 判定"Manager provisioning disabled" → 不创建 Manager。

### 4.3 正确做法：Python 写干净 env 文件 + `--env-file`

**Step 1：** 从旧容器导出全部环境变量，用 **Python** 写成一个干净文件（关键：`newline='\n'` 避免 CR）：

```bash
# 导出旧容器 env
docker inspect agentteams-controller > controller-inspect.json
jq -r '.[0].Config.Env[]' controller-inspect.json > env_clean.txt

# 用 Python 写干净 env（追加两个 token）
python -c "
import io
lines = []
with io.open(r'<env_clean.txt 的 Windows 路径>', 'r', encoding='utf-8', newline='') as f:
    for l in f:
        lines.append(l.rstrip('\r\n'))
lines.append('AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN=<你的AS_TOKEN>')
lines.append('AGENTTEAMS_MATRIX_APPSERVICE_HS_TOKEN=<你的HS_TOKEN>')
with io.open(r'C:\<路径>\container.env', 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
"
```

**Step 2：** 删除旧容器，用 `--env-file` 重建（务必加 `MSYS_NO_PATHCONV=1`）：

```bash
export MSYS_NO_PATHCONV=1
docker stop agentteams-controller
docker rm agentteams-controller

docker run -d \
  --name agentteams-controller \
  --restart unless-stopped \
  --network agentteams-net \
  --network-alias matrix-local.agentteams.io \
  --network-alias aigw-local.agentteams.io \
  --network-alias fs-local.agentteams.io \
  -p 127.0.0.1:18001:8001 \
  -p 127.0.0.1:18080:8080 \
  -p 127.0.0.1:18088:8088 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v agentteams-data:/data \
  -v "/run/desktop/mnt/host/c/Users/<用户名>/agentteams-manager:/root/agentteams-fs/agents/manager" \
  --env-file "C:/<路径>/container.env" \
  higress-registry.cn-hangzhou.cr.aliyuncs.com/agentteams/agentteams-embedded:latest
```

> ⚠️ 端口/网络别名/挂载要与实际一致（上面是标准嵌入式安装的默认值）。

### 4.4 重建后验证

```bash
# 各服务 RUNNING（含 agentteams-controller 不再崩溃）
docker logs agentteams-controller 2>&1 | grep -E "success:|FATAL"

# env 无 \r
docker exec agentteams-controller sh -c 'printf "%s" "$AGENTTEAMS_MANAGER_ENABLED" | od -c'
# → 应输出: true （无 \r）

# Manager 容器被创建
docker ps --format "{{.Names}} {{.Status}}" | grep agentteams
# → agentteams-manager 应 Up
```

---

## 五、验证系统启动

### 5.1 网页访问（全部应 HTTP 200）

```
http://127.0.0.1:18088   Element Web 聊天界面
http://127.0.0.1:18001   Higress 控制台
http://127.0.0.1:18080   AI 网关
http://127.0.0.1:18888   Manager 控制台（OpenClaw）
```

### 5.2 用 admin 账号登录 Element Web

默认管理员账号在安装时配置（用户/密码）。

---

## 六、创建 Worker 并打通 Skill 链路（核心验证）

### 6.1 创建 Worker

```bash
# CLI 方式
docker exec agentteams-controller agt create worker --name alice --model deepseek-v4-flash

# 或聊天方式：Element Web 里 DM manager 说
#   "创建 worker alice，runtime openclaw"
```

验证：`docker exec agentteams-controller agt get workers` → alice 应 Running。

### 6.2 准备一个 Skill（复制到 Manager 工作区）

```bash
# 例如 test-run Skill
mkdir -p "C:\Users\<用户名>\agentteams-manager\worker-skills\test-run"
# 把 SKILL.md（含 frontmatter: name + description）放进去
```

> SKILL.md 格式（frontmatter 是关键触发条件）：
> ```markdown
> ---
> name: test-run
> description: 运行 pytest 并读取测试输出。当任务提到"运行测试、跑 pytest、验证测试"时使用。
> ---
> <正文指令>
> ```

### 6.3 Element Web 让 Manager 分发 Skill

在 **manager 房间**发：

> 请从 `~/agentteams-manager/worker-skills/test-run/` 安装 `test-run` 这个 Skill 给 Worker `alice`。验证文件已上传，并确认 alice 的 Skill 分配中包含 test-run。

> ⚠️ 关键：skill 名必须出现在 `spec.skills`（只是把文件放进存储不算安装完成）。

### 6.4 验证分配成功

```bash
docker exec agentteams-controller agt get workers alice -o json | jq '.skills'
# → 应包含 "test-run"
```

### 6.5 让 alice 用 Skill 完成任务（验证链路）

在 **alice 房间**发：

> 用 `test-run` 这个 skill 对 `/root/agentteams-fs/agents/alice/greeting-cli/test_greeter.py` 跑一遍测试，并把结果写到 test_report.txt。

**判断成功**：
- alice 房间出现 pytest 输出
- alice 是"按 SKILL.md 指令执行"（不是自由发挥）
- 产物写入共享区

> ✅ 走到这里，Skill 分发链路就打通了，后续可以铺开完整 DevFlow Kit 的 8 个 Agent + 11 个 Skill。

---

## 七、搭建完整 Worker 与 Team（apply.sh 批量创建）

> 目标：把 `agents/` 目录下的 **8 个 Worker + 2 个 Team** 定义批量应用到 AgentTeams。

### 7.1 前置

- AgentTeams 已运行：`docker ps` 能看到 `agentteams-controller` / `agentteams-manager`
- `agt` 可用：`docker exec agentteams-controller agt get workers` 能返回列表
- `agents/*.yaml` 定义已就绪（Worker + Team）

### 7.2 执行 apply.sh

```bash
cd AgentTeams-devflow-kit
bash scripts/apply.sh
```

**apply.sh 原理**（脚本在 `scripts/apply.sh`）：

```
1. 复制 agents/*.yaml → 宿主机工作区 apply-yamls/
   （controller 挂载了 C:\Users\<用户名>\agentteams-manager → /root/agentteams-fs/agents/manager/）
2. 依次 docker exec agentteams-controller agt apply -f <容器内路径>
   - 先 Worker（被引用），后 Team（引用 Worker）
3. 验证：agt get workers / agt get teams
```

> ⚠️ `agt apply` 不支持 `-f -`（stdin），必须给真实文件路径，所以 apply.sh 用"复制到挂载点"传文件。

### 7.3 验证结果

```bash
docker exec agentteams-controller agt get workers
docker exec agentteams-controller agt get teams
```

期望：8 个 Worker 全部 `Running`，2 个 Team `created`；`docker ps` 看到 8 个 `agentteams-worker-*` 容器。

### 7.4 踩坑记录（重要）

| # | 现象 | 原因 | 解决 |
|---|------|------|------|
| 1 | `Error: read -: open -: no such file` | `agt apply -f` 不支持 stdin `-` | 复制 YAML 到挂载点再 `agt apply -f <容器内路径>` |
| 2 | `HTTP 400: cannot unmarshal string into mcpServers` | v1.1.1 起 `mcpServers` 改为 `{name,url,transport}` 对象数组 | 写对象格式，或暂不配置 |
| 3 | `HTTP 400: invalid role "member"` | Team 成员 role 合法值只有 `team_leader`/`worker` | `role: member` → `role: worker` |
| 4 | `HTTP 400: referenced Worker xx does not exist` | Team 引用了未创建的 Worker | apply.sh 先 Worker 后 Team |
| 5 | `Error: read C:/Develop/Git/root/...` | Git Bash MSYS 把 `/root/...` 转成 Windows 路径 | `export MSYS_NO_PATHCONV=1` |

### 7.5 修改 / 删除角色

```bash
# 修改：编辑 agents/*.yaml → 重跑 apply.sh（apply 是"创建或更新"）
bash scripts/apply.sh

# 删除
docker exec agentteams-controller agt delete worker <name>
docker exec agentteams-controller agt delete team <team-name>
```

---

## 八、分发 Skill 到全部 Worker

> 目标：把 `skills/` 下的自定义 Skill 装进各 Worker（写入 spec.skills + 上传到 MinIO），让 Worker 真正"会干活"。

### 8.1 复制 Skill 到工作区

```bash
cd AgentTeams-devflow-kit
bash scripts/install-skills.sh
# → 把 skills/ 复制到 C:\Users\<用户名>\agentteams-manager\worker-skills\
```

> 注意：`devflow-pipeline` 在 `workflow/` 下，需单独复制到 `worker-skills/`：
> ```bash
> cp -r workflow/devflow-pipeline ~/agentteams-manager/worker-skills/
> ```

### 8.2 Element Web 让 Manager 分发

在 **manager 房间**逐条发送（每 Worker 一条），Manager 会上传 Skill 到 MinIO（`agents/<worker>/skills/`）并更新 spec.skills：

> 请从 `~/agentteams-manager/worker-skills/` 安装 `<skill列表>` 给 Worker `<名字>`。验证上传并确认 spec.skills 已包含。

### 8.3 验证

```bash
for w in devflow-runner designer implementer tester reviewer analyst architect-leader quality-leader; do
  echo "=== $w ==="
  docker exec agentteams-controller agt get workers $w -o json | jq -r '.skills[]?'
done
```

### 8.4 ⚠️ 坑：spec.skills 含内置技能导致分发中断

**现象**：Manager 安装脚本 `--add-skill` 镜像该 Worker spec 已有技能时，找不到 `task-management` 的 SKILL.md，`set -e` 中断，目标技能没写进 spec。

**原因**：
- `task-management` 是 **Manager 专用技能**（在 Manager 技能目录，不是 Worker 技能），Worker 技能库里没有它的 SKILL.md
- 其他内置技能（`file-sync`/`project-participation` 等）是 openclaw **自动物化**的，写不写 spec 都会在 Worker 里

**解决**：从 Worker 的 spec.skills 移除所有内置技能，**只保留自定义 Skill**，重新 apply：

```bash
# 编辑 agents/*.yaml，skills 只留自定义项，例如 implementer 只留:
#   skills:
#     - tdd-coding
bash scripts/apply.sh   # 重新应用，spec.skills 更新
```

### 8.5 验证内置技能自动物化

即使 spec.skills 不含 `file-sync`/`project-participation`，Worker 的 MinIO `agents/<name>/skills/` 里也会有它们（openclaw 自动物化）——可确认：
```bash
docker exec agentteams-controller mc ls agentteams/agentteams-storage/agents/implementer/skills/
```

---

## 九、验证文件共享读写链路（Worker 读写 MinIO 共享区）

> 目的：确认 Worker 能**读、改、写回**共享文件——这是 implementer↔tester 多 Worker 协作的基础。

### 7.1 先理解：共享区在哪（三层模型）

| 层 | 路径 | 说明 |
|----|------|------|
| MinIO 对象存储 | `agentteams/agentteams-storage/shared/` | 真源 |
| Worker/Manager 容器内 | `/root/agentteams-fs/shared/` | Worker 读写这个，自动与 MinIO 同步 |
| 宿主机 | ❌ 没有 | 资源管理器看不到，只能用 mc 或容器访问 |

> ⚠️ 关键认知：**MinIO 是"网盘"，mc 是"网盘客户端"**。共享区不是本地文件夹。

### 7.2 把文件放进共享区

套路：先放宿主机工作区（controller 挂载点）→ 再 mc cp 到 MinIO：

```bash
# 1. 文件先放宿主机工作区（controller 挂载了它）
#    C:\Users\<用户名>\agentteams-manager\<名称>\
# 2. controller 里 mc cp 上传到 MinIO shared/
export MSYS_NO_PATHCONV=1
docker exec agentteams-controller mc cp -r \
  /root/agentteams-fs/agents/manager/<名称> \
  agentteams/agentteams-storage/shared/projects/
```

### 7.3 让 Worker 读写共享文件（验证）

在 **alice 房间**发任务：

> 读取 `/root/agentteams-fs/shared/projects/<名称>/<文件>`，把某处改成 xxx，写回共享区。

观察 Worker 行为：
- 先执行 `agentteams-sync` 从 MinIO 拉取最新文件
- 本地修改
- `mc cp` 写回 MinIO

### 7.4 验证写回成功（⚠️ 看 MinIO，不是宿主中转目录）

```bash
# 看 MinIO 上文件的真实内容
export MSYS_NO_PATHCONV=1
docker exec agentteams-controller mc cat \
  agentteams/agentteams-storage/shared/projects/<名称>/<文件>
```

> ⚠️ 关键坑：宿主机 `agentteams-manager\<名称>\` 只是当初上传用的**中转副本**，不是共享区。Worker 改的是 MinIO 里的副本，**验证改动必须查 MinIO**，别查宿主中转目录。

### 7.5 把 MinIO 代码拉回本地（审阅 / git 提交）

```bash
# 方法 1：mc cp 到挂载点（自动同步到宿主机工作区）
export MSYS_NO_PATHCONV=1
docker exec agentteams-controller mc cp -r \
  agentteams/agentteams-storage/shared/projects/<名称> \
  /root/agentteams-fs/agents/manager/minio-pulled/
# → 本地出现在 C:\Users\<用户名>\agentteams-manager\minio-pulled\<名称>\

# 方法 2：一键脚本（DevFlow Kit 的 scripts/）
bash scripts/pull-minio.sh shared/projects/<名称>
# → 拉到 C:\Users\<用户名>\agentteams-manager\minio-pulled\<名称>\
```

### 7.6 图形界面（可选）

开通 MinIO 控制台（重建 controller 加 `-p 127.0.0.1:19001:9001`）后，浏览器访问 `http://127.0.0.1:19001`，账号 `admin` / 管理员密码，像文件管理器一样浏览/下载共享区。详见 `HiClaw接入与Docker部署指南.md` 2.4。

### 7.7 验证 Worker 访问共享区模板工程

> 目的：确认 Worker（如 implementer）能访问共享区里的模板工程（`shared/projects/devflow-template/`）——后面 implementer 要在它上面写代码、tester 要测它。

**操作**（用 **admin 身份**，在对应 Worker 的房间发消息——admin 在所有人的房间里，可直接对话）：

> 请读取 `/root/agentteams-fs/shared/projects/devflow-template/backend/pom.xml` 的内容，告诉我这个 Maven 项目的 groupId、artifactId 和 Spring Boot 版本。

**判断成功**：Worker 能正确读出 pom.xml 内容（如 `groupId=com.example`、`artifactId=app`、Spring Boot `2.7.18`）→ 访问共享区模板的路径通了。

### 9.8 自定义 Worker 镜像（Java/Maven/MySQL/Playwright）

> 背景：官方 Worker 镜像**没有 Java/Maven**，无法跑 `mvn test`/Playwright E2E。需要给 implementer/tester/analyst 配带全工具链的自定义镜像。

**构建**：用 `AgentTeams-devflow-kit/docker/Dockerfile.worker` 构建：

```bash
cd AgentTeams-devflow-kit/docker
docker build -f Dockerfile.worker -t devflow-worker:latest .
```

> ⚠️ 坑：MySQL 必须用显式包名 `mysql-server-8.0`，且**不能用 `--no-install-recommends`**（否则不装真正的 server，只装空元包）。

**配置**：在 Worker YAML 的 spec 加 `image: devflow-worker:latest`（implementer/tester/analyst 三个），重新 `apply.sh`。

**移植**：`docker save devflow-worker:latest | gzip > devflow-worker.tar.gz` → 目标机 `docker load -i devflow-worker.tar.gz`（详见部署指南 3.4）。

### 9.9 跨 Worker 协作试跑（implementer 编码 → tester 测试）

> 目的：验证 **implementer 写代码 → 共享区 → tester 跑测试** 的真实多 Agent 协作闭环。

**操作**（Element Web，admin 身份）：

1. **implementer 房间**发：在模板 backend 实现一个加法 API（`GET /api/calc/add?a=2&b=3` 返回 `{"result":5}`），TDD 写 JUnit 测试。
2. **tester 房间**发：用 `test-run` skill 对 backend 执行 `mvn test`，确认通过并写 test_report.txt。

**结果**（2026-08-12 实测）：`BUILD SUCCESS, Tests run: 3, Failures: 0, Errors: 0`——CalcController + CalcControllerTest 同步到共享区，test_report.txt 写入 MinIO。

**这证明了**：多 Agent 通过共享区协作 + 真实测试由机制保证（核心差异化）。

> ✅ 走到这里，文件共享读写链路就通了——Worker 之间可以通过 MinIO 共享区协作。

---

## 十、完整流水线跑通（端到端 + 每个 Worker 的提示语）

> 目标：把 DevFlow Kit 的 14 节点流水线完整跑通（运费计算功能）。
> 实际执行于 2026-08-13，**手动驱动**（admin 在 Element Web 逐个给对应 Worker 发任务）。
> 以下消息模板可直接复制使用，把「运费计算」替换成你的需求即可。

### 10.1 前提

- 8 个 Worker + 2 个 Team 已建好（见七）
- 11 个 Skill 已分发（见八）
- implementer/tester/analyst 用了自定义镜像（Java/Maven，见 9.8）
- 模板工程在共享区 `shared/projects/devflow-template/`

### 10.2 逐节点提示语（admin 按顺序发）

> 共享区路径统一写 `/root/agentteams-fs/shared/projects/devflow-template/`（下文简称「模板」）。

**① designer（系统设计）**
> 请为模板工程 `/root/agentteams-fs/shared/projects/devflow-template/` 设计一个「运费计算」功能：根据里程（km）、重量（kg）、服务等级（normal/express）计算运费。规则：基础费 5 元含首 3km 和首 5kg；超 3km 每 km 加 2 元；超 5kg 每 kg 加 1 元；express 加收 30%；单笔超 100 元打 9 折；总价不足 5 元按 5 元计。请产出设计文档 `design.md`，包含：模块划分（后端 controller/service、前端 views/api）、数据结构、核心流程、接口契约（/api/**）、边界处理。写入共享区。

**② architect-leader（架构评审）**
> 请评审 `/root/agentteams-fs/shared/projects/devflow-template/design.md` 这份系统设计文档（运费计算功能）。检查：模块划分是否合理、数据结构/接口是否覆盖验收标准、核心流程是否完整、边界处理是否周全、是否存在技术债。输出 JSON：`{"approved": true|false, "issues": "..."}`。

**③ implementer（后端编码）**
> 请基于 `/root/agentteams-fs/shared/projects/devflow-template/design.md` 实现**后端**功能。按设计文档模块划分实现（controller/service/constant/dto/exception），严格按业务规则顺序计算。**重点遵守架构评审意见**：统一 express 加收计算路径、保证明细之和等于最终运费、金额先 setScale(2) 再相加。写 JUnit 测试覆盖正数/负数/零/空/临界值/express/最低价兜底。确保 `mvn test` 全部通过。文件写到 `backend/`。

**④ tester（后端测试）**
> 请用 `test-run` 这个 skill，对 `/root/agentteams-fs/shared/projects/devflow-template/backend/` 执行 `mvn test`，确认运费计算测试全部通过（BUILD SUCCESS、Failures: 0、Errors: 0），把结果写成 `test_report.txt`。

**⑤ implementer（前端编码）**
> 请基于 `/root/agentteams-fs/shared/projects/devflow-template/design.md` 实现**前端 Vue3**：`src/views/FreightCalc.vue`（表单输入里程/重量/服务等级 + 计算按钮 + 结果展示明细）、`src/api/freight.js`（封装 POST /api/freight/calculate）、修改 `src/App.vue` 挂载。金额两位小数，Element Plus 组件，接口契约严格按 design.md。确保 `npm run build` 通过。文件写到 `frontend/`。

**⑥ tester（前端构建）**
> 请用 `test-run` 这个 skill，对 `/root/agentteams-fs/shared/projects/devflow-template/frontend/` 执行 `npm install` 和 `npm run build`，确认构建成功，把结果写成 `frontend_build_report.txt`。

**⑦ reviewer（代码评审）**
> 请用 `code-review` 这个 skill，审查 `/root/agentteams-fs/shared/projects/devflow-template/` 的全栈实现，对照 `design.md`。重点：规则正确性、设计落地、前后端接口一致、架构评审意见落实、测试充分性。输出 JSON：`{"approved": true|false, "issues": "..."}`。

**⑧ analyst（对抗性测试）**
> 请用 `adversarial-test` 这个 skill，对运费计算后端做**独立对抗性测试**：不参考、不复制 implementer 的自写测试，只依据验收标准独立构造攻击性 JUnit 用例（边界值、非法输入、规则组合、精度），写入 backend/src/test 并真实运行 `mvn test`。输出 `adversarial_test_report.txt`。若暴露缺陷如实报告。

**⑨ analyst（缺陷定位）**（若 ⑧ 暴露缺陷）
> 请把对抗测试暴露的缺陷整理成 `defect_report.md`：candidates（文件/行/函数）、root_cause、evidence、fix_suggestion。

**⑩ implementer（带证据修复）**（回流）
> 根据 `defect_report.md` 修复缺陷（如：FreightService.validate() 强制 distance/weight 最多 2 位小数），并补充对应测试。确保 `mvn test` 通过。

**⑪ tester（回归验证）**
> 请用 `test-run` skill 对 backend 重跑 `mvn test`，确认包含对抗用例在内的**全部测试通过**，更新 `test_report.txt`。

**⑫ analyst（影响面分析）**
> 请用 `impact-analysis` 这个 skill，对改动做影响面分析：扫描 backend/frontend 源码结构，产出 `impact_report.md`（模块清单、受影响范围、建议回归范围）。程序化产出，不依赖模型判断。

**⑬ tester（E2E）**
> 请用 `test-run` skill 执行**全栈 E2E**：启动 backend（mvn spring-boot:run）和 frontend（npm run dev），用 Playwright（chromium）真实浏览器测试运费计算页面：打开页面 → 输入里程/重量/服务等级 → 点击计算 → 断言明细与最终运费。输出 `e2e_report.txt` 与截图。

**⑭ quality-leader（质量门禁）**
> 请用 `quality-gate` 这个 skill 做发布前质量门禁复核：审查 `test_report.txt`（后端 + JaCoCo）、`frontend_build_report.txt`、`adversarial_test_report.txt`、`e2e_report.txt`、`impact_report.md`。确认全部真实通过后输出 JSON：`{"approved": true|false, "issues": "..."}`。
> ⚠️ 若报告没更新，先让它执行 `agentteams-sync` 拉最新再复核。

**⑮ devflow-runner（发布）**
> 请用 `verify-release` 这个 skill 执行发布：在 `/root/agentteams-fs/shared/projects/devflow-template/` 下执行 `git init`（如未初始化）、`git add .`、`git commit -m "devflow: 运费计算功能 [ci pass]"`。若未配置 git 身份自动补。

### 10.3 关键结果（实测）

- **对抗测试暴露真实缺陷**：implementer 21 个自写用例全过（自洽盲区），analyst 独立 28 个对抗用例抓到 1 个契约缺陷（distance/weight 未校验 2 位小数）→ 定位 → 带证据回流修复 → 回归全绿
- **质量门禁拦截过期证据**：对抗报告未更新时，quality-leader 正确拒绝放行；`agentteams-sync` 重新同步后通过
- **E2E 真实浏览器验证**：Playwright 打开页面 → 输入里程/重量/等级 → 计算 → 断言明细与最终运费
- **发布**：`git commit "devflow: 运费计算功能 [ci pass]"`（35 文件）

### 10.4 经验

1. **手动驱动可靠**：admin 在每个人房间发任务，流程可控，适合 demo 演示
2. **证据同步时序**：Worker 产出后要 `agentteams-sync` 才更新本地副本；质量门禁强制同步再校验
3. **带证据回流**：缺陷定位报告 → implementer 带结论修复（非推倒重来）

---

## 十一、全自动流水线驱动（run-pipeline.py）

> 用脚本自动给各 Worker 发消息（Matrix API）+ 轮询 MinIO 判断节点完成 + 内容校验 + 自动推进/回流，实现"发一个需求 → 流水线自动跑完"。
> 实测：运费计算、增值税计算两个功能的 1-5 节点均**全自动通过**。

### 11.1 文件位置

| 文件 | 说明 |
|------|------|
| `AgentTeams-devflow-kit/scripts/run-pipeline.py` | 驱动脚本（运行在 controller 容器内）|
| `AgentTeams-devflow-kit/scripts/pipeline.json` | 流水线定义（节点/worker/产物/提示语/fail_to）|

### 11.2 用法（两种触发方式）

**方式一：宿主机脚本（推荐，无需进容器）**

```bash
# 宿主机直接运行，自动复制驱动到工作区并在 controller 内执行
python scripts/run-pipeline-host.py "需求描述" --rules "业务规则" [--max-nodes N]
```

**方式二：在 controller 容器内直接运行**

```bash
# 先复制驱动到挂载点（controller 可见）
cp scripts/run-pipeline.py scripts/pipeline.json ~/agentteams-manager/

docker exec agentteams-controller bash -c 'cd /root/agentteams-fs/agents/manager && \
  PYTHONIOENCODING=utf-8 python3 -u run-pipeline.py "需求描述" \
  --rules "业务规则" [--max-nodes N] [--dry-run]'
```

> 两种方式等价。宿主机脚本通过 `PIPELINE_REQ`/`PIPELINE_RULES` 环境变量传参（避免引号转义）。

### 11.3 工作原理

```
读 pipeline.json → 获取 admin token + 各 Worker 房间
→ 对每个节点：给 Worker 房间发提示语（真提及格式）→ 轮询 MinIO 等产物
→ 内容校验（BUILD SUCCESS / approved / Failures: 0）→ 通过推进 / 失败按 fail_to 回流
→ 直到 release
```

### 11.4 pipeline.json 配置要点

| 字段 | 说明 |
|------|------|
| `project_root` | 容器内项目路径（如 `/root/agentteams-fs/shared/projects/devflow-vat`）|
| `nodes[].worker` | 目标 Worker 名 |
| `nodes[].artifact` | 检测该节点完成的产物文件（相对 project_root）|
| `nodes[].prompt` | 发给 Worker 的提示语（`{ROOT}`/`{REQ}`/`{RULES}` 占位符）|
| `nodes[].fail_to` | 失败时回流的节点 |
| `nodes[].success` | 产物内容含这些关键词才算通过（如 `BUILD SUCCESS`）|

> ⚠️ 换需求时：**新建项目目录**（如 devflow-vat），改 `project_root` 和产物名（如 `VatController.java`/`VatCalc.vue`），避免 Worker 记忆旧功能。

### 11.5 ⚠️ 六个关键坑（解决了才跑通全流程）

**坑 1：@mention 格式（最关键）**

发消息必须带 `format: org.matrix.custom.html` + `formatted_body`（permalink 链接）+ `m.mentions.user_ids`，否则 Worker 不识别为"真提及"、不会处理：

```json
{
  "msgtype": "m.text",
  "body": "@worker:server 指令",
  "format": "org.matrix.custom.html",
  "formatted_body": "<a href=\"https://matrix.to/#/@worker:server\">@worker:server</a> 指令",
  "m.mentions": {"user_ids": ["@worker:server"]}
}
```

- ❌ 只写 `@worker:server`（纯文本）→ 收不到
- ❌ 手打 `@@worker:server` → 双@ 不是真提及
- ✅ 必须带 `m.mentions.user_ids` + `formatted_body` permalink

**坑 2：产物同步到 MinIO**

Worker 写了文件不一定自动同步到 MinIO。提示语里必须加：**"产出文件后必须用 file-sync / agentteams-sync 同步到 MinIO 共享区"**，否则驱动轮询不到。

**坑 3：换需求要新项目目录**

Worker 有"记忆"（会话/工作区），换需求要建新项目目录（如 `devflow-vat`），否则它认为"上轮已完成"不重新开发。

**坑 4：success 关键词要匹配实际报告措辞**

驱动按 `nodes[].success` 关键词判断节点通过。必须匹配 Worker 报告的实际措辞：
- 前端构建报告写"**构建成功**"，不是"构建通过"/"BUILD SUCCESS" → success 要包含"构建成功"
- 判定规则：列出所有可能的通过措辞，防止误判失败

**坑 5：Worker 会话污染 → 用 `/new` 重置**

Worker 的 LLM 会话会积累旧需求上下文（如 analyst 一直在讲旧 freight 项目）。**流水线开始时对所有 Worker 发 `/new`** 重置会话，否则后续节点会引用旧项目不处理新任务。

**坑 6：尾部节点提示语要明确指定项目**

影响面/E2E/门禁等节点，提示语必须**明确 {ROOT} 项目 + 禁止复用旧报告**，否则 Worker 会检查旧项目的报告（如 `FreightService.java`）而拒绝重做。

### 11.6 质量门禁回流（拒绝 → 修复 → 重跑）

门禁节点（quality-leader / review / 对抗）拒绝时，驱动自动走 fail_to 回流：

```
节点失败（approved:false 或超时）
  → defect-locate：读失败证据（对抗报告/quality_notes）→ defect_report.md
  → implementer：按 defect_report.md + quality_notes.md 精准修复（含配置问题）
  → 重跑该节点 → 直到通过
```

> 配置类问题（如 JaCoCo 缺失、npm 高危依赖）也要让 implementer 一并修复（改 pom.xml / npm audit fix）。

### 11.7 JaCoCo 覆盖率预置（保证每次有覆盖率）

模板 `backend/pom.xml` 预置 `jacoco-maven-plugin`（prepare-agent + report），`mvn test` 自动生成覆盖率。这样质量门禁**每次都能验证覆盖率 ≥60%**，不会被"JaCoCo 未配置"卡住。

### 11.8 release 判定 + 通知 Manager

- **release 节点**：产物是特殊标记 `RELEASE_DONE`（检查 `.git` 是否出现），判定时直接视为成功（`.git` 出现即 git 初始化完成）
- **完成通知**：流水线全部跑完后，驱动自动给 **Manager 的 DM 房间**发通知，报告"共 X/13 个节点通过"（`MANAGER_ROOM` 常量）

### 11.9 实测结果

| 需求 | 节点 | 结果 |
|------|------|------|
| 运费计算（freight）| 1-5 | ✅ 全过（57 测试）|
| 增值税计算（VAT）| 1-5（全新需求）| ✅ 全过（74 测试）|
| **BMI 计算**（全新需求）| **1-13 完整流水线** | ✅ **全过（含 JaCoCo 覆盖率、E2E、质量门禁、发布、通知 Manager 13/13）** |

---

## 十二、日常启动方法（以后重启电脑）

```
1. 启动 Docker Desktop（AutoStart 默认关，需手动开）
2. 两个容器 unless-stopped 自动拉起（电脑正常重启时）
3. 若手动 docker stop 过 → docker start agentteams-controller agentteams-manager
4. 等约 1 分钟 → 浏览器开 http://127.0.0.1:18088
```

---

## 十三、常用命令速查

| 需求 | 命令 |
|------|------|
| 看容器 | `docker ps` |
| 看 worker | `docker exec agentteams-controller agt get workers` |
| 看 worker skills | `docker exec agentteams-controller agt get workers <name> -o json \| jq '.skills'` |
| 看 controller 日志 | `docker logs agentteams-controller` |
| 进 manager 容器 | `docker exec -it agentteams-manager sh` |
| 拷贝容器文件到宿主 | `docker cp agentteams-manager:/路径/xxx "F:\xxx"` |
| 宿主文件拷进容器 | `docker cp "F:\xxx" agentteams-manager:/路径/` |
| 查看 MinIO 结构 | `docker exec agentteams-controller mc ls agentteams/agentteams-storage/` |

---

## 十四、常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| controller 崩溃：APPSERVICE_AS_TOKEN 缺失 | 安装脚本没生成 token | 见第三章，补两个 token 并重建容器 |
| Manager 不创建（日志：provisioning disabled）| env 值带 `\r` | 见第四章，用 Python+`--env-file` 重建 |
| `docker` 命令找不到 | 老终端 PATH 未更新 | `export PATH="/f/Docker/resources/bin:$PATH"` 或重开终端 |
| Skill 分发后 Worker 不调用 | spec.skills 没更新 | 重新让 Manager 安装并确认 `spec.skills` |
| Worker 容器内文件读不到 | 路径/权限问题 | 用 `docker exec` 确认路径，检查共享区挂载 |

---

*文档生成时间：2026-08-12*
