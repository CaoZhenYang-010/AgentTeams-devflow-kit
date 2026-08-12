# tools/ —— 验证机制确定性工具

这些是 DevFlow Kit 的核心差异化：**验证由确定性工具保证，而非模型自评**。

| 文件 | 用途 |
|------|------|
| `git_helper.py` | git 与命令子进程执行（Windows 兼容 .cmd 解析）|
| `coverage.py` | 覆盖率解析（Python coverage + JaCoCo）|
| `test_runner.py` | 真实运行测试（后端 mvn test / 前端 npm build）|
| `impact_analyzer.py` | 影响面分析（程序化结构扫描）|

> 后续可封装为 MCP Server 挂到 Higress 网关，Worker 通过 MCP 调用；当前先在 Worker 容器内直接执行。
