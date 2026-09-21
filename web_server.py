#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8080

class AtomDashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            index_path = os.path.join(ROOT, "web", "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
                return

        if self.path == "/api/status":
            self.send_json(self.get_system_status())
            return

        if self.path == "/api/tasks":
            self.send_json(self.get_tasks_data())
            return

        if self.path == "/api/workspace":
            self.send_json(self.get_workspace_files())
            return

        if self.path == "/api/logs":
            self.send_json(self.get_recent_logs())
            return

        if self.path == "/api/run_test":
            res = self.execute_unit_tests()
            self.send_json(res)
            return

        # Fallback to default static file handling
        return super().do_GET()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if self.path == "/api/run_test":
            res = self.execute_unit_tests()
            self.send_json(res)
            return

        if self.path == "/api/dispatch":
            res = self.dispatch_agent_task(payload)
            self.send_json(res)
            return

        self.send_response(404)
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def get_system_status(self):
        # 1. GPU info
        gpu_info = {
            "name": "NVIDIA RTX 6000 Ada Generation",
            "vram_total_mb": 49140,
            "vram_used_mb": 0,
            "temperature_c": 38,
            "driver_status": "Ready (Kernel 6.17 Module Built)"
        }
        try:
            res = subprocess.run("nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu --format=csv,noheader,nounits",
                                 shell=True, capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split(",")
                gpu_info["name"] = parts[0].strip()
                gpu_info["vram_total_mb"] = int(parts[1].strip())
                gpu_info["vram_used_mb"] = int(parts[2].strip())
                gpu_info["temperature_c"] = int(parts[3].strip())
                gpu_info["driver_status"] = "Active"
        except Exception:
            pass

        # 2. Ollama info
        ollama_info = {"running": False, "version": "0.34.2", "models": []}
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                ollama_info["running"] = True
                ollama_info["models"] = [m.get("name") for m in data.get("models", [])]
        except Exception:
            pass

        # 3. Tasks stats
        tasks_dir = os.path.join(ROOT, "tasks")
        status_counts = {"todo": 0, "doing": 0, "done": 0, "blocked": 0, "total": 0}
        if os.path.exists(tasks_dir):
            for f in os.listdir(tasks_dir):
                if f.endswith(".md"):
                    status_counts["total"] += 1
                    try:
                        with open(os.path.join(tasks_dir, f), "r", encoding="utf-8") as tf:
                            txt = tf.read()
                            if "status: done" in txt:
                                status_counts["done"] += 1
                            elif "status: blocked" in txt:
                                status_counts["blocked"] += 1
                            elif "status: doing" in txt:
                                status_counts["doing"] += 1
                            else:
                                status_counts["todo"] += 1
                    except Exception:
                        status_counts["todo"] += 1

        # 4. Message counts
        done_dir = os.path.join(ROOT, "done")
        done_count = len([f for f in os.listdir(done_dir) if f.endswith(".md")]) if os.path.exists(done_dir) else 0

        return {
            "gpu": gpu_info,
            "ollama": ollama_info,
            "tasks": status_counts,
            "messages_processed": done_count,
            "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_sec": int(time.time() - SERVER_START_TIME)
        }

    def get_tasks_data(self):
        tasks = []
        tasks_dir = os.path.join(ROOT, "tasks")
        if not os.path.exists(tasks_dir):
            return []
        for f in sorted(os.listdir(tasks_dir)):
            if f.endswith(".md"):
                fp = os.path.join(tasks_dir, f)
                try:
                    with open(fp, "r", encoding="utf-8") as tf:
                        content = tf.read()
                    tid = f.replace(".md", "")
                    title = "Task"
                    status = "todo"
                    assigned = "ENG"
                    for line in content.split("\n"):
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip()
                        elif line.startswith("status:"):
                            status = line.split(":", 1)[1].strip()
                        elif line.startswith("assigned_to:"):
                            assigned = line.split(":", 1)[1].strip()
                    tasks.append({
                        "id": tid,
                        "title": title,
                        "status": status,
                        "assigned_to": assigned,
                        "filename": f
                    })
                except Exception:
                    pass
        return tasks

    def get_workspace_files(self):
        files = []
        # Check both workspace and workspace/workspace
        search_dirs = [os.path.join(ROOT, "workspace"), os.path.join(ROOT, "workspace", "workspace")]
        seen = set()
        for d in search_dirs:
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.endswith(".py") or f.endswith(".json") or f.endswith(".md"):
                        if f in seen:
                            continue
                        seen.add(f)
                        fp = os.path.join(d, f)
                        try:
                            with open(fp, "r", encoding="utf-8") as file_obj:
                                content = file_obj.read()
                            files.append({
                                "name": f,
                                "path": os.path.relpath(fp, ROOT),
                                "size": len(content),
                                "lines": len(content.split("\n")),
                                "content": content
                            })
                        except Exception:
                            pass
        return files

    def get_recent_logs(self):
        logs = {"ENG": [], "PM": []}
        for role in ["ENG", "PM"]:
            lp = os.path.join(ROOT, "ledger", f"agent_{role}.log")
            if os.path.exists(lp):
                with open(lp, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                    logs[role] = [l.strip() for l in lines[-25:]]
        return logs

    def execute_unit_tests(self):
        # Prefer workspace/workspace if it has test_todo.py, else workspace
        cwd = os.path.join(ROOT, "workspace", "workspace")
        if not os.path.exists(os.path.join(cwd, "test_todo.py")):
            cwd = os.path.join(ROOT, "workspace")

        start = time.time()
        try:
            res = subprocess.run([sys.executable, "-m", "unittest", "test_todo.py"],
                                 cwd=cwd, capture_output=True, text=True, timeout=15)
            elapsed = time.time() - start
            return {
                "success": (res.returncode == 0),
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "elapsed_ms": int(elapsed * 1000),
                "cwd": cwd
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "elapsed_ms": 0,
                "cwd": cwd
            }

    def dispatch_agent_task(self, payload):
        role = payload.get("role", "ENG").upper()
        task_id = payload.get("task", "TASK-0001")
        instruction = payload.get("instruction", "Execute task deliverables.")

        # Use AgentRuntime to send message safely
        from agent import AgentRuntime
        try:
            sender_role = "PM" if role == "ENG" else "ENG"
            sender = AgentRuntime(sender_role, backend="ollama", root=ROOT)
            msg_id, msg_p = sender.send_message(role, None, task_id, "assign" if sender_role=="PM" else "report", instruction)
            
            # Now trigger 1 turn of the recipient agent
            agent = AgentRuntime(role, model="gemma4:e4b", backend="ollama", root=ROOT)
            ok = agent.process_one_message()
            return {
                "success": ok,
                "msg_id": msg_id,
                "role": role,
                "task": task_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

SERVER_START_TIME = time.time()
PORTS = [8080, 3000, 3001]

import socket

class DualStackServer(HTTPServer):
    address_family = socket.AF_INET6
    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()

def serve_on_port(port):
    try:
        httpd = DualStackServer(("::", port), AtomDashboardHandler)
        print(f"[ATOM DASHBOARD] Server listening at [::]:{port} (Dual-stack IPv4+IPv6)")
        httpd.serve_forever()
    except Exception as e:
        try:
            httpd = HTTPServer(("0.0.0.0", port), AtomDashboardHandler)
            print(f"[ATOM DASHBOARD] Server listening at 0.0.0.0:{port} (IPv4)")
            httpd.serve_forever()
        except Exception as e2:
            print(f"[ATOM DASHBOARD] Port {port} binding failed: {e2}")

def run_server():
    import threading
    threads = []
    for p in PORTS:
        t = threading.Thread(target=serve_on_port, args=(p,), daemon=True)
        t.start()
        threads.append(t)
    print(f"[ATOM DASHBOARD] Multi-port server running on ports: {PORTS}")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_server()
