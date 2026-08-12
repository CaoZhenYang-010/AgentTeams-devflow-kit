# -*- coding: utf-8 -*-
"""工具调用层 —— git 与任意命令子进程（迁移自 devflow-demo/tools.py）"""
import shutil
import subprocess


def _resolve_cmd(cmd):
    """Windows 上把 mvn/npm/npx 等 .cmd 命令解析为实际可执行文件。

    subprocess 默认无法直接执行 .cmd/.bat（非 shell 模式），需先经 shutil.which 解析。
    """
    if not cmd:
        return cmd
    return shutil.which(cmd) or cmd


def git(cwd, *args):
    """在指定目录执行 git 命令，返回 (returncode, stdout, stderr)。"""
    cmd = ["git", "-C", str(cwd), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def run(cwd, *cmd):
    """在指定目录运行任意命令，返回 (returncode, stdout, stderr)。

    首个命令在 Windows 上先解析（mvn/npm/npx → 对应 .cmd/.exe 实际路径）。
    """
    args = list(cmd)
    args[0] = _resolve_cmd(args[0])
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr
