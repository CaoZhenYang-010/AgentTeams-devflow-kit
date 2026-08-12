# -*- coding: utf-8 -*-
"""影响面分析工具 —— 程序化结构扫描，产出 impact_report.md（迁移自 devflow-demo/runner.py）"""
from pathlib import Path


def analyze_project(workdir):
    """扫描 work/backend 与 work/frontend 的源码文件结构，返回影响面报告文本。

    程序化产出，不依赖 LLM 判断，结果可复现、可审计。
    """
    workdir = Path(workdir)
    lines = ["# 影响面分析（全栈结构扫描 · 程序化产出，非模型判断）\n"]
    for base, label in (("backend/src/main", "后端 Java 实现"),
                        ("backend/src/test", "后端测试"),
                        ("frontend/src", "前端 Vue/JS")):
        d = workdir / base
        lines.append(f"## {label}（{base}）")
        if d.exists():
            files = sorted(p for p in d.rglob("*")
                           if p.is_file() and p.suffix in (".java", ".vue", ".js"))
            if files:
                for p in files:
                    lines.append(f"- `{p.relative_to(workdir)}`")
            else:
                lines.append("- （无源码文件）")
        else:
            lines.append("- （目录不存在）")
    lines.append("\n## 建议回归范围")
    lines.append("- 后端变更：重跑 `mvn test`（结论见 test_report.txt）")
    lines.append("- 前端变更：重跑 `npm run build` 与 E2E（结论见 e2e_report.txt）")
    return "\n".join(lines)
