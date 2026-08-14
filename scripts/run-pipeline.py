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
import json, re, subprocess, sys, time, urllib.parse, uuid, os

MATRIX = "http://127.0.0.1:6167"
MC_ALIAS = "agentteams/agentteams-storage"
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.json")


def get_manager_room(token):
    """动态发现 admin 与 manager 的 DM 房间（含 @manager 的小房间）。换电脑也适用。"""
    import urllib.parse as up
    r = sh("curl", "-s", f"{MATRIX}/_matrix/client/v3/joined_rooms",
           "-H", f"Authorization: Bearer {token}")
    rooms = json.loads(r.stdout).get("joined_rooms", [])
    found = []
    for room in rooms:
        enc = up.quote(room, safe="")
        mr = sh("curl", "-s", f"{MATRIX}/_matrix/client/v3/rooms/{enc}/joined_members",
                "-H", f"Authorization: Bearer {token}")
        members = json.loads(mr.stdout).get("joined", {})
        ids = list(members.keys())
        if any("manager" in u for u in ids) and len(ids) <= 3:
            found.append((len(ids), room))
    # 优先返回 2 人纯 DM（admin+manager），否则返回任意含 manager 的小房间
    found.sort(key=lambda x: x[0])
    return found[0][1] if found else None

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
    if node.get("artifact") == "RELEASE_DONE":
        return True  # .git 已出现（git init/commit 完成）即发布成功
    success = node.get("success", [])
    if not success:
        return content != ""  # 只要产物存在就算成功
    if any(k in content for k in success):
        return True
    # 兜底：approved 判定放宽 JSON/YAML 空格与大小写差异（如 "approved" : true / approved: True）
    if any("approved" in k for k in success):
        return bool(re.search(r'approved\s*[":\s]*true', content, re.I))
    return False

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
    # 需求/规则/项目：优先环境变量，否则从 argv 解析（跳过 --flag）
    req = os.environ.get("PIPELINE_REQ", "")
    rules = os.environ.get("PIPELINE_RULES", "")
    req_file = os.environ.get("PIPELINE_REQ_FILE", "")
    project = os.environ.get("PIPELINE_PROJECT", "")
    max_nodes = 999
    dry_run = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--rules" and i + 1 < len(args):
            if not rules:
                rules = args[i + 1]
            i += 2
        elif args[i] == "--req-file" and i + 1 < len(args):
            if not req_file:
                req_file = args[i + 1]
            i += 2
        elif args[i] == "--max-nodes" and i + 1 < len(args):
            max_nodes = int(args[i + 1]); i += 2
        elif args[i] == "--project" and i + 1 < len(args):
            if not project:
                project = args[i + 1]
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True; i += 1
        elif args[i].startswith("--"):
            i += 1
        elif not req:
            req = args[i]; i += 1
        else:
            i += 1
    # 复杂需求：从文件读取（不受命令行长度限制）
    if req_file:
        with open(req_file, encoding="utf-8") as f:
            req = f.read()
    if not req:
        print("用法: python3 run-pipeline.py \"需求\" [--rules \"规则\"] [--req-file 文件] [--max-nodes N] [--dry-run]")
        sys.exit(1)

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    root = cfg["project_root"]
    # 项目路径可参数化：PIPELINE_PROJECT 环境变量或 --project 参数覆盖（换需求用新项目目录）
    if project:
        root = f"/root/agentteams-fs/shared/projects/{project}"
        cfg["project_root"] = root
        print(f"[流水线] 使用项目目录: {root}")
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

    # 运行前重置所有 Worker 会话（清除跨功能上下文污染，否则 Worker 会卡在旧需求）
    if not dry_run:
        print("[流水线] 重置 Worker 会话（/new）...")
        for w, room in rooms.items():
            send_message(token, room, "/new", users.get(w))
            time.sleep(6)

    idx = 0
    passed_count = 0
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

        # 重试机制：LLM Worker 会话可能忙/混淆，超时后重新派发（最多 2 次）
        retry = 0
        while not appeared and retry < 2 and not node.get("skip_if_no_failure"):
            print(f"  ↻ 节点 {nid} 超时，重试第 {retry+1} 次...")
            send_message(token, rooms[worker], prompt, users.get(worker))
            content, appeared = wait_artifact(root, node, node.get("timeout", 120))
            retry += 1

        if not appeared:
            if node.get("skip_if_no_failure"):
                print(f"  ⏭ {nid} 无产物但标记为跳过（无失败场景），视为通过")
                passed_count += 1
                idx += 1
                continue
            print(f"  ✗ 节点 {nid} 超时无产物")
            idx = handle_failure(node, token, rooms, users, root, node_map, req, rules, content)
            continue

        ok = check_success(node, content)
        if ok:
            print(f"  ✓ {nid} 通过")
            passed_count += 1
            idx += 1
        else:
            print(f"  ✗ {nid} 产物存在但未通过内容校验")
            idx = handle_failure(node, token, rooms, users, root, node_map, req, rules, content)
    else:
        print("[流水线] 超过最大迭代次数（疑似死循环）")
        sys.exit(1)

    print("\n[流水线] 全部节点完成 ✅")
    print(f"产物在: {root}")

    # 通知 Manager：流水线完成 + 通过节点数（可选步骤，失败不影响已完成的流水线结果）
    notify = (f"流水线执行完成：共 {passed_count}/{len(nodes)} 个节点通过。"
              f"需求「{req[:40]}」，产物在 {root}。")
    if not dry_run:
        try:
            mgr_room = get_manager_room(token)
            if mgr_room:
                send_message(token, mgr_room, notify)
                print(f"[通知] 已发送给 Manager: {notify}")
            else:
                print(f"[通知] 未找到 Manager DM 房间，跳过通知")
        except Exception as e:
            print(f"[通知] 发送失败（不影响流水线结果）: {e}")


