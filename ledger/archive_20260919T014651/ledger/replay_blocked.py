#!/usr/bin/env python3
import os
import re
import datetime

ROOT = "/home/sims/auto/atom-company"
ENG_LOG = os.path.join(ROOT, "ledger", "agent_ENG.log")
PM_LOG = os.path.join(ROOT, "ledger", "agent_PM.log")
DONE_DIR = os.path.join(ROOT, "done")
ARCHIVE_DIR = os.path.join(ROOT, "HUMAN_GATE", "archive_t3")

def analyze_blocked_events():
    print("=== REPLAY BLOCKED EVENTS ANALYSIS ===")
    
    # 1. Inspect the 4 blocked lines in agent_ENG.log
    blocked_lines = []
    with open(ENG_LOG, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if "status=BLOCKED" in line:
                blocked_lines.append((idx, line.strip()))
                
    print(f"Found {len(blocked_lines)} BLOCKED events in agent_ENG.log:")
    for line_no, line in blocked_lines:
        print(f"  Line {line_no}: {line}")

    # 2. Correlate with REQ files in HUMAN_GATE/archive_t3
    print("\nMatching HUMAN_GATE REQ files created during soak run:")
    for line_no, line in blocked_lines:
        # Extract timestamp, e.g. 2026-09-18T13:51:40
        m = re.search(r"\[([0-9T:-]+)\.", line)
        if m:
            ts_prefix = m.group(1).replace("-", "").replace(":", "")[:15] # YYYYMMDDTHHMMSS
            req_match = [f for f in os.listdir(ARCHIVE_DIR) if ts_prefix[8:] in f.replace("-", "")]
            print(f"  Event at line {line_no} ({m.group(1)}): REQ files = {req_match}")

    # 3. Analyze task message count in done/
    # Count messages per task in done/
    task_counts = {}
    for fn in os.listdir(DONE_DIR):
        if not fn.endswith(".md"):
            continue
        fp = os.path.join(DONE_DIR, fn)
        with open(fp, "r", encoding="utf-8") as f:
            c = f.read()
        tm = re.search(r"task:\s*([A-Za-z0-9_-]+)", c)
        t = tm.group(1) if tm else "UNKNOWN"
        task_counts[t] = task_counts.get(t, 0) + 1

    print("\nTask message count in done/:")
    for t in sorted(task_counts.keys()):
        print(f"  {t}: {task_counts[t]} messages")

if __name__ == "__main__":
    analyze_blocked_events()
