"""Smoke test: exercises the API manually (login, add repo, create task)."""

import json
import urllib.request
import urllib.error
import sys

BASE = "http://localhost:9000"


def api(method, path, data=None, token=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        r = urllib.request.urlopen(req)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return {"error": e.code, "detail": json.loads(body)}
        except json.JSONDecodeError:
            return {"error": e.code, "detail": body}


def main():
    # 1. Login
    print("=== 1. LOGIN ===")
    resp = api("POST", "/api/auth/login", {"username": "admin", "password": "111325"})
    if "access_token" not in resp:
        print(f"  FAIL: {resp}")
        sys.exit(1)
    token = resp["access_token"]
    print(f"  OK: token = {token[:20]}...")

    # 2. Add repo
    print("\n=== 2. ADD REPO ===")
    resp = api("POST", "/api/repos", {
        "platform": "github",
        "url": "https://github.com/dubsaider/PC-Guardian-Server",
        "token": "",
        "autonomy": "full_auto",
        "watch_labels": ["autoproger"],
        "default_branch": "master",
    }, token)
    if "error" in resp:
        print(f"  FAIL: {resp}")
        sys.exit(1)
    repo_id = resp["id"]
    print(f"  OK: repo_id = {repo_id}, platform = {resp['platform']}, autonomy = {resp['autonomy']}")

    # 3. Create task (simulate an issue)
    print("\n=== 3. CREATE TASK ===")
    resp = api("POST", "/api/tasks/create", {
        "repo_id": repo_id,
        "issue_number": 1,
        "issue_title": "Add health check endpoint",
        "issue_body": "Add a GET /health endpoint that returns JSON with status ok.",
        "issue_labels": ["autoproger"],
    }, token)
    if "error" in resp:
        print(f"  FAIL: {resp}")
        sys.exit(1)
    task_id = resp["id"]
    print(f"  OK: task_id = {task_id}, status = {resp['status']}")

    # 4. List tasks
    print("\n=== 4. LIST TASKS ===")
    tasks = api("GET", "/api/tasks", token=token)
    for t in tasks:
        print(f"  [{t['status']:12s}] {t['id']}: {t['issue_title']}")

    # 5. List repos
    print("\n=== 5. LIST REPOS ===")
    repos = api("GET", "/api/repos", token=token)
    for r in repos:
        print(f"  {r['id']}: {r['url']} ({r['platform']}, {r['autonomy']})")

    print(f"\n=== DONE ===")
    print(f"Server: {BASE}")
    print(f"Swagger UI: {BASE}/docs")
    print(f"Repo ID: {repo_id}")
    print(f"Task ID: {task_id}")
    print(f"\nTo run pipeline: POST {BASE}/api/tasks/{task_id}/run")


if __name__ == "__main__":
    main()
