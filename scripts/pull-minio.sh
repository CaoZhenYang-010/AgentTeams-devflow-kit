#!/bin/bash
# 把 MinIO 共享区的内容拉取到本地宿主机（供查看 / 审阅 / git 提交）
# 原理：mc cp 到 controller 的挂载点（/root/agentteams-fs/agents/manager），
#       该挂载点自动同步到宿主机 C:\Users\<用户名>\agentteams-manager\minio-pulled\
# 用法：bash scripts/pull-minio.sh <minio路径>
#   例：bash scripts/pull-minio.sh shared/projects/devflow-template
#       bash scripts/pull-minio.sh shared/projects        # 拉整个 projects
#       bash scripts/pull-minio.sh shared/runs            # 拉所有 run 产物
export MSYS_NO_PATHCONV=1

CONTROLLER="agentteams-controller"
SRC="${1:?用法: bash scripts/pull-minio.sh <minio路径>，如 shared/projects/devflow-template}"
DEST="/root/agentteams-fs/agents/manager/minio-pulled"

# 宿主上对应的本地目录（Windows）
HOST_DEST="${AGENTTEAMS_WORKSPACE_DIR:-$HOME/agentteams-manager}/minio-pulled"

echo "=== 拉取 MinIO: agentteams/agentteams-storage/$SRC ==="
docker exec "$CONTROLLER" mc cp -r "agentteams/agentteams-storage/$SRC" "$DEST/" \
  || { echo "[FAIL] 拉取失败，检查 MinIO 路径是否存在"; exit 1; }

echo "=== 完成 ==="
echo "本地位置: $HOST_DEST/$(basename "$SRC")"
