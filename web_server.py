#!/usr/bin/env python3
import os
import sys
import json
import time
import signal
import subprocess
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

os.environ["no_proxy"] = "127.0.0.1,localhost,::1"
os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8080

def ensure_ollama_daemon():
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=1.5):
            return True
    except Exception:
        pass
    
    import subprocess
    import os
    ollama_path = os.path.expanduser("~/.local/bin/ollama")
    if os.path.exists(ollama_path):
        try:
            subprocess.Popen([ollama_path, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            for _ in range(10):
                time.sleep(0.5)
                try:
                    req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
                    with urllib.request.urlopen(req, timeout=1):
                        return True
                except Exception:
                    pass
        except Exception:
            return False
    return False

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
            index_path = os.path.join(ROOT, "index.html")
            if not os.path.exists(index_path):
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

        if self.path in ("/binasea", "/riteflow", "/autonomous", "/agents", "/web"):
            self.send_response(301)
            self.send_header("Location", self.path + "/")
            self.end_headers()
            return

        if self.path == "/api/status":
            self.send_json(self.get_system_status())
            return

        if self.path == "/api/loop/status":
            self.send_json(self.get_loop_status())
            return

        if self.path == "/api/conversations":
            self.send_json(self.get_conversations())
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
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        return super().do_HEAD()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if self.path == "/api/debug":
            print(f"\n🔥🔥🔥 [BROWSER DEBUG] {json.dumps(payload, indent=2)}\n", flush=True)
            self.send_json({"ok": True})
            return

        if self.path == "/api/loop/start":
            res = self.start_loop()
            self.send_json(res)
            return

        if self.path == "/api/loop/stop":
            res = self.stop_loop()
            self.send_json(res)
            return

        if self.path == "/api/run_test":
            res = self.execute_unit_tests()
            self.send_json(res)
            return

        if self.path == "/api/dispatch":
            res = self.dispatch_agent_task(payload)
            self.send_json(res)
            return

        if self.path == "/api/chat":
            res = self.handle_chat_query(payload)
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

    def get_loop_status(self):
        pid_file = os.path.join(ROOT, "ledger", "daemon.pid")
        state_file = os.path.join(ROOT, "ledger", "daemon_state.json")
        is_running = False
        pid = None
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                is_running = True
            except Exception:
                is_running = False
                pid = None

        state_data = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
            except Exception:
                pass

        return {
            "running": is_running,
            "pid": pid,
            "state": state_data,
            "uptime_sec": state_data.get("uptime_sec", 0) if is_running else 0,
            "round_count": state_data.get("round_count", 0),
            "current_task": state_data.get("current_task", {}),
            "total_messages": state_data.get("total_messages", 0),
            "last_event": state_data.get("last_event", "대기 중 (루프 정지됨)" if not is_running else "자율 가동 중"),
            "last_updated": state_data.get("last_updated", "")
        }

    def start_loop(self):
        status = self.get_loop_status()
        if status.get("running"):
            return {
                "success": True,
                "already_running": True,
                "pid": status.get("pid"),
                "message": f"24시간 자율 가동 루프가 이미 실행 중입니다 (PID: {status.get('pid')})."
            }

        orch_script = os.path.join(ROOT, "continuous_orchestrator.py")
        orch_log = os.path.join(ROOT, "ledger", "orchestrator.log")
        try:
            with open(orch_log, "a", encoding="utf-8") as log_f:
                env_copy = dict(os.environ)
                env_copy["no_proxy"] = "127.0.0.1,localhost,::1"
                env_copy["NO_PROXY"] = "127.0.0.1,localhost,::1"
                proc = subprocess.Popen(
                    [sys.executable, "-u", orch_script, "--model", "gemma4:e4b"],
                    stdout=log_f,
                    stderr=log_f,
                    cwd=ROOT,
                    start_new_session=True,
                    env=env_copy
                )
            time.sleep(1.0)
            pid = proc.pid
            return {
                "success": True,
                "pid": pid,
                "message": f"24시간 자율 가동 루프가 성공적으로 시작되었습니다 (PID: {pid})."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_loop(self):
        pid_file = os.path.join(ROOT, "ledger", "daemon.pid")
        state_file = os.path.join(ROOT, "ledger", "daemon_state.json")
        if not os.path.exists(pid_file):
            return {"success": True, "message": "실행 중인 자율 루프 프로세스가 없습니다."}

        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

            if os.path.exists(pid_file):
                os.remove(pid_file)

            if os.path.exists(state_file):
                try:
                    with open(state_file, "r+", encoding="utf-8") as f:
                        data = json.load(f)
                        data["status"] = "STOPPED"
                        data["last_event"] = "사용자에 의해 일시 중지됨"
                        f.seek(0)
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.truncate()
                except Exception:
                    pass

            return {"success": True, "message": f"24시간 자율 가동 루프가 정상 종료되었습니다 (PID: {pid})."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_conversations(self):
        feed_file = os.path.join(ROOT, "ledger", "conversation_feed.jsonl")
        conversations = []
        if os.path.exists(feed_file):
            try:
                with open(feed_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-60:]:
                        line = line.strip()
                        if line:
                            try:
                                conversations.append(json.loads(line))
                            except Exception:
                                pass
            except Exception:
                pass

        if len(conversations) < 5:
            done_dir = os.path.join(ROOT, "done")
            if os.path.exists(done_dir):
                done_files = sorted([f for f in os.listdir(done_dir) if f.endswith(".md") and not f.startswith("REJECTED_")])
                for fn in done_files[-20:]:
                    fp = os.path.join(done_dir, fn)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            content = f.read()
                        from validate_msg import parse_frontmatter
                        meta, body = parse_frontmatter(content)
                        if meta:
                            conversations.append({
                                "id": meta.get("id", fn.replace(".md", "")),
                                "from": meta.get("from", "ENG" if "ENG" in fn else "PM"),
                                "to": meta.get("to", "PM" if "ENG" in fn else "ENG"),
                                "in_reply_to": meta.get("in_reply_to", None),
                                "task": meta.get("task", "TASK-0001"),
                                "type": meta.get("type", "report" if "ENG" in fn else "assign"),
                                "created": meta.get("created", ""),
                                "body": body.strip()[:800]
                            })
                    except Exception:
                        pass

        return {
            "success": True,
            "count": len(conversations),
            "conversations": conversations
        }

    def dispatch_agent_task(self, payload):
        role = payload.get("role", "ENG").upper()
        task_id = payload.get("task", "TASK-0001")
        instruction = payload.get("instruction", "Execute task deliverables.")

        # 1. Inject into tasks/INJECT_TASK.json for the continuous loop
        inject_file = os.path.join(ROOT, "tasks", "INJECT_TASK.json")
        try:
            with open(inject_file, "w", encoding="utf-8") as f:
                json.dump({
                    "title": instruction,
                    "role": role,
                    "task": task_id,
                    "created_at": time.time()
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 2. Check if loop is running
        status = self.get_loop_status()
        if status.get("running"):
            return {
                "success": True,
                "injected": True,
                "running": True,
                "task": task_id,
                "message": f"과업({task_id})이 24시간 자율 순환 오케스트레이터에 성공적으로 주입되었습니다."
            }

        # 3. If loop not running, execute 1 turn directly
        from agent import AgentRuntime
        try:
            sender_role = "PM" if role == "ENG" else "ENG"
            sender = AgentRuntime(sender_role, backend="ollama", root=ROOT)
            msg_id, msg_p = sender.send_message(role, None, task_id, "assign" if sender_role=="PM" else "report", instruction)
            
            agent = AgentRuntime(role, model="gemma4:e4b", backend="ollama", root=ROOT)
            ok = agent.process_one_message()
            return {
                "success": ok,
                "injected": False,
                "running": False,
                "msg_id": msg_id,
                "role": role,
                "task": task_id,
                "message": "단일 턴 직접 실행 완료."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_chat_query(self, payload):
        prompt = payload.get("prompt", "").strip()
        role = payload.get("role", "DIRECT").upper()
        attachments = payload.get("attachments", [])

        if not prompt and not attachments:
            return {"success": False, "error": "프롬프트 또는 첨부파일을 입력해주세요."}

        context_parts = []
        images_b64 = []
        for att in attachments:
            name = att.get("name", "file")
            ftype = att.get("type", "")
            data = att.get("data", "")
            if ftype.startswith("image/"):
                if "," in data:
                    data = data.split(",", 1)[1]
                images_b64.append(data)
                context_parts.append(f"[첨부 이미지: {name}]")
            elif "pdf" in ftype or name.endswith(".pdf"):
                context_parts.append(f"[첨부 PDF 문서: {name}]")
            elif ftype.startswith("audio/"):
                context_parts.append(f"[첨부 오디오: {name}]")
            elif ftype.startswith("video/"):
                context_parts.append(f"[첨부 비디오: {name}]")
            else:
                context_parts.append(f"[첨부 파일: {name}]")

        full_prompt = prompt
        if context_parts:
            full_prompt = "\n".join(context_parts) + ("\n\n" + prompt if prompt else "\n\n위 첨부 자료를 분석해주세요.")

        system_prompt = "당신은 로컬 NVIDIA RTX 6000 Ada 환경에서 구동되는 Google Gemma 4 AI 어시스턴트입니다. 한국어로 깊이 있고 전문적이며 친절하게 답변하세요."
        if role == "PM":
            system_prompt += " 당신은 AtomCompany의 수석 Project Manager입니다. 작업 계획, 기획 검토, 테스트 요구사항 명세 관점에서 답변하세요."
        elif role == "ENG":
            system_prompt += " 당신은 AtomCompany의 수석 Software Engineer입니다. 고품질 코드 구현, 단위 테스트 작성, 최적화 및 디버깅 관점에서 답변하세요."

        start_t = time.time()
        ensure_ollama_daemon()
        try:
            req_data = {
                "model": "gemma4:e4b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                "stream": False
            }
            if images_b64:
                req_data["messages"][-1]["images"] = images_b64

            req_bytes = json.dumps(req_data).encode("utf-8")
            ollama_req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=req_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(ollama_req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            elapsed = time.time() - start_t
            content = result.get("message", {}).get("content", "")
            eval_count = result.get("eval_count", 0)
            tps = round(eval_count / elapsed, 1) if elapsed > 0 and eval_count > 0 else 0

            return {
                "success": True,
                "response": content,
                "model": "gemma4:e4b",
                "role": role,
                "gpu": "NVIDIA RTX 6000 Ada Generation (48GB)",
                "elapsed_sec": round(elapsed, 2),
                "tokens": eval_count,
                "tokens_per_sec": tps
            }
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_t
            err_body = e.read().decode("utf-8", errors="ignore")
            err_str = f"Ollama HTTP {e.code}: {err_body or e.reason}"
            return {
                "success": False,
                "error": f"Gemma 4 로컬 추론 오류 ({err_str})",
                "elapsed_sec": round(elapsed, 2),
                "fallback": f"A6000 Gemma 4 연산 중 HTTP 오류: {err_str}"
            }
        except urllib.error.URLError as e:
            elapsed = time.time() - start_t
            err_str = f"Ollama 데몬 연결 실패 ({e.reason})"
            return {
                "success": False,
                "error": f"Gemma 4 로컬 추론 오류 ({err_str})",
                "elapsed_sec": round(elapsed, 2),
                "fallback": f"A6000 Gemma 4 데몬에 연결할 수 없습니다 ({err_str}). 'ollama serve' 상태를 확인하세요."
            }
        except Exception as e:
            elapsed = time.time() - start_t
            err_str = str(e) or type(e).__name__
            return {
                "success": False,
                "error": f"Gemma 4 로컬 추론 오류 ({err_str})",
                "elapsed_sec": round(elapsed, 2),
                "fallback": f"A6000 Gemma 4 연산 중 예외 발생: {err_str}"
            }

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
