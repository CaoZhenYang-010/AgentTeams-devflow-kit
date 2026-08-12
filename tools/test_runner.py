# -*- coding: utf-8 -*-
"""测试执行工具 —— 真实运行测试并统计覆盖率（迁移自 devflow-demo/runner.py）"""
import json
import subprocess
import sys
from pathlib import Path

from coverage import parse_python_coverage, parse_jacoco
from git_helper import run


def _run_test_file(workdir, script, with_coverage=False):
    """本地真实运行指定测试文件，返回 (ok, report)。coverage 可用时附加覆盖率，不可用则降级。"""
    workdir = Path(workdir)
    rc, out, err = run(workdir, sys.executable, "-m", "coverage", "run", "--source=.", script)
    if "No module named coverage" in err:
        rc, out, err = run(workdir, sys.executable, script)
        report = f"{out}\n{err}".strip() or "(无输出)"
        coverage_note = "（coverage 未安装，未统计覆盖率）"
    else:
        report = f"{out}\n{err}".strip() or "(无输出)"
        run(workdir, sys.executable, "-m", "coverage", "json")  # 生成 coverage.json
        cov_path = workdir / "coverage.json"
        coverage_note = (parse_python_coverage(cov_path.read_text(encoding="utf-8"))
                         if cov_path.exists() else "")
    if with_coverage and coverage_note:
        report += "\n\n[覆盖率] " + coverage_note
    # 只信 stdout 中的通过标记，不检查合并文本——失败的 traceback 可能含源码行里的
    # "ALL TESTS PASSED" 字样，若按合并文本判断会误判为通过
    ok = (rc == 0) and ("ALL TESTS PASSED" in out)
    return ok, report


def run_backend_tests(backend_dir):
    """在 work/backend 真实运行 mvn test + JaCoCo 覆盖率，返回 (ok, report)。"""
    backend = Path(backend_dir)
    if not (backend / "pom.xml").exists():
        return False, "缺少 backend/pom.xml（后端工程未初始化）"
    rc, out, err = run(backend, "mvn", "test")
    report = f"{out}\n{err}".strip() or "(无输出)"
    rc2, _o, _e = run(backend, "mvn", "jacoco:report")
    if rc2 == 0:
        cov_xml = backend / "target" / "site" / "jacoco" / "jacoco.xml"
        if cov_xml.exists():
            cov_note = parse_jacoco(cov_xml.read_text(encoding="utf-8"))
            if cov_note:
                report += "\n\n[覆盖率] " + cov_note
    ok = rc == 0
    return ok, report


def run_frontend_build(frontend_dir):
    """在 work/frontend 真实运行 npm install + npm run build，返回 (ok, report)。"""
    frontend = Path(frontend_dir)
    if not (frontend / "package.json").exists():
        return False, "缺少 frontend/package.json"
    rc, out, err = run(frontend, "npm", "install")
    if rc != 0:
        report = f"{out}\n{err}".strip() or "(无输出)"
        return False, f"npm install 失败：{report[-200:]}"
    rc, out, err = run(frontend, "npm", "run", "build")
    report = f"{out}\n{err}".strip() or "(无输出)"
    ok = rc == 0
    if ok:
        report = "前端构建通过\n" + report
    return ok, report
