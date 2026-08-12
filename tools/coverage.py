# -*- coding: utf-8 -*-
"""覆盖率解析工具 —— Python coverage 与 JaCoCo（迁移自 devflow-demo/runner.py）"""
import json
import xml.etree.ElementTree as ET

COVERAGE_THRESHOLD = 60  # 建议阈值（Demo 阶段为提示，复赛升级为硬门禁）


def parse_python_coverage(json_text):
    """解析 `coverage report --format=json`，返回核心模块覆盖率摘要；解析失败返回空串。"""
    try:
        data = json.loads(json_text)
    except Exception:
        return ""
    files = data.get("files", {})
    core = {name: info for name, info in files.items()
            if not name.startswith("test") and name.endswith(".py")}
    if not core:
        return ""
    pcts = [info.get("summary", {}).get("percent_covered", 0) for info in core.values()]
    avg = sum(pcts) / len(pcts)
    detail = ", ".join(
        f"{name}:{info.get('summary', {}).get('percent_covered', 0):.1f}%"
        for name, info in sorted(core.items()))
    flag = f"  {'≥建议阈值' + str(COVERAGE_THRESHOLD) + '%' if avg >= COVERAGE_THRESHOLD else '低于建议阈值（提示）'}"
    return f"核心模块平均覆盖率 {avg:.1f}%（{detail}）{flag}"


def parse_jacoco(xml_text):
    """解析 JaCoCo jacoco.xml，返回核心模块覆盖率摘要；解析失败返回空串。"""
    try:
        root = ET.fromstring(xml_text)
        pcts, detail = [], []
        for pkg in root.iter("package"):
            counter = {c.get("type"): c for c in pkg.findall("counter")}
            c = counter.get("LINE") or counter.get("INSTRUCTION")
            if c is None:
                continue
            covered = int(c.get("covered", 0))
            missed = int(c.get("missed", 0))
            total = covered + missed
            if total > 0:
                pcts.append(covered / total * 100)
                detail.append(f"{pkg.get('name')}:{covered / total * 100:.1f}%")
        if not pcts:
            return ""
        avg = sum(pcts) / len(pcts)
        flag = f"  {'≥建议阈值' + str(COVERAGE_THRESHOLD) + '%' if avg >= COVERAGE_THRESHOLD else '低于建议阈值（提示）'}"
        return f"后端 JaCoCo 覆盖率 {avg:.1f}%（{', '.join(detail)}）{flag}"
    except Exception:
        return ""
