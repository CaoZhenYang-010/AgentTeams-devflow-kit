#!/usr/bin/env python3
"""宿主机运行全自动流水线。

用法（宿主机，无需进 controller 容器）：
  python scripts/run-pipeline-host.py "需求" --rules "业务规则"

流程：复制驱动到挂载工作区 → docker exec 在 controller 内运行
     （需求/规则经环境变量 PIPELINE_REQ/PIPELINE_RULES 传入，避免引号转义）
"""
import os
import sys
import shutil
import subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "agentteams-manager")
CONTROLLER = "agentteams-controller"
CONTAINER_WORK = "/root/agentteams-fs/agents/manager"
os.environ["MSYS_NO_PATHCONV"] = "1"  # 防止 Git Bash 转义路径


def main():
    if len(sys.argv) < 2:
        print('用法: python run-pipeline-host.py "需求" [--rules "规则"] [--max-nodes N]')
        sys.exit(1)
    req = sys.argv[1]
    rules, max_nodes = "", ""
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--rules" and i + 1 < len(args):
            rules = args[i + 1]
            i += 2
        elif args[i] == "--max-nodes" and i + 1 < len(args):
            max_nodes = args[i + 1]
            i += 2
        else:
            i += 1

    # 1. 复制驱动到挂载工作区（保证最新）
    for f in ("run-pipeline.py", "pipeline.json"):
        src = os.path.join(REPO, f)
        dst = os.path.join(WORKSPACE, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"[准备] 已复制 {f} → 工作区")
        else:
            print(f"[警告] 缺少 {f}")

    # 2. 组装 docker exec 命令（需求/规则经环境变量传入）
    mn = f" --max-nodes {max_nodes}" if max_nodes else ""
    cmd = (
        f'docker exec -e "PIPELINE_REQ={req}" -e "PIPELINE_RULES={rules}" '
        f'{CONTROLLER} bash -c "cd {CONTAINER_WORK} && '
        f'PYTHONIOENCODING=utf-8 python3 -u run-pipeline.py{mn}"'
    )
    print(f"[运行] 全自动流水线启动...")
    rc = subprocess.call(cmd, shell=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
