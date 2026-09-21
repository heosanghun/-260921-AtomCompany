import os
import subprocess
import datetime

root = "/home/sims/auto/atom-company"
os.makedirs(os.path.join(root, "ledger"), exist_ok=True)
ledger_file = os.path.join(root, "ledger", "ENV_LOCK.txt")

def run(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

lines = []
lines.append("=== ENV_LOCK.txt ===")
lines.append(f"GENERATED_AT: {datetime.datetime.now().isoformat()}")
lines.append(f"ROOT_DIR: {root}")

# 1. Ollama Version
code, out, err = run("ollama --version")
lines.append(f"[OLLAMA_VERSION_STATUS] code={code}")
val = out if code == 0 else (err or "COMMAND_NOT_FOUND")
lines.append(f"OLLAMA_VERSION: {val}")

# 2. NVIDIA-SMI / GPU VRAM
code, out, err = run("nvidia-smi --query-gpu=name,memory.total --format=csv")
lines.append(f"[NVIDIA_SMI_STATUS] code={code}")
val = out if code == 0 else (err or "DRIVER_COMMUNICATION_FAILED")
lines.append(f"GPU_SPECS: {val}")

# 3. Model manifests / Ollama list
code, out, err = run("ollama list")
lines.append(f"[OLLAMA_LIST_STATUS] code={code}")
val = out if code == 0 else (err or "UNAVAILABLE")
lines.append(f"OLLAMA_LIST: {val}")

# 4. Manifest hashes
code, out, err = run("sha256sum ~/.ollama/models/manifests/registry.ollama.ai/library/gemma4/*")
lines.append(f"[OLLAMA_MANIFEST_SHA256_STATUS] code={code}")
val = out if code == 0 else (err or "NOT_FOUND")
lines.append(f"OLLAMA_MANIFEST_SHA256: {val}")

# 5. Local HF Cache & System info (Additional ground truth pointer)
code, out, err = run("ls -la /home/sims/.cache/huggingface/hub/models--google--gemma-4-e4b-it/ 2>&1")
lines.append(f"[HF_CACHE_GEMMA4_STATUS] code={code}")
lines.append(f"HF_CACHE_GEMMA4_INFO: {out.splitlines()[0] if out else err}")

code, out, err = run("uname -a")
lines.append(f"OS_KERNEL: {out}")

with open(ledger_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"ENV_LOCK.txt written to {ledger_file}")
