#!/usr/bin/env python3
"""
Atom Company Continuous 24h Autonomous Orchestrator (continuous_orchestrator.py)
Orchestrates PM & ENG dual-agent autonomous software development loop using local Gemma 4 on RTX 6000 Ada.
Supports continuous task rotation, infinite iteration, dynamic task injection, and real-time state telemetry.
"""
import os
import sys
import time
import json
import signal
import datetime
import argparse
import traceback
import subprocess

os.environ["no_proxy"] = "127.0.0.1,localhost,::1"

ROOT = os.path.dirname(os.path.abspath(__file__))
from agent import AgentRuntime
from validate_msg import parse_frontmatter

BASE_TASK_SPECS = [
    ("TASK-0001", "기본 Todo 추가 및 목록 조회 CLI 구현"),
    ("TASK-0002", "Todo 완료(done) 및 삭제(del) 기능 구현"),
    ("TASK-0003", "유효하지 않은 명령어 및 인자 예외 처리 구현"),
    ("TASK-0004", "정수형이 아닌 ID 및 누락 인자 검증 로직 추가"),
    ("TASK-0005", "영속성 JSON 데이터 저장소 격리 및 검증"),
    ("TASK-0006", "한국어 도움말 및 안내 메시지 포맷팅 개선"),
    ("TASK-0007", "CLI 종료 코드(0 vs 1) 정합성 보장"),
    ("TASK-0008", "단위 테스트 케이스 1: 기본 CRUD 기능 검증"),
    ("TASK-0009", "단위 테스트 케이스 2: 예외 처리 및 에러 메시지 검증"),
    ("TASK-0010", "단위 테스트 케이스 3: 경계값 및 비정상 입력 검증"),
    ("TASK-0011", "회귀 테스트 및 코드 품질 정적 점검"),
    ("TASK-0012", "최종 소프트웨어 인수 검증 및 운영 배포 준비"),
]

EXTENDED_TASK_THEMES = [
    "비동기 파일 입출력 및 멀티프로세스 동시성 락 최적화",
    "JSON 데이터 저장소 트랜잭션 롤백 및 자동 백업 복구",
    "마감일(Due Date) 및 우선순위(Priority: High/Med/Low) 필터링",
    "다중 태그(Tags) 할당 및 정규식 기반 정밀 키워드 검색",
    "대용량 Todo 목록 페이징(Pagination) 및 정렬(Sorting) 엔진",
    "ANSI 네온 컬러 터미널 UI 출력 및 테이블 서식 자동 맞춤",
    "10,000건 대량 데이터 스트레스 테스트 및 메모리 프로파일링",
    "YAML 및 CSV 데이터 내보내기/가져오기(Export/Import) 인터페이스",
    "RESTful API 연동 준비 및 JSON 스키마 유효성 자가 검증기",
    "소버린 AI 에이전트 감사 추적(Audit Trail) 및 암호화 로그 생성"
]

