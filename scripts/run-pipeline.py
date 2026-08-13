#!/usr/bin/env python3
"""OpenClaw 全自动流水线驱动

在 agentteams-controller 容器内执行：
  python3 /root/agentteams-fs/agents/manager/run-pipeline.py "需求描述"

读取 pipeline.json，按节点顺序：
  1. 通过 Matrix API 给目标 Worker 的房间发提示语（模拟 admin 手动驱动）
  2. 轮询 MinIO 检查预期产物是否出现
  3. 用内容关键词判定节点通过/失败
  4. 通过则推进，失败按 fail_to 走缺陷定位 → 修复 → 重跑
"""
import json, subprocess, sys, time, urllib.parse, uuid, os

MATRIX = "http://127.0.0.1:6167"
MC_ALIAS = "agentteams/agentteams-storage"
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.json")

def _load_admin_pass():
    """从同目录 .env 读取管理员密码（.env 不提交，留在本地）。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("AGENTTEAMS_ADMIN_PASSWORD="):
                v = line.split("=", 1)[1].strip()
                return v.strip('"').strip("'")
    return os.environ.get("AGENTTEAMS_ADMIN_PASSWORD", "")

ADMIN_PASS = _load_admin_pass()

def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=30)

# ---------- Matrix ----------
def get_token():
    r = sh("curl", "-s", "-X", "POST", f"{MATRIX}/_matrix/client/v3/login",
           "-H", "Content-Type: application/json",
           "-d", json.dumps({"type": "m.login.password",
                             "identifier": {"type": "m.id.user", "user": "admin"},
                             "password": ADMIN_PASS}))
    return json.loads(r.stdout)["access_token"]

def get_room(token, worker):
    r = sh("agt", "get", "workers", worker, "-o", "json")
    return json.loads(r.stdout)["roomID"]

def send_message(token, room, text, mention=None):
    """发送消息；mention 为 worker 的 matrixUserID 时自动 @ 并带 m.mentions 通知。
    （房间人数 >2 时，不 @ 接收者没人处理——AgentTeams 官方要求）"""
    enc = urllib.parse.quote(room, safe="")
    txn = uuid.uuid4().hex[:16]
    # mention 可能已带 @ 前缀（如 @worker:server），避免拼成 @@
    if mention and not mention.startswith("@"):
        mention = "@" + mention
    body = (f"{mention} " + text) if mention else text
    content = {"msgtype": "m.text", "body": body}
    if mention:
        # 必须带 format/formatted_body(permalink) + m.mentions，否则 Worker 不识别为真提及
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = f'<a href="https://matrix.to/#/{mention}">{mention}</a> ' + text
        content["m.mentions"] = {"user_ids": [mention]}
    payload = json.dumps(content)
    r = sh("curl", "-s", "-X", "PUT",
           f"{MATRIX}/_matrix/client/v3/rooms/{enc}/send/m.room.message/{txn}",
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json", "-d", payload)
    return json.loads(r.stdout).get("event_id", "?")

# ---------- MinIO 产物检测 ----------
def full_path(root, artifact):
    # root 是容器路径（/root/agentteams-fs/...），MinIO 路径要剥离该前缀
    mc_root = root.replace("/root/agentteams-fs/", "")
    if artifact == "RELEASE_DONE":
        return f"{MC_ALIAS}/{mc_root}/.git"
    return f"{MC_ALIAS}/{mc_root}/{artifact}"

def read_artifact(root, artifact):
    if artifact == "RELEASE_DONE":
        return ""
    p = full_path(root, artifact)
    r = sh("mc", "cat", p)
    return r.stdout if r.returncode == 0 else ""

def check_success(node, content):
    """根据节点类型用内容关键词判定成功。"""
    success = node.get("success", [])
    if not success:
        return content != ""  # 只要产物存在就算成功
    return any(k in content for k in success)

def wait_artifact(root, node, timeout):
    """轮询等待节点产物出现，返回 (content, 是否出现)。"""
    artifact = node["artifact"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        if artifact == "RELEASE_DONE":
            if sh("mc", "ls", full_path(root, artifact)).returncode == 0:
                return "", True
        else:
            content = read_artifact(root, artifact)
            if content:
                return content, True
        time.sleep(10)
    return read_artifact(root, artifact) if artifact != "RELEASE_DONE" else "", False

# ---------- 主流程 ----------
def main():
    if len(sys.argv) < 2:
        print("用法: python3 run-pipeline.py \"需求\" [--rules \"规则\"] [--max-nodes N] [--dry-run]")
        sys.exit(1)
    req = sys.argv[1]
    rules = ""
    max_nodes = 999
    dry_run = False
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--rules" and i + 1 < len(args):
            rules = args[i + 1]; i += 2
        elif args[i] == "--max-nodes" and i + 1 < len(args):
            max_nodes = int(args[i + 1]); i += 2
        elif args[i] == "--dry-run":
            dry_run = True; i += 1
        else:
            i += 1

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    root = cfg["project_root"]
    nodes = cfg["nodes"]
    node_map = {n["id"]: n for n in nodes}

    token = get_token()
    print(f"[流水线] 启动，共 {len(nodes)} 个节点。需求: {req[:60]}...")

    # 预取所有 worker 的 roomId + matrixUserID
    rooms, users = {}, {}
    for n in nodes:
        w = n["worker"]
        if w not in rooms:
            data = json.loads(sh("agt", "get", "workers", w, "-o", "json").stdout)
            rooms[w] = data["roomID"]
            users[w] = data["matrixUserID"]
            print(f"[房间] {w} -> {rooms[w]}  ({users[w]})")

    idx = 0
    max_iter = 30
    for _ in range(max_iter):
        if idx >= len(nodes) or idx >= max_nodes:
            break
        node = nodes[idx]
        nid, worker = node["id"], node["worker"]
        prompt = node["prompt"].replace("{ROOT}", root).replace("{REQ}", req).replace("{RULES}", rules)
        print(f"\n[节点 {idx+1}/{len(nodes)}] {nid} -> {worker}")

        if dry_run:
            print(f"  [dry-run] 将发送给 {worker}:\n  {prompt[:100]}...")
            print(f"  [dry-run] 将等待产物: {node['artifact']}")
            idx += 1
            continue

        send_message(token, rooms[worker], prompt, users.get(worker))
        content, appeared = wait_artifact(root, node, node.get("timeout", 300))

        if not appeared:
            print(f"  ✗ 节点 {nid} 超时无产物")
            idx = handle_failure(node, token, rooms, users, root, node_map, req, rules)
            continue

        ok = check_success(node, content)
        if ok:
            print(f"  ✓ {nid} 通过")
            idx += 1
        else:
            print(f"  ✗ {nid} 产物存在但未通过内容校验")
            idx = handle_failure(node, token, rooms, users, root, node_map, req, rules)
    else:
        print("[流水线] 超过最大迭代次数（疑似死循环）")
        sys.exit(1)

    print("\n[流水线] 全部节点完成 ✅")
    print(f"产物在: {root}")


def handle_failure(node, token, rooms, users, root, node_map, req, rules):
    """节点失败：有 fail_to 则走缺陷定位 → 修复 → 重跑该节点。"""
    target = node.get("fail_to")
    if not target:
        print(f"  节点 {node['id']} 失败且无 fail_to，终止。")
        sys.exit(1)
    print(f"  失败 → 走 {target}")

    # 1. 缺陷定位
    dl = node_map.get("defect-locate")
    if dl:
        dl_prompt = dl["prompt"].replace("{ROOT}", root).replace("{REQ}", req).replace("{RULES}", rules)
        send_message(token, rooms[dl["worker"]], dl_prompt, users.get(dl["worker"]))
        _, appeared = wait_artifact(root, dl, dl.get("timeout", 300))
        print(f"  缺陷定位报告{'已产出' if appeared else '未产出'}")
        if not appeared:
            sys.exit("缺陷定位失败，终止")

    # 2. 修复（implementer 带证据重写）
    fix_prompt = (f"根据 {root}/defect_report.md 修复缺陷，带证据精准修复，确保 mvn test 通过后报告完成。")
    fix_worker = "implementer"
    send_message(token, rooms[fix_worker], fix_prompt, users.get(fix_worker))
    print(f"  已通知 {fix_worker} 按缺陷报告修复，等待 120s...")
    time.sleep(120)

    # 3. 返回重跑原失败节点
    return list(node_map.keys()).index(node["id"])


if __name__ == "__main__":
    main()
