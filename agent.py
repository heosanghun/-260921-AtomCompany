#!/usr/bin/env python3
import os
import sys
import time
import json
import re
import shlex
import argparse
import hashlib
import datetime
import subprocess
import urllib.request
import urllib.error

from validate_msg import parse_frontmatter, validate_message, format_message

class HumanGateViolation(Exception):
    def __init__(self, reason, details):
        super().__init__(reason)
        self.reason = reason
        self.details = details

# AC-03 Task F / AC-04 Task Q: Ollama Native Tools Schema
ALL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file strictly within workspace directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file inside workspace"},
                    "content": {"type": "string", "description": "Text content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read text content of a file strictly within workspace directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file inside workspace"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories in a workspace directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside workspace (empty for workspace root)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute an allowed shell command in workspace (shell=False)",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Command string using allowed binaries (ls, cat, head, tail, wc, diff, python3)"}
                },
                "required": ["cmd"]
            }
        }
    }
]

DEFAULT_ROOT = os.path.dirname(os.path.abspath(__file__))

class AgentRuntime:
    def __init__(self, role, model="gemma4:e4b", backend="ollama", root=None, poll_interval=1.0, llm_timeout=120.0, num_ctx=16384):
        self.role = role.upper()
        if self.role not in ["PM", "ENG"]:
            raise ValueError(f"Invalid role: {role}")
        self.peer_role = "ENG" if self.role == "PM" else "PM"
        self.model = model
        self.backend = backend
        self.root = os.path.abspath(root) if root else DEFAULT_ROOT
        self.poll_interval = poll_interval
        self.llm_timeout = float(llm_timeout)
        self.num_ctx = int(num_ctx)
        
        # Directories
        self.inbox_dir = os.path.join(self.root, "inbox", self.role)
        self.peer_inbox_dir = os.path.join(self.root, "inbox", self.peer_role)
        self.done_dir = os.path.join(self.root, "done")
        self.tasks_dir = os.path.join(self.root, "tasks")
        self.workspace_dir = os.path.join(self.root, "workspace")
        self.human_gate_dir = os.path.join(self.root, "HUMAN_GATE")
        self.ledger_dir = os.path.join(self.root, "ledger")
        self.roles_dir = os.path.join(self.root, "ROLES")
        
        for d in [self.inbox_dir, self.peer_inbox_dir, self.done_dir, self.tasks_dir,
                  self.workspace_dir, self.human_gate_dir, self.ledger_dir, self.roles_dir]:
            os.makedirs(d, exist_ok=True)
            
        self.log_file = os.path.join(self.ledger_dir, f"agent_{self.role}.log")
        self.msg_counter = 0
        self.consecutive_5xx = 0
        self.current_task_id = "TASK-0001"
        self.retry_count = {}   # AC-03 Task H: Per-message retry tracking
        self.last_shell = None  # AC-04 Task N: {task, exit, cmd} for objective ACCEPT verification

    def _get_tools_schema(self):
        # AC-04 Task N: PM must NOT have write_file tool. Deliverables written only by ENG.
        if self.role == "PM":
            return [t for t in ALL_TOOLS if t["function"]["name"] != "write_file"]
        return ALL_TOOLS

    def log(self, msg_id, from_role, to_role, task_id, msg_type, tool_count, latency_ms, status, note=""):
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = f"[{ts}] id={msg_id} from={from_role} to={to_role} task={task_id} type={msg_type} tools={tool_count} latency={latency_ms:.1f}ms status={status} note={note}\n"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line)

    def write_guard_log(self, guard_name, text):
        path = os.path.join(self.ledger_dir, f"T3_guard_{guard_name}.log")
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    # ==========================================
    # AC-04 Task O: SHELL ALLOWLIST & SAFE RUNNER
    # ==========================================
    def _check_security(self, action, target_path=None, cmd=None, tokens=None):
        net_pattern = re.compile(r"\b(curl|wget|nc|ssh|ping|nmap|git\s+(clone|push)|pip\s+install|npm\s+install)\b", re.IGNORECASE)
        audio_pattern = re.compile(r"\b(aplay|paplay|speaker-test|beep)\b", re.IGNORECASE)
        billing_pattern = re.compile(r"\b(stripe|billing|credit_card|purchase|subscribe|buy_tokens)\b", re.IGNORECASE)

        if cmd:
            if net_pattern.search(cmd):
                raise HumanGateViolation("EXTERNAL_NETWORK_ATTEMPT", f"Command contains network pattern: '{cmd}'")
            if audio_pattern.search(cmd):
                raise HumanGateViolation("AUDIO_ALERT_ATTEMPT", f"Command contains audio pattern: '{cmd}'")
            if billing_pattern.search(cmd):
                raise HumanGateViolation("FINANCIAL_CHARGE_ATTEMPT", f"Command contains billing pattern: '{cmd}'")

        if action == "run_shell" and cmd:
            # Check shell metacharacters and redirects
            if any(c in cmd for c in ["$", "~", ";", "&", "|", "`", ">", "<"]):
                raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", f"Command contains forbidden shell metacharacter: '{cmd}'")

            if tokens is None:
                try:
                    tokens = shlex.split(cmd)
                except Exception as e:
                    raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", f"shlex parse error: {e}")

            if not tokens:
                raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", "Empty command")

            ALLOWED_BINARIES = ["ls", "cat", "head", "tail", "wc", "diff", "python3"]
            binary = tokens[0]
            if binary not in ALLOWED_BINARIES:
                raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", f"Binary '{binary}' not in allowlist {ALLOWED_BINARIES}")

            if binary == "python3" and "-c" in tokens:
                raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", "python3 -c inline execution is strictly prohibited")

            for arg in tokens[1:]:
                if arg.startswith("/") and arg != "/dev/null":
                    raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", f"Absolute path prohibited in argument: '{arg}'")
                if ".." in arg or "~" in arg or "$" in arg:
                    raise HumanGateViolation("OUT_OF_WORKSPACE_SHELL", f"Path traversal/expansion prohibited in argument: '{arg}'")

        if target_path:
            norm = os.path.realpath(os.path.join(self.workspace_dir, target_path))
            ws = os.path.realpath(self.workspace_dir)
            if not (norm == ws or norm.startswith(ws + os.sep)):
                raise HumanGateViolation("OUT_OF_WORKSPACE_PATH", f"Attempted access outside workspace: '{target_path}' -> '{norm}'")

    def tool_read_file(self, rel_path):
        self._check_security("read_file", target_path=rel_path)
        full = os.path.realpath(os.path.join(self.workspace_dir, rel_path))
        if not os.path.exists(full):
            return f"ERROR: File not found: {rel_path}"
        with open(full, "r", encoding="utf-8") as f:
            content = f.read()
        self.log(f"TOOL-READ-{int(time.time()*1000)%1000000}", self.role, "WORKSPACE", self.current_task_id, "tool_call", 1, 0.0, "EXECUTED", f"tool=read_file path={rel_path}")
        return content

    def tool_write_file(self, rel_path, content):
        if self.role == "PM":
            return "ERROR: PM may not write files. Deliverables must be created by ENG."
        self._check_security("write_file", target_path=rel_path)
        full = os.path.realpath(os.path.join(self.workspace_dir, rel_path))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        self.log(f"TOOL-WRITE-{int(time.time()*1000)%1000000}", self.role, "WORKSPACE", self.current_task_id, "tool_call", 1, 0.0, "EXECUTED", f"tool=write_file path={rel_path}")
        return f"SUCCESS: Wrote {len(content)} bytes to {rel_path}"

    def tool_list_dir(self, rel_path=""):
        self._check_security("list_dir", target_path=rel_path)
        full = os.path.realpath(os.path.join(self.workspace_dir, rel_path))
        if not os.path.exists(full):
            return f"ERROR: Directory not found: {rel_path}"
        items = os.listdir(full)
        self.log(f"TOOL-LIST-{int(time.time()*1000)%1000000}", self.role, "WORKSPACE", self.current_task_id, "tool_call", 1, 0.0, "EXECUTED", f"tool=list_dir path={rel_path}")
        return json.dumps(sorted(items))

    def _is_test_command(self, cmd):
        try:
            argv = shlex.split(cmd)
        except Exception:
            return False
        if not argv or argv[0] != "python3":
            return False
        if len(argv) >= 3 and argv[1:3] in (["-m", "unittest"], ["-m", "pytest"]):
            return True
        if len(argv) >= 2 and bool(re.match(r"^test_\w+\.py$", argv[1])):
            return True
        return False

    def _tests_actually_ran(self, out):
        m = re.search(r"Ran (\d+) tests?", out) or re.search(r"(\d+) passed", out)
        return bool(m) and int(m.group(1)) >= 1

    def tool_run_shell(self, cmd):
        try:
            tokens = shlex.split(cmd)
        except Exception as e:
            return f"ERROR: shlex parse error: {e}"
        self._check_security("run_shell", cmd=cmd, tokens=tokens)
        env = {
            "PATH": os.path.dirname(sys.executable) + ":/usr/bin:/bin",
            "TODO_FILE": os.path.join(self.workspace_dir, ".atom_todos.json"),
            "LANG": "C.UTF-8"
        }
        try:
            # AC-08 Task T-7: Substitute python3 token with sys.executable for conda/pyenv portability
            exec_tokens = list(tokens)
            if exec_tokens and exec_tokens[0] == "python3":
                exec_tokens[0] = sys.executable
            # AC-04 Task O: Execute with shell=False, strictly bounded
            res = subprocess.run(exec_tokens, shell=False, cwd=self.workspace_dir, env=env, capture_output=True, text=True, timeout=30)
            combined_out = (res.stdout + res.stderr)[-4000:]
            # AC-04 Task N & AC-07 Task T-5: Update last_shell state with command output
            self.last_shell = {"task": self.current_task_id, "exit": res.returncode, "cmd": cmd, "out": combined_out}
            self.log(f"TOOL-SHELL-{int(time.time()*1000)%1000000}", self.role, "WORKSPACE", self.current_task_id, "tool_call", 1, 0.0, "EXECUTED", f"tool=run_shell exit={res.returncode}")
            return f"EXIT: {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        except subprocess.TimeoutExpired:
            self.last_shell = {"task": self.current_task_id, "exit": -1, "cmd": cmd, "out": "ERROR: Shell command timed out (30s)"}
            return "ERROR: Shell command timed out (30s)"
        except Exception as e:
            self.last_shell = {"task": self.current_task_id, "exit": -1, "cmd": cmd, "out": f"ERROR: Shell execution failed: {str(e)}"}
            return f"ERROR: Shell execution failed: {str(e)}"

    def _dispatch_tool(self, name, args):
        if name == "write_file":
            return self.tool_write_file(args.get("path", ""), args.get("content", ""))
        elif name == "read_file":
            return self.tool_read_file(args.get("path", ""))
        elif name == "list_dir":
            return self.tool_list_dir(args.get("path", ""))
        elif name == "run_shell":
            return self.tool_run_shell(args.get("cmd", ""))
        else:
            return f"ERROR: Unknown tool '{name}'"

    def raise_human_gate_request(self, task_id, violation_type, detail):
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        req_id = f"REQ-{ts}-{violation_type[:10]}"
        req_path = os.path.join(self.human_gate_dir, f"{req_id}.md")
        content = f"""---
id: {req_id}
task: {task_id}
role: {self.role}
violation: {violation_type}
created: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
status: pending_approval
---

### Human Gate Approval Required
- Action Attempted: {violation_type}
- Details: {detail}
- Instruction: Approval from Principal is strictly required before proceeding.
"""
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.write_guard_log("humangate", f"BLOCKED: {violation_type} on {task_id}. File: {req_path}")
        return req_id

    # ==========================================
    # ATOMIC MESSAGE SENDING
    # ==========================================
    def send_message(self, to_role, in_reply_to, task_id, msg_type, body):
        self.msg_counter += 1
        now = datetime.datetime.now(datetime.timezone.utc)
        msg_id = f"MSG-{now.strftime('%Y%m%d')}-{self.role}-{int(now.timestamp()*1000)%1000000:06d}-{self.msg_counter:04d}"
        raw = format_message(msg_id, self.role, to_role, in_reply_to, task_id, msg_type, body)
        
        target_inbox = self.peer_inbox_dir if to_role == self.peer_role else self.inbox_dir
        tmp_path = os.path.join(target_inbox, f"{msg_id}.tmp")
        final_path = os.path.join(target_inbox, f"{msg_id}.md")
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            
        os.replace(tmp_path, final_path)
        return msg_id, final_path

    # ==========================================
    # GUARD 1: LOOP GUARD
    # ==========================================
    def check_loop_guard(self, task_id):
        done_files = sorted(os.listdir(self.done_dir))
        task_msgs = []
        for fn in done_files:
            # AC-04 Task M: Exclude CLOSED_, DEADLETTER_, REJECTED_, VIOLATION_
            if not fn.endswith(".md") or any(fn.startswith(p) for p in ["CLOSED_", "DEADLETTER_", "REJECTED_", "VIOLATION_"]):
                continue
            fp = os.path.join(self.done_dir, fn)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    meta, _ = parse_frontmatter(f.read())
                    if meta and meta.get("task") == task_id:
                        task_msgs.append((fn, meta))
            except Exception:
                continue

        roundtrips = len(task_msgs)
        if roundtrips >= 30:
            self.write_guard_log("loop", f"TASK {task_id} ROUNDTRIP_LIMIT_EXCEEDED (count={roundtrips} >= 30)")
            self._mark_task_blocked(task_id, f"Loop guard triggered: roundtrip limit {roundtrips} >= 30")
            self.raise_human_gate_request(task_id, "LOOP_LIMIT_EXCEEDED", f"Task roundtrips reached {roundtrips}")
            return False, "ROUNDTRIP_EXCEEDED"

        if len(task_msgs) >= 3:
            last3_shas = [m[1].get("content_sha256") for m in task_msgs[-3:]]
            if last3_shas[0] and last3_shas[0] == last3_shas[1] == last3_shas[2]:
                self.write_guard_log("loop", f"TASK {task_id} IDENTICAL_SHA_LOOP_DETECTED (sha={last3_shas[0]})")
                self._mark_task_blocked(task_id, f"Loop guard triggered: 3 consecutive identical SHA256 ({last3_shas[0]})")
                self.raise_human_gate_request(task_id, "IDENTICAL_PINGPONG_LOOP", f"3 consecutive identical hashes: {last3_shas[0]}")
                return False, "IDENTICAL_PINGPONG_DETECTED"

        return True, "OK"

    def _mark_task_blocked(self, task_id, reason):
        card_path = os.path.join(self.tasks_dir, f"{task_id}.md")
        if os.path.exists(card_path):
            with open(card_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r"status:\s*\w+", "status: blocked", content)
            content += f"\n\n<!-- BLOCKED_REASON: {reason} at {datetime.datetime.now(datetime.timezone.utc).isoformat()} -->\n"
            with open(card_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _mark_task_done_by_pm(self, task_id, decision_id):
        card_path = os.path.join(self.tasks_dir, f"{task_id}.md")
        if os.path.exists(card_path):
            with open(card_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r"status:\s*\w+", "status: done", content)
            content += f"\n<!-- PM_DECISION_ACCEPT: {decision_id} at {datetime.datetime.now(datetime.timezone.utc).isoformat()} -->\n"
            with open(card_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log(decision_id, "PM", "TASKS", task_id, "decision", 0, 0.0, "TASK_MARKED_DONE", f"card={task_id}.md")

    # ==========================================
    # AC-04 Task J: REAL CONTEXT & REAL SUMMARY
    # ==========================================
    def _load_task_history(self, task_id, n=10):
        msgs = []
        if os.path.exists(self.done_dir):
            for fn in os.listdir(self.done_dir):
                # Exclude administrative files
                if not fn.endswith(".md") or any(fn.startswith(p) for p in ["CLOSED_", "DEADLETTER_", "REJECTED_", "VIOLATION_"]):
                    continue
                fp = os.path.join(self.done_dir, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        meta, body = parse_frontmatter(f.read())
                        if meta and meta.get("task") == task_id:
                            msgs.append({
                                "id": meta.get("id"),
                                "from": meta.get("from"),
                                "to": meta.get("to"),
                                "type": meta.get("type"),
                                "created": meta.get("created", ""),
                                "body": body
                            })
                except Exception:
                    continue
        msgs.sort(key=lambda x: x["created"])
        return msgs[-n:]

    def check_and_compress_context(self, task_id, system_prompt, task_card, recent_msgs, token_limit=24000):
        lines = [f"[{m['from']} ({m['id']})]: {m['body']}" for m in recent_msgs]
        combined_text = system_prompt + "\n" + task_card + "\n" + "\n".join(lines)
        est_tokens = int(len(combined_text) / 3.5)

        if est_tokens > token_limit:
            self.write_guard_log("budget", f"BUDGET_EXCEEDED: est_tokens={est_tokens} > limit={token_limit} for {task_id}. Compressing history.")
            # AC-03 Task J / AC-04: No fake sentences! Truncate older messages by ID + first 300 chars
            summary_lines = [f"- {m['id']} ({m['from']}, {m['type']}): {m['body'][:300].strip()}…" for m in recent_msgs]
            summary_content = "# Compressed Task History (Truncated)\n" + "\n".join(summary_lines)
            summary_path = os.path.join(self.ledger_dir, f"summary_{task_id}.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_content)
            self.write_guard_log("budget", f"Truncated history written to {summary_path}.")
            return summary_content
        return "\n".join(lines)

    # ==========================================
    # AC-04 Task Q: OLLAMA /API/CHAT PAYLOAD & LOOP
    # ==========================================
    def _post_chat(self, messages, tools=None, timeout=None):
        if timeout is None:
            timeout = self.llm_timeout
        url = "http://127.0.0.1:11434/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": (self.role == "PM"),
            "options": {
                "num_ctx": self.num_ctx
            }
        }

        if tools:
            payload["tools"] = tools

        # Dump payload sample for audit verification
        sample_path = os.path.join(self.ledger_dir, "ollama_payload_sample.json")
        try:
            with open(sample_path, "w", encoding="utf-8") as sf:
                json.dump(payload, sf, indent=2, ensure_ascii=False)
        except Exception:
            pass

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self.consecutive_5xx = 0
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                self.consecutive_5xx += 1
                self.write_guard_log("watchdog", f"Ollama 5xx encountered ({e.code}), consecutive={self.consecutive_5xx}")
                if self.consecutive_5xx >= 3:
                    self.write_guard_log("watchdog", "Ollama 5xx 3 consecutive times! Entering 30s exponential backoff.")
                    time.sleep(30)
            raise e

    def call_llm_with_watchdog(self, role_prompt, task_card, history_text, task_id="TASK-0001", timeout=None):
        if timeout is None:
            timeout = self.llm_timeout
        start_t = time.time()
        if self.backend == "mock":
            return self._mock_llm_response(role_prompt, task_card, history_text, task_id=task_id)

        tools_schema = self._get_tools_schema()
        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": f"[TASK CARD]\n{task_card}\n\n[CONVERSATION HISTORY]\n{history_text}"}
        ]
        tool_count = 0

        try:
            for _ in range(8):  # Max 8 tool calls per message
                res = self._post_chat(messages, tools=tools_schema, timeout=timeout)
                msg = res.get("message", {})
                messages.append(msg)
                calls = msg.get("tool_calls") or []

                if not calls:
                    return msg.get("content", ""), tool_count

                for c in calls:
                    fn = c.get("function", {}).get("name", "")
                    raw_args = c.get("function", {}).get("arguments", {})
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception as je:
                        self.write_guard_log("watchdog", f"JSON_PARSE_ERROR: tool={fn} raw_args='{raw_args}' err={je}")
                        out = f"ERROR: Invalid JSON in arguments: {je}"
                        messages.append({"role": "tool", "tool_name": fn, "content": str(out)})
                        continue
                    out = self._dispatch_tool(fn, args)  # HumanGateViolation will propagate cleanly
                    messages.append({"role": "tool", "tool_name": fn, "content": str(out)})
                    tool_count += 1

            self.write_guard_log("watchdog", f"TOOL_LIMIT_REACHED: task={task_id} tool_count={tool_count}")
            return "[TOOL_LIMIT_REACHED]", tool_count

        except Exception as e:
            elapsed = time.time() - start_t
            if elapsed >= timeout:
                self.write_guard_log("watchdog", f"WATCHDOG: LLM call timed out after {elapsed:.1f}s >= {timeout}s (timeout={timeout}s).")
            raise e

    def _mock_llm_response(self, role_prompt, task_card, history_text, task_id="TASK-0001"):
        # Isolated mock response engine for tests/test_protocol.py
        if self.role == "PM":
            if "report" in history_text:
                # Mock PM runs unit test directly using run_shell to verify Task N
                test_output = self.tool_run_shell("python3 -m unittest test_todo.py")
                if "OK" in test_output or "EXIT: 0" in test_output:
                    return f"[PM REVIEW] Task {task_id}: Tested successfully.\nDECISION: ACCEPT"
                return f"[PM REVIEW] Task {task_id}: Tests failed.\nDECISION: REJECT"
            return f"[PM ASSIGN] Task {task_id}: Please implement deliverables in workspace/ and report.\nDECISION: CONTINUE"
        else: # ENG
            return f"[ENG REPORT] Task {task_id}: Completed implementation in workspace.\nEXIT: 0\nSTDOUT: Unit test passed."

    # ==========================================
    # INBOX POLLING & MESSAGE PROCESSING
    # ==========================================
    def process_one_message(self):
        inbox_files = sorted([f for f in os.listdir(self.inbox_dir) if f.endswith(".md")])
        if not inbox_files:
            return False

        msg_file = inbox_files[0]
        msg_path = os.path.join(self.inbox_dir, msg_file)
        start_time = time.time()
        task_id = "TASK-0001"

        try:
            with open(msg_path, "r", encoding="utf-8") as f:
                raw_msg = f.read()

            is_valid, reason = validate_message(raw_msg)
            if not is_valid:
                self.log(msg_file, "UNKNOWN", self.role, "UNKNOWN", "invalid", 0, 0, "REJECTED", reason)
                os.replace(msg_path, os.path.join(self.done_dir, f"REJECTED_{msg_file}"))
                return True

            meta, body = parse_frontmatter(raw_msg)
            task_id = meta.get("task", "TASK-0001")
            self.current_task_id = task_id
            in_reply_to = meta.get("id")
            self.last_shell = None  # AC-06 T-2: Reset last_shell per message processing
            
            # AC-04 Task M: Thread Completion & Termination Check
            task_card_path = os.path.join(self.tasks_dir, f"{task_id}.md")
            task_status = "todo"
            if os.path.exists(task_card_path):
                with open(task_card_path, "r", encoding="utf-8") as f:
                    card_txt = f.read()
                sm = re.search(r"status:\s*([a-zA-Z_]+)", card_txt)
                if sm:
                    task_status = sm.group(1).lower()

            is_decision_to_eng = (self.role == "ENG" and meta.get("type") == "decision")
            if task_status in ["done", "blocked"] or is_decision_to_eng:
                closed_dest = os.path.join(self.done_dir, f"CLOSED_{msg_file}")
                os.replace(msg_path, closed_dest)
                self.log(msg_file, meta.get("from"), self.role, task_id, meta.get("type"), 0, 0.0, "CLOSED", f"status={task_status} is_decision={is_decision_to_eng}")
                return True

            # 1. Execute Loop Guard check
            loop_ok, loop_reason = self.check_loop_guard(task_id)
            if not loop_ok:
                self.log(meta.get("id"), meta.get("from"), self.role, task_id, meta.get("type"), 0, 0, "BLOCKED", loop_reason)
                os.replace(msg_path, os.path.join(self.done_dir, f"BLOCKED_{msg_file}"))
                return True

            # 2. Build Prompt with real history (AC-03 Task J)
            role_prompt_path = os.path.join(self.roles_dir, f"{self.role}.md")
            role_prompt = ""
            if os.path.exists(role_prompt_path):
                with open(role_prompt_path, "r", encoding="utf-8") as f:
                    role_prompt = f.read()

            history_msgs = self._load_task_history(task_id, n=10)
            history_msgs.append({
                "id": meta.get("id"),
                "from": meta.get("from"),
                "to": meta.get("to"),
                "type": meta.get("type"),
                "created": meta.get("created", ""),
                "body": body
            })
            history_text = self.check_and_compress_context(task_id, role_prompt, card_txt if os.path.exists(task_card_path) else "", history_msgs)

            # 3. Call LLM (with Native Tools Loop)
            response_tuple = self.call_llm_with_watchdog(role_prompt, card_txt if os.path.exists(task_card_path) else "", history_text, task_id=task_id)
            if isinstance(response_tuple, tuple):
                response_text, tool_calls_count = response_tuple
            else:
                response_text, tool_calls_count = response_tuple, 0

            # 4. AC-04 Task N: Objective verification for PM ACCEPT decision
            if self.role == "PM":
                m = re.search(r"^DECISION:\s*(ACCEPT|REJECT|CONTINUE)\s*$", response_text, re.M)
                verdict = m.group(1) if m else "CONTINUE"

                # Check if PM directly executed automated unit test in workspace and confirmed exit 0 with >= 1 tests run
                pm_executed_valid_test = (
                    self.last_shell is not None
                    and self.last_shell.get("task") == task_id
                    and self.last_shell.get("exit") == 0
                    and self._is_test_command(self.last_shell.get("cmd", ""))
                    and self._tests_actually_ran(self.last_shell.get("out", ""))
                )

                if verdict == "ACCEPT":
                    if not (meta.get("type") == "report" and pm_executed_valid_test):
                        # Demote to CONTINUE + System Rejection notice
                        verdict = "CONTINUE"
                        response_text += "\n[SYSTEM] Rejection: PM must directly execute automated test suite in workspace and observe EXIT: 0 before issuing ACCEPT."
                        self.write_guard_log("watchdog", f"ACCEPT_DEMOTION: task={task_id} type={meta.get('type')} pm_test={pm_executed_valid_test}")

                is_done_decision = (verdict == "ACCEPT")
                resp_type = {"ACCEPT": "decision", "REJECT": "review", "CONTINUE": "assign"}[verdict]
                out_id, out_path = self.send_message(self.peer_role, in_reply_to, task_id, resp_type, response_text)
                if is_done_decision:
                    self._mark_task_done_by_pm(task_id, out_id)
            else:
                resp_type = "report"
                out_id, out_path = self.send_message(self.peer_role, in_reply_to, task_id, resp_type, response_text)

            # 5. Move processed message to done/
            done_dest = os.path.join(self.done_dir, msg_file)
            os.replace(msg_path, done_dest)

            latency_ms = (time.time() - start_time) * 1000.0
            self.log(out_id, self.role, self.peer_role, task_id, resp_type, tool_calls_count, latency_ms, "PROCESSED", f"in_reply_to={in_reply_to} decision={verdict if self.role == 'PM' else 'None'}")
            return True

        except HumanGateViolation as hgv:
            self.raise_human_gate_request(task_id, hgv.reason, hgv.details)
            self.log(msg_file, self.role, self.peer_role, task_id, "humangate", 0, 0.0, "BLOCKED", hgv.reason)
            os.replace(msg_path, os.path.join(self.done_dir, f"VIOLATION_{msg_file}"))
            return True
        except Exception as e:
            # AC-03 Task H: Retry limit & Deadletter handling
            n = self.retry_count.get(msg_file, 0) + 1
            self.retry_count[msg_file] = n
            self.log(msg_file, "SYSTEM", self.role, task_id, "error", 0, 0.0, "ERROR", f"retry={n} {e}")
            if n >= 3:
                deadletter_dest = os.path.join(self.done_dir, f"DEADLETTER_{msg_file}")
                os.replace(msg_path, deadletter_dest)
                self._mark_task_blocked(task_id, f"deadletter after {n} retries: {e}")
                self.raise_human_gate_request(task_id, "DEADLETTER", str(e))
                self.write_guard_log("watchdog", f"DEADLETTER {msg_file} task={task_id} retry={n} error={e}")
            return False

    def run_loop(self, max_iterations=None):
        count = 0
        while True:
            processed = self.process_one_message()
            if processed:
                count += 1
                if max_iterations and count >= max_iterations:
                    break
            else:
                if max_iterations and count >= max_iterations:
                    break
                time.sleep(self.poll_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atom Company Agent Runner")
    parser.add_argument("--role", required=True, choices=["PM", "ENG"], help="Agent role")
    parser.add_argument("--model", default="gemma4:e4b", help="Model name tag")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "mock"], help="LLM backend")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Root directory")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--llm-timeout", type=float, default=120.0, help="LLM request timeout in seconds (default: 120.0)")
    parser.add_argument("--num-ctx", type=int, default=16384, help="LLM context window size in tokens (default: 16384)")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max messages to process before exit")
    parser.add_argument("--once", action="store_true", help="Process 1 message and exit (smoke test)")

    args = parser.parse_args()
    agent = AgentRuntime(args.role, model=args.model, backend=args.backend, root=args.root,
                         poll_interval=args.poll_interval, llm_timeout=args.llm_timeout, num_ctx=args.num_ctx)

    if args.once:
        agent.process_one_message()
    else:
        agent.run_loop(max_iterations=args.max_iterations)