class ContinuousOrchestrator:
    def __init__(self, root=ROOT, model="gemma4:e4b", poll_interval=1.5):
        self.root = root
        self.model = model
        self.poll_interval = poll_interval
        self.running = True
        self.start_time = time.time()
        self.round_count = 0
        self.task_idx = 0
        self.all_tasks = list(BASE_TASK_SPECS)
        
        self.ledger_dir = os.path.join(self.root, "ledger")
        self.tasks_dir = os.path.join(self.root, "tasks")
        self.queue_dir = os.path.join(self.tasks_dir, "queue")
        self.workspace_dir = os.path.join(self.root, "workspace")
        self.inbox_pm = os.path.join(self.root, "inbox", "PM")
        self.inbox_eng = os.path.join(self.root, "inbox", "ENG")
        self.done_dir = os.path.join(self.root, "done")
        
        for d in [self.ledger_dir, self.tasks_dir, self.queue_dir, self.workspace_dir, self.inbox_pm, self.inbox_eng, self.done_dir]:
            os.makedirs(d, exist_ok=True)
            
        self.pid_file = os.path.join(self.ledger_dir, "daemon.pid")
        self.state_file = os.path.join(self.ledger_dir, "daemon_state.json")
        self.feed_file = os.path.join(self.ledger_dir, "conversation_feed.jsonl")
        
        self._write_pid()
        self._register_signals()

        # Initialize runtimes
        self.pm = AgentRuntime("PM", model=self.model, backend="ollama", root=self.root, poll_interval=1.0)
        self.eng = AgentRuntime("ENG", model=self.model, backend="ollama", root=self.root, poll_interval=1.0)

    def _write_pid(self):
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception:
            pass

    def _register_signals(self):
        def sig_handler(signum, frame):
            print(f"[ORCHESTRATOR] Received signal {signum}, stopping gracefully...")
            self.running = False
            self.update_state("STOPPED", "Shutdown signal received")
            self._remove_pid()
            sys.exit(0)
        signal.signal(signal.SIGTERM, sig_handler)
        signal.signal(signal.SIGINT, sig_handler)

    def update_state(self, status="RUNNING", event=""):
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        uptime = int(time.time() - self.start_time)
        
        # Read current task details
        curr_tid, curr_title = self.all_tasks[self.task_idx] if self.task_idx < len(self.all_tasks) else ("TASK-XXXX", "자율 확장 과업")
        task_status = self.get_task_status(curr_tid)
        
        # Count messages in done
        done_count = len([f for f in os.listdir(self.done_dir) if f.endswith(".md") and not f.startswith("REJECTED_")])
        
        # List files in workspace
        workspace_files = [f for f in os.listdir(self.workspace_dir) if not f.startswith(".")]

        state_data = {
            "status": status,
            "pid": os.getpid(),
            "model": self.model,
            "uptime_sec": uptime,
            "round_count": self.round_count,
            "current_task": {
                "id": curr_tid,
                "title": curr_title,
                "status": task_status,
                "index": self.task_idx + 1,
                "total_defined": len(self.all_tasks)
            },
            "total_messages": done_count,
            "workspace_files": workspace_files,
            "last_event": event,
            "last_updated": now_ts
        }
        
        tmp_p = self.state_file + ".tmp"
        with open(tmp_p, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_p, self.state_file)

    def get_task_status(self, task_id):
        tp = os.path.join(self.tasks_dir, f"{task_id}.md")
        if not os.path.exists(tp):
            return "todo"
        try:
            with open(tp, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            m = re.search(r"status:\s*([a-zA-Z_]+)", content)
            return m.group(1).lower() if m else "todo"
        except Exception:
            return "todo"

    def ensure_task_card(self, tid, title):
        tp = os.path.join(self.tasks_dir, f"{tid}.md")
        if not os.path.exists(tp):
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            content = f"""---
id: {tid}
title: {title}
status: todo
assigned_to: ENG
created: {now}
updated: {now}
---

### Objective
{title}
"""
            with open(tp, "w", encoding="utf-8") as f:
                f.write(content)

    def check_injected_tasks(self):
        """Check for external user tasks injected via UI"""
        inject_file = os.path.join(self.tasks_dir, "INJECT_TASK.json")
        if os.path.exists(inject_file):
            try:
                with open(inject_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                os.remove(inject_file)
                custom_title = data.get("title", "사용자 실시간 요청 과업")
                new_idx = len(self.all_tasks) + 1
                new_tid = f"TASK-{new_idx:04d}"
                self.all_tasks.append((new_tid, custom_title))
                self.ensure_task_card(new_tid, custom_title)
                
                # Assign immediately
                self.task_idx = len(self.all_tasks) - 1
                self.pm.send_message("ENG", None, new_tid, "assign", f"PM assigning user injected task {new_tid}: {custom_title}. Implement deliverables in workspace/ and verify with unittest.")
                self.update_state("RUNNING", f"User injected task {new_tid} adopted")
                print(f"[ORCHESTRATOR] User task {new_tid} successfully adopted into loop!")
            except Exception as e:
                print(f"[ORCHESTRATOR] Error reading injected task: {e}")

    def synthesize_next_task(self):
        """Generate next progressive engineering task to guarantee 24/7 continuous operation"""
        ext_idx = len(self.all_tasks) - len(BASE_TASK_SPECS)
        theme = EXTENDED_TASK_THEMES[ext_idx % len(EXTENDED_TASK_THEMES)]
        iteration = (ext_idx // len(EXTENDED_TASK_THEMES)) + 1
        new_idx = len(self.all_tasks) + 1
        new_tid = f"TASK-{new_idx:04d}"
        new_title = f"{theme} (고도화 사이클 {iteration})"
        self.all_tasks.append((new_tid, new_title))
        self.ensure_task_card(new_tid, new_title)
        print(f"[ORCHESTRATOR] Synthesized continuous task {new_tid}: {new_title}")
        return new_tid, new_title

    def run(self):
        print(f"=== [24H AUTONOMOUS ORCHESTRATOR STARTED] (PID: {os.getpid()}) ===")
        print(f"Model: {self.model} on NVIDIA RTX 6000 Ada | Root: {self.root}")
        
        # Ensure base tasks exist
        for tid, title in self.all_tasks:
            self.ensure_task_card(tid, title)

        curr_tid, curr_title = self.all_tasks[self.task_idx]
        
        # If no messages in inboxes, send initial assignment to kick off loop
        pm_inbox_files = [f for f in os.listdir(self.inbox_pm) if f.endswith(".md")]
        eng_inbox_files = [f for f in os.listdir(self.inbox_eng) if f.endswith(".md")]
        
        if not pm_inbox_files and not eng_inbox_files:
            print(f"[ORCHESTRATOR] Initializing conversation: PM assigning {curr_tid}...")
            self.pm.send_message(
                "ENG", None, curr_tid, "assign",
                f"ENG, please execute {curr_tid}: {curr_title}. Implement deliverables via write_file in workspace/ and verify with run_shell (python3 -m unittest)."
            )
            self.update_state("RUNNING", f"Assigned {curr_tid} to ENG")

        last_progress_time = time.time()

        while self.running:
            try:
                self.check_injected_tasks()
                
                # Execute turns
                eng_active = self.eng.process_one_message()
                if eng_active:
                    self.round_count += 1
                    last_progress_time = time.time()
                    self.update_state("RUNNING", "ENG processed message & updated workspace")

                pm_active = self.pm.process_one_message()
                if pm_active:
                    self.round_count += 1
                    last_progress_time = time.time()
                    self.update_state("RUNNING", "PM reviewed deliverables & executed verification")

                # Check task completion
                curr_tid, curr_title = self.all_tasks[self.task_idx]
                task_status = self.get_task_status(curr_tid)
                
                if task_status in ["done", "blocked"]:
                    print(f"[ORCHESTRATOR] Task {curr_tid} reached status '{task_status}'. Advancing to next task...")
                    self.task_idx += 1
                    if self.task_idx >= len(self.all_tasks):
                        # Synthesize new task infinitely
                        next_tid, next_title = self.synthesize_next_task()
                    else:
                        next_tid, next_title = self.all_tasks[self.task_idx]
                        self.ensure_task_card(next_tid, next_title)
                        
                    self.pm.send_message(
                        "ENG", None, next_tid, "assign",
                        f"PM advancing to {next_tid}: {next_title}. Implement deliverables in workspace/ and run unittests."
                    )
                    self.update_state("RUNNING", f"Advanced to {next_tid}")
                    last_progress_time = time.time()

                # Stall prevention watchdog (if idle for > 180s, nudge conversation)
                if (time.time() - last_progress_time) > 180.0:
                    print(f"[ORCHESTRATOR] Idle watchdog triggered (>180s). Nudging PM & ENG...")
                    curr_tid, curr_title = self.all_tasks[self.task_idx]
                    self.pm.send_message(
                        "ENG", None, curr_tid, "assign",
                        f"PM status check on {curr_tid}: {curr_title}. Please report current implementation progress or write unit tests."
                    )
                    last_progress_time = time.time()
                    self.update_state("RUNNING", "Watchdog nudged active task")

                self.update_state("RUNNING", "Active 24h collaboration loop")
                time.sleep(self.poll_interval)

            except Exception as e:
                err_msg = f"Orchestrator loop exception: {e}\n{traceback.format_exc()}"
                print(f"[ORCHESTRATOR ERROR] {err_msg}")
                self.update_state("DEGRADED", str(e))
                time.sleep(3.0)

        self.update_state("STOPPED", "Orchestrator exited")
        self._remove_pid()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="24h Continuous Autonomous Orchestrator")
    parser.add_argument("--model", default="gemma4:e4b", help="Model name")
    parser.add_argument("--poll-interval", type=float, default=1.5, help="Poll interval in seconds")
    args = parser.parse_args()
    
    orch = ContinuousOrchestrator(model=args.model, poll_interval=args.poll_interval)
    orch.run()
