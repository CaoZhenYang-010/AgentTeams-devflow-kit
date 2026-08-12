---
name: verify-release
description: Use to verify and release after all gates pass. Commits the work to git with a [ci pass] marker. Does NOT call the LLM.
---

# Verify Release（验证发布）

你是 **Manager**（由 devflow-runner 承担）。所有前置节点通过后，执行发布：

1. 在 `work/` 工作区执行 `git init`（如未初始化）
2. `git add .`
3. `git commit -m "devflow: <需求摘要> [ci pass]"`

## 说明

- 提交信息中的 `[ci pass]` 表示测试门禁已通过，是发布准入标记
- git 提交记录是最终执行证据，供审计使用
- 本节点不调用大模型
- 若本地仓库未配置 git 身份，自动补 `user.name` / `user.email`（不影响用户全局配置）
- `nothing to commit` 视为成功（工作区与仓库一致）
