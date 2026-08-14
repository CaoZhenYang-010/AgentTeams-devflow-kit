# AgentTeams DevFlow Kit

基于 **AgentTeams**（原名 HiClaw）框架的**软件研发全流程多 Agent 协同系统**，支持**全自动流水线**：发一个需求，13 个节点自动跑完（设计→编码→测试→评审→对抗→E2E→质量门禁→发布→通知 Manager）。

## 一句话定位

> 在 AgentTeams 上构建一支"AI 研发团队"，用 `run-pipeline.py` 一键驱动：`designer / implementer / tester / reviewer / analyst` 完成 **需求→设计→架构把关→编码→测试→对抗→缺陷定位→影响面→E2E→质量门禁→发布** 完整闭环，验证机制（真实测试、**JaCoCo 覆盖率**、对抗测试、缺陷定位、影响面分析）全部由确定性工具保证，而非模型自评。

## 目录结构

```
AgentTeams-devflow-kit/
├── workflow/                 # 流水线定义
│   ├── workflow.yaml         # 声明式流水线（节点/角色/回流规则）
│   └── devflow-pipeline/     # devflow-runner 编排 Skill
├── agents/                   # 8 个 Worker + 2 个 Team 定义
├── skills/                   # 11 个 Skill（SKILL.md）
├── tools/                    # 验证机制确定性工具（test/coverage/impact/git）
├── scripts/
│   ├── apply.sh              # 一键创建 Worker/Team
│   ├── install-skills.sh     # 一键分发 Skill
│   ├── run-pipeline.py       # ★ 全自动流水线驱动（Matrix 派发 + MinIO 轮询 + 回流）
│   ├── pipeline.json         # ★ 流水线驱动配置（节点/产物/提示语/success 判定）
│   ├── pull-minio.sh         # 拉取 MinIO 产物到本地
│   └── run.sh                # 手动驱动入口
├── docker/                   # 自定义 Worker 镜像（Java+Maven+MySQL+Playwright）
├── template-project/         # 被开发的全栈工程模板（含 JaCoCo 覆盖率）
├── screenshots/              # 流水线运行截图 + description
└── docs/                     # 架构 / 调试手册 / Identity 清单 / 作品简介 / 核心 Skill 清单
```

## 角色清单（8 个 Agent）

| Agent | 类型 | 职责 | 关键 Skill |
|-------|------|------|-----------|
| devflow-runner | Worker（编排）| 读 workflow.yaml、驱动流水线、发布 | devflow-pipeline / verify-release |
| designer | Worker | 系统设计（全栈模块/接口/边界）| system-design |
| implementer | Worker | TDD 编码（后端 SpringBoot + 前端 Vue3）| tdd-coding |
| tester | Worker | 测试/覆盖率/前端构建/E2E | test-run |
| reviewer | Worker | 代码评审 | code-review |
| analyst | Worker | 对抗测试/缺陷定位/影响面分析 | adversarial-test / defect-locate / impact-analysis |
| architect-leader | Team Leader | 编码前架构评审门禁 | architecture-review |
| quality-leader | Team Leader | 发布前质量门禁 | quality-gate |

> Manager 由 AgentTeams 框架提供，负责创建/调度上述 Agent。

## 快速开始

### ① 环境搭建（一次性）

```bash
# 1. 创建 8 个 Worker + 2 个 Team
./scripts/apply.sh

# 2. 分发 11 个 Skill
./scripts/install-skills.sh
```

> implementer/tester/analyst 需使用自定义镜像（Java/Maven/MySQL/Playwright），见 `docker/`。

### ② 全自动跑流水线（一键）

```bash
# 在 agentteams-controller 容器内运行
docker exec agentteams-controller bash -c \
  'cd /root/agentteams-fs/agents/manager && \
   PYTHONIOENCODING=utf-8 python3 -u run-pipeline.py "需求描述" \
   --rules "业务规则"'

# 例如：
#   python3 -u run-pipeline.py "BMI 计算功能" \
#     --rules "输入身高体重，计算 BMI=体重/身高^2，输出分类"
```

> 流水线自动完成 13 个节点，完成后通知 Manager 通过节点数。详细用法见 `docs/agentTeams调试步骤.md` 第十一章。

### ③ 手动驱动（备选）

在 Element Web 逐节点给对应 Worker 发消息，流程可全程人工介入。

## 实测结果（全自动）

| 需求 | 范围 | 结果 |
|------|------|------|
| 运费计算（freight）| 1-5 节点 | ✅ 全过（57 测试）|
| 增值税计算（VAT）| 1-5 节点 | ✅ 全过（74 测试）|
| **BMI 计算** | **1-13 完整流水线** | ✅ **全过（JaCoCo 覆盖率 + E2E + 质量门禁 + 发布 + 通知 Manager 13/13）** |

## 参考文档

1. 调试手册（含所有坑）：`docs/agentTeams调试步骤.md`
2. 架构说明：`docs/architecture.md`
3. Agent Identity 清单（8 个 Agent 身份/职责）：`docs/Agent_Identity_清单.md`
4. 核心 Skill 清单（11 个 Skill 的用途/输入输出/失败处理/协同关系）：`docs/核心skill清单.md`
5. 作品简介（问题/方案/创新/复用/进展）：`docs/作品简介.md`
6. AgentTeams 官方仓库：https://github.com/agentscope-ai/AgentTeams/tree/main
