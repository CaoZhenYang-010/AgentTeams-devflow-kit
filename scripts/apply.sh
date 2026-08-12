#!/bin/bash
# 一键应用所有 Agent/Team 定义到 AgentTeams
# 顺序：先 Worker（被引用），再 Team（引用 Worker）
# 原理：复制 agents/*.yaml 到 controller 挂载的工作区，再从容器内 agt apply
export MSYS_NO_PATHCONV=1

CONTROLLER="agentteams-controller"
WORKSPACE="${AGENTTEAMS_WORKSPACE_DIR:-$HOME/agentteams-manager}"
STAGE="$WORKSPACE/apply-yamls"
AGENTS_DIR="$(cd "$(dirname "$0")/../agents" && pwd)"
CONTAINER_STAGE="/root/agentteams-fs/agents/manager/apply-yamls"

echo "=== 复制 YAML 到工作区 ==="
mkdir -p "$STAGE"
for f in "$AGENTS_DIR"/*.yaml; do
  cp "$f" "$STAGE/"
done

apply_all() {
  for f in "$@"; do
    name=$(basename "$f")
    echo "  -> $name"
    docker exec "$CONTROLLER" agt apply -f "$CONTAINER_STAGE/$name" \
      || echo "  [WARN] $name 失败"
  done
}

echo "=== 第 1 步：应用 Worker（8 个） ==="
apply_all "$AGENTS_DIR"/worker-*.yaml

echo "=== 第 2 步：应用 Team（2 个，依赖 Worker） ==="
apply_all "$AGENTS_DIR"/team-*.yaml

echo "=== 验证 ==="
docker exec "$CONTROLLER" agt get workers
docker exec "$CONTROLLER" agt get teams
echo "完成。"
