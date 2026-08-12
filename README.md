# AgentTeams DevFlow Kit

基于 **AgentTeams**（原名 HiClaw）框架的软件研发全流程多 Agent 协同系统。
从 `devflow-demo`（自研编排原型）迁移而来，以 AgentTeams 的 **Manager – Team Leader – Worker** 分层原语承载研发流水线。

## 一句话定位

> 在 AgentTeams 上构建一支"AI 研发团队"：`devflow-runner` 按 `workflow.yaml` 驱动 designer / implementer / tester / reviewer / analyst 完成 **需求→设计→架构把关→编码→测试→对抗→缺陷定位→影响面→门禁→发布** 完整闭环，验证机制（真实测试、覆盖率、对抗测试、缺陷定位、影响面分析）全部由确定性工具保证，而非模型自评。

## 目录结构

```
AgentTeams-devflow-kit/
├── workflow/                 # 流水线定义 + 编排 Skill
│   ├── workflow.yaml         # 声明式流水线（节点/角色/回流规则）
│   └── devflow-pipeline/     # devflow-runner 的编排 Skill（状态机）
├── agents/                   # 8 个 Agent + 2 个 Team 的声明式定义
├── skills/                   # 11 个 Skill（SKILL.md，供 Worker 使用）
├── tools/                    # 验证机制确定性工具（test/coverage/impact/git）
├── scripts/                  # 一键 apply / 分发 Skill / 发起流水线
├── template-project/         # 被开发的全栈示例工程（引用 stack-template）
└── docs/                     # 架构说明 + 复现步骤
```

## 角色清单（9 个 Agent）

| Agent | 类型 | 职责 | 关键 Skill |
|-------|------|------|-----------|
| devflow-runner | Worker（编排）| 读 workflow.yaml、驱动流水线、维护状态 | devflow-pipeline |
| designer | Worker | 系统设计（全栈模块/接口/边界）| system-design |
| implementer | Worker | TDD 编码（后端 SpringBoot + 前端 Vue3）| tdd-coding |
| tester | Worker | 测试执行/覆盖率/前端构建/E2E | test-run |
| reviewer | Worker | 代码评审 | code-review |
| analyst | Worker | 对抗测试/缺陷定位/影响面分析 | adversarial-test / defect-locate / impact-analysis |
| architect-leader | Team Leader | 编码前架构评审门禁 | architecture-review |
| quality-leader | Team Leader | 发布前质量门禁 | quality-gate |

> Manager 由 AgentTeams 框架提供，负责接收需求、创建/调度上述 Agent。

## 快速开始（步骤）

```bash
# 1. 一键创建 8 个 Agent + 2 个 Team
./scripts/apply.sh

# 2. 一键分发 11 个 Skill 到对应 Worker
./scripts/install-skills.sh

# 3. 发起一个流水线运行
./scripts/run.sh "开发一个运费计费引擎：……"
```

详见 `docs/复现步骤.md`。

## 迁移说明

本包由 `devflow-demo`（自研 Python 编排引擎）迁移而来，迁移映射见 `MIGRATION-NOTES.md`。
