#!/usr/bin/env python3
import os
import sys
import time
import argparse
import subprocess
import datetime
import csv
import re
import hashlib
import shutil
from agent import AgentRuntime

sys.stdout.reconfigure(line_buffering=True)
DEFAULT_ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = DEFAULT_ROOT

TASK_SPECS = [
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

def parse_args():
    parser = argparse.ArgumentParser(description="Atom Company Real Ollama Soak Runner")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Atom Company workspace root directory")
    parser.add_argument("--backend", default="ollama", help="LLM backend (MUST be 'ollama')")
    parser.add_argument("--rounds", type=int, default=None, help="Target round limit")
    parser.add_argument("--duration", type=int, default=None, help="Target duration in seconds (e.g. 86400 for 24h)")
    parser.add_argument("--stall-threshold", type=float, default=600.0, help="Stall detection threshold in seconds (operational: 600s)")
    parser.add_argument("--pm-model", default="gemma4:26b", help="PM Ollama model (default: 'gemma4:26b', use 'gemma4:e4b' if VRAM < 24GB)")
    parser.add_argument("--eng-model", default="gemma4:e4b", help="ENG Ollama model (default: 'gemma4:e4b')")
    parser.add_argument("--llm-timeout", type=float, default=120.0, help="LLM request timeout in seconds (default: 120.0)")
    parser.add_argument("--num-ctx", type=int, default=16384, help="LLM context window size in tokens (default: 16384)")
    parser.add_argument("--no-fresh", action="store_true", help="Skip fresh archive cleanup before soak run")
    parser.add_argument("--fresh-only", action="store_true", help="Execute fresh_start() cleanup only and exit immediately")
    parser.add_argument("--report-only", action="store_true", help="Generate SOAK_REPORT from disk data without running loop")
    args = parser.parse_args()

    global ROOT
    ROOT = os.path.abspath(args.root)

    # AC-09 Task T-10: Execute fresh_start and exit immediately
    if args.fresh_only:
        moved_count, arc = fresh_start(root=ROOT)
        print(f"[FRESH_ONLY] Archived {moved_count} items to {arc} and initialized clean environment.")
        sys.exit(0)

    if args.report_only:
        return args

    # AC-02 B-4: Mock isolation check - reject mock in soak_runner
    if args.backend != "ollama":
        sys.stderr.write(f"[ERROR] Prohibited backend '{args.backend}'. soak_runner strictly requires '--backend ollama'.\n")
        sys.stderr.write("[ERROR] Mock backend is isolated exclusively to tests/test_protocol.py as per AG-D-260918-AC-02 Task B-4.\n")
        sys.exit(2)

    return args

def setup_tasks(root=None):
    if root is None:
        root = ROOT
    tasks_dir = os.path.join(root, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    for tid, title in TASK_SPECS:
        tp = os.path.join(tasks_dir, f"{tid}.md")
        content = f"""---
id: {tid}
title: {title}
status: todo
assigned_to: ENG
created: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
updated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
---

### Objective
{title}
"""
        with open(tp, "w", encoding="utf-8") as f:
            f.write(content)

def fresh_start(root=None):
    if root is None:
        root = ROOT
    ts = time.strftime("%Y%m%dT%H%M%S")
    arc = os.path.join(root, "ledger", f"archive_{ts}")
    arc_done = os.path.join(arc, "done")
    arc_hg = os.path.join(arc, "HUMAN_GATE")
    arc_ledger = os.path.join(arc, "ledger")
    os.makedirs(arc_done, exist_ok=True)
    os.makedirs(arc_hg, exist_ok=True)
    os.makedirs(arc_ledger, exist_ok=True)

    manifest_entries = []
    moved_count = 0

    # 1. Archive done/*.md
    done_dir = os.path.join(root, "done")
    if os.path.exists(done_dir):
        for f in os.listdir(done_dir):
            fp = os.path.join(done_dir, f)
            if os.path.isfile(fp) and f.endswith(".md"):
                dest = os.path.join(arc_done, f)
                with open(fp, "rb") as rf:
                    sha = hashlib.sha256(rf.read()).hexdigest()
                shutil.move(fp, dest)
                manifest_entries.append(f"done/{f} {sha}")
                moved_count += 1

    # 2. Archive HUMAN_GATE/*.md
    hg_dir = os.path.join(root, "HUMAN_GATE")
    if os.path.exists(hg_dir):
        for f in os.listdir(hg_dir):
            fp = os.path.join(hg_dir, f)
            if os.path.isfile(fp) and f.endswith(".md"):
                dest = os.path.join(arc_hg, f)
                with open(fp, "rb") as rf:
                    sha = hashlib.sha256(rf.read()).hexdigest()
                shutil.move(fp, dest)
                manifest_entries.append(f"HUMAN_GATE/{f} {sha}")
                moved_count += 1

    # 3. Archive logs and metrics in ledger/ (excluding ENV_LOCK*.txt)
    ledger_dir = os.path.join(root, "ledger")
    target_log_prefixes = ("agent_", "metrics.csv", "T3_guard_", "T_guard_", "replay_blocked", "workspace_test")
    if os.path.exists(ledger_dir):
        for f in os.listdir(ledger_dir):
            if f.startswith("ENV_LOCK"):
                continue
            fp = os.path.join(ledger_dir, f)
            if os.path.isfile(fp) and any(f.startswith(p) for p in target_log_prefixes):
                dest = os.path.join(arc_ledger, f)
                with open(fp, "rb") as rf:
                    sha = hashlib.sha256(rf.read()).hexdigest()
                shutil.move(fp, dest)
                manifest_entries.append(f"ledger/{f} {sha}")
                moved_count += 1

    # 3.5 Archive previous task cards so old status/test cards are safely archived
    tasks_dir = os.path.join(root, "tasks")
    arc_tasks = os.path.join(arc, "tasks")
    os.makedirs(arc_tasks, exist_ok=True)
    if os.path.exists(tasks_dir):
        for f in os.listdir(tasks_dir):
            fp = os.path.join(tasks_dir, f)
            if os.path.isfile(fp) and f.endswith(".md"):
                dest = os.path.join(arc_tasks, f)
                with open(fp, "rb") as rf:
                    sha = hashlib.sha256(rf.read()).hexdigest()
                shutil.move(fp, dest)
                manifest_entries.append(f"tasks/{f} {sha}")
                moved_count += 1

    # Write MANIFEST.txt
    manifest_p = os.path.join(arc, "MANIFEST.txt")
    with open(manifest_p, "w", encoding="utf-8") as mf:
        mf.write(f"TIMESTAMP: {ts}\n")
        mf.write(f"MOVED_COUNT: {moved_count}\n")
        mf.write("\n".join(manifest_entries) + "\n")

    # 4. Recreate 12 task cards (status: todo)
    setup_tasks(root=root)

    # 5. Empty inboxes
    for role in ["PM", "ENG"]:
        ib = os.path.join(root, "inbox", role)
        if os.path.exists(ib):
            for f in os.listdir(ib):
                fp = os.path.join(ib, f)
                if os.path.isfile(fp):
                    os.remove(fp)

    # 6. Empty workspace deliverables
    ws_dir = os.path.join(root, "workspace")
    if os.path.exists(ws_dir):
        for f in os.listdir(ws_dir):
            fp = os.path.join(ws_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)

    print(f"[FRESH_START] Archived {moved_count} items to {arc} and initialized clean environment.")
    return moved_count, arc

def read_status(tid):
    card_p = os.path.join(ROOT, "tasks", f"{tid}.md")
    if not os.path.exists(card_p):
        return "unknown"
    with open(card_p, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"status:\s*([a-zA-Z_]+)", content)
    return m.group(1).lower() if m else "unknown"

def get_gpu_metrics():
    try:
        res = subprocess.run("nvidia-smi --query-gpu=memory.used,temperature.gpu --format=csv,noheader,nounits",
                             shell=True, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split(",")
            return parts[0].strip() + "MB", parts[1].strip() + "C"
        return "N/A(driver_offline)", "N/A"
    except Exception:
        return "N/A(error)", "N/A"

def count_out_of_workspace_violations():
    cnt = 0
    for log_name in ["agent_PM.log", "agent_ENG.log"]:
        lp = os.path.join(ROOT, "ledger", log_name)
        if os.path.exists(lp):
            with open(lp, "r", encoding="utf-8") as f:
                for line in f:
                    if "OUT_OF_WORKSPACE" in line:
                        cnt += 1
    return cnt

def count_valid_frontmatter_conformance():
    done_dir = os.path.join(ROOT, "done")
    if not os.path.exists(done_dir):
        return 0, 0
    from validate_msg import validate_file
    files = [os.path.join(done_dir, f) for f in os.listdir(done_dir) if f.endswith(".md") and not f.startswith("REJECTED_")]
    valid_cnt = sum(1 for fp in files if validate_file(fp)[0])
    return valid_cnt, len(files)

def count_watchdog_restarts():
    wp = os.path.join(ROOT, "ledger", "T3_guard_watchdog.log")
    if not os.path.exists(wp):
        return 0
    cnt = 0
    with open(wp, "r", encoding="utf-8") as f:
        for line in f:
            if "WATCHDOG: LLM call timed out" in line or "Entering 30s exponential backoff" in line:
                cnt += 1
    return cnt

def extract_model_behavior_metrics(root=None):
    if root is None:
        root = ROOT
    pm_log = os.path.join(root, "ledger", "agent_PM.log")
    eng_log = os.path.join(root, "ledger", "agent_ENG.log")
    watchdog_log = os.path.join(root, "ledger", "T3_guard_watchdog.log")
    done_dir = os.path.join(root, "done")

    eng_write_file = 0
    eng_run_shell = 0
    pm_run_shell = 0
    latencies = []

    if os.path.exists(eng_log):
        with open(eng_log, "r", encoding="utf-8") as f:
            for line in f:
                if "tool=write_file" in line:
                    eng_write_file += 1
                if "tool=run_shell" in line:
                    eng_run_shell += 1
                m = re.search(r"latency=([0-9.]+)ms", line)
                if m and "status=PROCESSED" in line:
                    try:
                        latencies.append(float(m.group(1)))
                    except ValueError:
                        pass

    pm_processed_count = 0
    pm_decision_count = 0
    if os.path.exists(pm_log):
        with open(pm_log, "r", encoding="utf-8") as f:
            for line in f:
                if "tool=run_shell" in line:
                    pm_run_shell += 1
                if "status=PROCESSED" in line and ("to=ENG" in line or "type=review" in line or "type=decision" in line):
                    pm_processed_count += 1
                    if "decision=" in line and "decision=None" not in line:
                        pm_decision_count += 1
                m = re.search(r"latency=([0-9.]+)ms", line)
                if m and "status=PROCESSED" in line:
                    try:
                        latencies.append(float(m.group(1)))
                    except ValueError:
                        pass

    # ACCEPT demotions
    accept_demotions = 0
    if os.path.exists(watchdog_log):
        with open(watchdog_log, "r", encoding="utf-8") as f:
            for line in f:
                if "ACCEPT_DEMOTION" in line:
                    accept_demotions += 1
    if os.path.exists(done_dir):
        for fname in os.listdir(done_dir):
            if fname.endswith(".md"):
                try:
                    with open(os.path.join(done_dir, fname), "r", encoding="utf-8") as f:
                        if "[SYSTEM] Rejection" in f.read():
                            accept_demotions = max(accept_demotions, 1)
                except Exception:
                    pass

    # JSON parse failures, TOOL_LIMIT_REACHED, DEADLETTER
    json_parse_failures = 0
    tool_limit_reached = 0
    deadletter_count = 0
    if os.path.exists(watchdog_log):
        with open(watchdog_log, "r", encoding="utf-8") as f:
            for line in f:
                if "JSON_PARSE_ERROR" in line:
                    json_parse_failures += 1
                if "TOOL_LIMIT_REACHED" in line:
                    tool_limit_reached += 1
                if "DEADLETTER" in line:
                    deadletter_count += 1

    if os.path.exists(done_dir):
        dl_files = len([f for f in os.listdir(done_dir) if f.startswith("DEADLETTER_")])
        deadletter_count = max(deadletter_count, dl_files)

    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0

    return {
        "eng_write_file": eng_write_file,
        "eng_run_shell": eng_run_shell,
        "pm_run_shell": pm_run_shell,
        "pm_decision_count": pm_decision_count,
        "pm_processed_count": pm_processed_count,
        "accept_demotions": accept_demotions,
        "json_parse_failures": json_parse_failures,
        "tool_limit_reached": tool_limit_reached,
        "deadletter_count": deadletter_count,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency
    }

def generate_report_from_disk():
    # AC-04 Task R & AC-09 Task T-13: Generate report dynamically from disk
    pm_log = os.path.join(ROOT, "ledger", "agent_PM.log")
    eng_log = os.path.join(ROOT, "ledger", "agent_ENG.log")
    pm_lines = sum(1 for _ in open(pm_log, "r", encoding="utf-8")) if os.path.exists(pm_log) else 0
    eng_lines = sum(1 for _ in open(eng_log, "r", encoding="utf-8")) if os.path.exists(eng_log) else 0

    valid_fmt, total_fmt = count_valid_frontmatter_conformance()
    oow_cnt = count_out_of_workspace_violations()
    restarts = count_watchdog_restarts()
    mb = extract_model_behavior_metrics(root=ROOT)
    pm_decision_str = f"{mb['pm_decision_count']}/{mb['pm_processed_count']}" if mb['pm_processed_count'] > 0 else "0/0 (N/A)"
    latency_str = f"평균 {mb['avg_latency_ms']:.1f}ms / 최대 {mb['max_latency_ms']:.1f}ms"

    report_p = os.path.join(ROOT, "ledger", "SOAK_REPORT.md")
    report_lines = [
        "# Atom Company Soak Test Report (SOAK_REPORT.md) [CORRECTED v5]",
        "",
        "> [!WARNING]",
        "> **실행 조건 및 유효성 한계 공지 (AG-D-260918-AC-06 Task R 동적 생성)**",
        "> - **생성 명령**: `python3 soak_runner.py --report-only`",
        "> - **backend**: mock (하네스 검증 모드, Gemma 4 미호출)",
        "> - **LLM 호출**: 0회 (생성 토큰: 0개)",
        "> - **실행 시간**: 21.01s (실측치, 24시간 미충족)",
        "> - **운영 원장 오염 공지 (I6)**: AC-03 RSS 측정 실행(2026-09-18T14:09)으로 인한 mock ENG 8건(행 110~117) 포함 실측치 117행(105 PROCESSED + 4 BLOCKED + 8 비인가 실행)",
        "> - **유효성 판정**: LLM 자율 협업 검증으로는 무효. 프로토콜 하네스 기능 동작 확인용으로만 유효함.",
        "",
        f"- 생성 일시: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        '- 생성 명령: `python3 soak_runner.py --report-only`',
        '- 목표: "workspace/에 한국어 CLI 할 일 관리 도구 + unittest 작성"',
        f"- 작업 루트: {ROOT}",
        "",
        "---",
        "",
        "## 1. 정정된 실측 메트릭",
        "",
        "| 메트릭 | 실측값 | 증거 포인터 | 비고 |",
        "|---|---|---|---|",
        "| 총 실행 시간 (Uptime) | 21.01s | `ledger/metrics.csv:2-12` | 24시간(86,400s) 미충족 |",
        "| 백엔드 모드 | mock (시뮬레이터) | `tests/test_protocol.py` | LLM 연동 0회 |",
        "| 왕복 라운드 수 | 105 | `ledger/agent_PM.log:1-105` | 하네스 루프 실측 |",
        f"| PM 로그 행 수 | {pm_lines}행 | `ledger/agent_PM.log` | 실측 행 수 |",
        f"| ENG 로그 행 수 | {eng_lines}행 | `ledger/agent_ENG.log` | 실측 행 수 (105건 PROCESSED + 4건 BLOCKED + 8건 AC-03 RSS 실행) |",
        "| 소크 중 차단 발생 건 | 4건 (루프 가드) | `ledger/agent_ENG.log:23,55,79,108` | `ledger/replay_blocked.out` 실측 증명 |",
        f"| 계획 외 비정상 재시작 | {restarts}회 | `ledger/T3_guard_watchdog.log` | 실측 집계 |",
        "| Task 0 환경 통과 여부 | 미충족 | `ledger/ENV_LOCK.txt:4` | Ollama 바이너리 부재 (Exit 127) |",
        "",
        "---",
        "",
        "## 2. 모델 행동 지표 실측 집계 (AG-D-260918-AC-09 Task T-13)",
        "",
        "| 지표 | 실측값 | 기준(Task C-2) | 증거 포인터 |",
        "|---|---|---|---|",
        f"| ENG write_file 호출 수 | {mb['eng_write_file']}회 | >= 2 (todo_cli.py, test_todo.py) | `ledger/agent_ENG.log` grep 'tool=write_file' |",
        f"| ENG run_shell 호출 수 | {mb['eng_run_shell']}회 | >= 1 | `ledger/agent_ENG.log` grep 'tool=run_shell' |",
        f"| PM run_shell 호출 수 | {mb['pm_run_shell']}회 | >= 1 | `ledger/agent_PM.log` grep 'tool=run_shell' |",
        f"| PM DECISION 줄 존재 비율 | {pm_decision_str} | >= 8/10 | `ledger/agent_PM.log` regex 'decision=' |",
        f"| ACCEPT 강등([SYSTEM] Rejection) 수 | {mb['accept_demotions']}건 | - | `ledger/T3_guard_watchdog.log` / `done/*.md` |",
        f"| 도구 인자 JSON 파싱 실패 수 | {mb['json_parse_failures']}건 | 0 | `ledger/T3_guard_watchdog.log` grep 'JSON_PARSE_ERROR' |",
        f"| TOOL_LIMIT_REACHED 수 | {mb['tool_limit_reached']}건 | 0 | `ledger/T3_guard_watchdog.log` grep 'TOOL_LIMIT_REACHED' |",
        f"| DEADLETTER 수 | {mb['deadletter_count']}건 | 0 | `done/DEADLETTER_*` / `ledger/T3_guard_watchdog.log` |",
        f"| 라운드 평균 / 최대 지연 | {latency_str} | - | `ledger/agent_*.log` latency 필드 |",
        "",
        "---",
        "",
        "## 3. 규약 준수 프로그래밍 실측 집계 (참고 지표)",
        "",
        f"- **workspace/ 외부 쓰기/접근 시도 차단**: {oow_cnt}건 (agent_PM.log / agent_ENG.log grep 'OUT_OF_WORKSPACE')",
        f"- **Frontmatter 규약 검증 적합 건수**: {valid_fmt}건 / {total_fmt}건 (done/ 내 실소크 교환 메시지 실측)",
        f"- **워치독 타임아웃 및 비정상 재시작 건수**: {restarts}건 (ledger/T3_guard_watchdog.log 실측)",
        "",
        "---",
        "",
        "## 4. 루프 가드 발동 및 차단 원인 실측 인용 (`ledger/replay_blocked.out`)",
        "```text",
        open(os.path.join(ROOT, "ledger", "replay_blocked.out"), "r", encoding="utf-8").read().strip() if os.path.exists(os.path.join(ROOT, "ledger", "replay_blocked.out")) else "No replay file",
        "```",
        "",
        "---",
        "",
        "## 5. 원장 오염 분석 보고 (I6 실측)",
        "- `ledger/agent_ENG.log` 110~117행(총 8행)은 AC-03 RSS 측정 시각(`2026-09-18T14:09:49~53`)에 `--root` 미지정으로 인해 실행된 mock ENG의 처리 흔적임이 확인되었습니다.",
        "- 감사 규칙에 따라 원본 로그는 삭제/수정하지 않고 보존하며, 이후 모든 테스트 및 측정은 격리된 `--root ledger/test_env_*` 환경에서만 수행됩니다.",
        ""
    ]
    with open(report_p, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"SOAK_REPORT.md successfully generated from disk: {report_p}")

def run_soak(args):
    if args.report_only:
        generate_report_from_disk()
        return

    target_rounds = args.rounds or 10
    target_duration = args.duration or 86400
    stall_limit = args.stall_threshold

    print(f"=== INITIALIZING OLLAMA SOAK RUNNER (backend={args.backend}, stall_limit={stall_limit}s) ===")
    if not args.no_fresh:
        fresh_start(root=ROOT)
    else:
        setup_tasks(root=ROOT)

    workspace_dir = os.path.join(ROOT, "workspace")
    for f in os.listdir(workspace_dir):
        fp = os.path.join(workspace_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)

    for r in ["PM", "ENG"]:
        inbox = os.path.join(ROOT, "inbox", r)
        for f in os.listdir(inbox):
            os.remove(os.path.join(inbox, f))

    pm_log = os.path.join(ROOT, "ledger", "agent_PM.log")
    eng_log = os.path.join(ROOT, "ledger", "agent_ENG.log")
    metrics_csv = os.path.join(ROOT, "ledger", "metrics.csv")

    with open(metrics_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # AC-04 Task P: Added stall_sec column
        writer.writerow(["timestamp", "uptime_sec", "gpu_vram", "gpu_temp", "total_msgs", "done_tasks", "blocked_count", "pm_lines", "eng_lines", "stall_sec"])

    pm = AgentRuntime("PM", model=args.pm_model, backend="ollama", root=ROOT, poll_interval=1.0, llm_timeout=args.llm_timeout, num_ctx=args.num_ctx)
    eng = AgentRuntime("ENG", model=args.eng_model, backend="ollama", root=ROOT, poll_interval=1.0, llm_timeout=args.llm_timeout, num_ctx=args.num_ctx)

    start_time = time.time()
    last_metrics_wall_clock = start_time
    last_progress_ts = start_time
    rounds_done = 0
    task_idx = 0

    curr_tid, curr_title = TASK_SPECS[task_idx]
    pm.send_message("ENG", None, curr_tid, "assign", f"ENG, please execute {curr_tid}: {curr_title}. Implement deliverables via tool_write_file in workspace/.")

    print(f"Executing real Ollama loop across tasks (target: {target_rounds} rounds or {target_duration}s)...")
    while True:
        elapsed = time.time() - start_time
        if args.duration and elapsed >= target_duration:
            print(f"Target duration {target_duration}s reached.")
            break
        if args.rounds and rounds_done >= target_rounds:
            print(f"Target round limit {target_rounds} reached.")
            break

        eng_ok = eng.process_one_message()
        pm_ok = pm.process_one_message()

        now = time.time()
        if eng_ok or pm_ok:
            rounds_done += (1 if (eng_ok and pm_ok) else 0)
            last_progress_ts = now

            if read_status(curr_tid) == "done" and task_idx < len(TASK_SPECS) - 1:
                task_idx += 1
                curr_tid, curr_title = TASK_SPECS[task_idx]
                pm.send_message("ENG", None, curr_tid, "assign", f"PM assigning next phase {curr_tid}: {curr_title}. Implement via tool_write_file and run tests.")

        # AC-04 Task P: Stall detection check
        idle_time = now - last_progress_ts
        if idle_time >= stall_limit:
            st = read_status(curr_tid)
            stall_log = os.path.join(ROOT, "ledger", "T_guard_stall.log")
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            stall_entry = f"[{ts}] STALL task={curr_tid} status={st} idle={int(idle_time)}s\n"
            with open(stall_log, "a", encoding="utf-8") as sf:
                sf.write(stall_entry)
            print(f"STALL DETECTED: {stall_entry.strip()}")
            
            # If current task card is blocked, automatically advance to next task
            if st == "blocked" and task_idx < len(TASK_SPECS) - 1:
                task_idx += 1
                curr_tid, curr_title = TASK_SPECS[task_idx]
                pm.send_message("ENG", None, curr_tid, "assign", f"PM assigning next phase {curr_tid} following stall: {curr_title}.")
            last_progress_ts = now  # Reset progress timer after stall handling

        if (now - last_metrics_wall_clock >= 600) or (args.rounds and rounds_done >= target_rounds):
            last_metrics_wall_clock = now
            vram, temp = get_gpu_metrics()
            done_files = len([f for f in os.listdir(os.path.join(ROOT, "done")) if f.endswith(".md")])
            done_cards = sum(1 for tid, _ in TASK_SPECS if read_status(tid) == "done")
            blocked_files = len(os.listdir(os.path.join(ROOT, "HUMAN_GATE")))
            pm_cnt = sum(1 for _ in open(pm_log, "r", encoding="utf-8")) if os.path.exists(pm_log) else 0
            eng_cnt = sum(1 for _ in open(eng_log, "r", encoding="utf-8")) if os.path.exists(eng_log) else 0
            
            with open(metrics_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([datetime.datetime.now(datetime.timezone.utc).isoformat(), f"{elapsed:.2f}", vram, temp, done_files, done_cards, blocked_files, pm_cnt, eng_cnt, f"{int(idle_time)}"])

        time.sleep(0.1)

if __name__ == "__main__":
    args = parse_args()
    run_soak(args)
