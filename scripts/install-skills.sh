#!/bin/bash
# 一键把 skills/ 分发给对应 Worker
# 原理：把 Skill 目录复制到 Manager 工作区（worker-skills/），再让 Manager 分发。
# 用法：bash scripts/install-skills.sh
set -e

SKILLS_DIR="$(cd "$(dirname "$0")/../skills" && pwd)"
WORKSPACE="${AGENTTEAMS_WORKSPACE_DIR:-$HOME/agentteams-manager}"
DEST="$WORKSPACE/worker-skills"

echo "=== 复制 Skill 到 Manager 工作区: $DEST ==="
mkdir -p "$DEST"
for d in "$SKILLS_DIR"/*/; do
  name=$(basename "$d")
  echo "  -> $name"
  rm -rf "$DEST/$name"
  cp -r "$d" "$DEST/$name"
done

echo "=== 请通过 Element Web 让 Manager 分发 Skill（或按以下提示） ==="
echo "  在 manager 房间发送："
echo '  请安装 ~/agentteams-manager/worker-skills/ 下的 skill 给对应 Worker，'
echo '  并确认各 Worker 的 spec.skills 已更新。'
echo "完成。"