def handle_failure(node, token, rooms, users, root, node_map, req, rules, content=""):
    """节点失败回流（尊重 fail_to 语义）。

    - fail_to 是上游产物节点（如 design）：评审/设计类驳回，回流到该节点重做产物（带驳回意见），
      而不是让 implementer 改代码——否则设计缺陷永远修不掉，形成死循环。
    - fail_to 是 defect-locate：测试/构建/门禁类失败，走缺陷定位 → implementer 修复 → 重跑原节点。
    """
    target = node.get("fail_to")
    if not target:
        print(f"  节点 {node['id']} 失败且无 fail_to，终止。")
        sys.exit(1)
    target_idx = list(node_map.keys()).index(target)
    print(f"  失败 → 按 fail_to 回流到 {target}")

    # 评审/设计类驳回：把失败证据发给上游 worker，让其修正产物，回流重做
    if target != "defect-locate":
        if content:
            back = (f"你的产物被 {node['id']} 驳回。驳回意见如下，请据此修正你的产出（写入 {root}/）"
                    f"并用 file-sync 同步到 MinIO：\n{content[:2000]}")
            worker = node_map[target]["worker"]
            send_message(token, rooms[worker], back, users.get(worker))
            print(f"  已把驳回意见发给 {worker}，等待其修正产物...")
            time.sleep(120)
        return target_idx

    # 缺陷类失败：1. 缺陷定位（读取失败证据：对抗测试报告 或 质量门禁意见 quality_notes.md）
    dl = node_map.get("defect-locate")
    if dl:
        dl_prompt = (f"请分析 {root}/ 下的失败证据（若有对抗测试报告 adversarial_test_report.txt，"
                     f"或质量门禁意见 quality_notes.md），把问题整理成 defect_report.md 写入 {root}/"
                     f"并用 file-sync 同步到 MinIO。包含：root_cause、evidence、fix_suggestion。")
        send_message(token, rooms[dl["worker"]], dl_prompt, users.get(dl["worker"]))
        _, appeared = wait_artifact(root, dl, dl.get("timeout", 300))
        print(f"  缺陷定位报告{'已产出' if appeared else '未产出'}")
        if not appeared:
            sys.exit("缺陷定位失败，终止")

    # 2. 修复（implementer 带证据精准修复，含配置问题如 JaCoCo/npm 漏洞）
    fix_prompt = (f"根据 {root}/defect_report.md（以及 {root}/quality_notes.md 质量门禁意见）修复问题。"
                  f"带证据精准修复；若是配置/依赖问题（如 pom.xml 缺 JaCoCo 插件、npm 高危依赖漏洞），"
                  f"一并修复（如 pom.xml 加 jacoco-maven-plugin 并执行 mvn jacoco:report、npm audit fix）。"
                  f"确保 mvn test 通过后，用 file-sync 把改动同步到 MinIO，报告完成。")
    fix_worker = "implementer"
    send_message(token, rooms[fix_worker], fix_prompt, users.get(fix_worker))
    print(f"  已通知 {fix_worker} 按缺陷/门禁意见修复，等待 180s...")
    time.sleep(180)

    # 3. 返回重跑原失败节点
    return list(node_map.keys()).index(node["id"])


if __name__ == "__main__":
    main()
