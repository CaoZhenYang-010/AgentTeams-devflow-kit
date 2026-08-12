#!/bin/bash
# 发起一次 DevFlow 流水线运行
# 用法：bash scripts/run.sh "一句话需求"
set -e

TASK="${1:?用法: bash scripts/run.sh \"一句话需求\"}"

echo "=== 向 devflow-runner 发起流水线运行 ==="
echo "需求：$TASK"

# 方式 A：通过 Matrix 房间给 devflow-runner 发任务（推荐，可观测）
#   打开 Element Web，在 devflow-runner 的房间发送上面的需求即可。

# 方式 B：通过 Manager 房间让 Manager 调度（若走 Manager 编排）
echo
echo "请在 Element Web 中，向 devflow-runner 的房间发送以下消息："
echo "------------------------------------------------------------"
echo "$TASK"
echo "------------------------------------------------------------"
echo "devflow-runner 会读取 workflow.yaml 驱动完整流水线。"
