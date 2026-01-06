import sys
import json
import subprocess
import argparse
import os
import urllib.request
import re
import time
from pathlib import Path

CONFIG_PATH = Path("C:/shadow/shadow-refiner/config.json")

# New Policy: Aggressive Reconstruction
# Only block literal garbage (<15). Improve everything else (<90).
BLOCK_THRESHOLD = 15
IMPROVE_THRESHOLD = 90

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"safe_commands": [], "engine": {"model": "glm4:9b", "ollama_url": "http://127.0.0.1:11434"}}

CONFIG = load_config()

def get_cache():
    cache_path = Path(CONFIG.get("paths", {}).get("cache", "C:/shadow/shadow-refiner/core/cache.json"))
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except: pass
    return {}

def save_cache(cache):
    cache_path = Path(CONFIG.get("paths", {}).get("cache", "C:/shadow/shadow-refiner/core/cache.json"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(cache, f)

def grade_content(text, content_type, mode="grade"):
    # 1. Check Skip-List (Instant)
    if content_type == "prompt" and text.strip().lower() in CONFIG.get("safe_commands", []):
        return {"score": 100, "action": "PASS", "reason": "Safe command detected", "is_quality": True}

    # 2. Check Cache
    cache = get_cache()
    cache_key = f"{content_type}_{mode}_{text}"
    if cache_key in cache:
        return cache[cache_key]

    # 3. Local LLM Logic
    result = call_ollama(text, content_type, mode)
    
    # Save to Cache
    if isinstance(result, dict):
        cache[cache_key] = result
        save_cache(cache)
    
    return result

def call_ollama(text, content_type, mode):
    url = f"{CONFIG['engine']['ollama_url']}/api/generate"
    
    # GATHER CONTEXT
    cwd = os.getcwd()
    recent_files = []
    try:
        files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.startswith('.')]
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        recent_files = files[:3]
    except: pass

    if mode == "improve":
        prompt = f"""
        You are the Executive Intent Reconstructor. 
        Expand this "lazy" developer prompt into a high-fidelity instruction.
        
        CONTEXT:
        - Current Directory: {cwd}
        - Recent Files: {recent_files}
        
        LAZY PROMPT: "{text}"
        
        INSTRUCTIONS:
        - Infer the technical goal based on the prompt and context.
        - If they say "fix it", they likely mean errors in {recent_files}.
        - If they say "build", they mean the project in {cwd}.
        - Return ONLY the improved prompt text. No chat.
        """
    elif mode == "sanitize":
        prompt = f"Security Audit: Mask API keys/passwords in this text with [MASKED]. Return sanitized text ONLY: '{text}'"
    else: # grade
        prompt = f"""
        Executive Quality Audit. Evaluate this {content_type}: "{text}"
        
        Rubric:
        - score < {BLOCK_THRESHOLD}: BLOCK (literal garbage/nonsense)
        - score < {IMPROVE_THRESHOLD}: IMPROVE (vague or lazy but has intent)
        - else: PASS (clear and high fidelity)
        
        Return ONLY JSON: {{"score": 0-100, "reason": "...", "action": "BLOCK|IMPROVE|PASS"}}
        """

    payload = {
        "model": CONFIG["engine"]["model"],
        "prompt": prompt,
        "stream": False,
        "format": "json" if mode == "grade" else ""
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            output = res_data.get("response", "").strip()
            
            if mode == "grade":
                try:
                    json_match = re.search(r'(\{.*\})', output, re.DOTALL)
                    res = json.loads(json_match.group(1)) if json_match else json.loads(output)
                    score = res.get("score", 100)
                    if score < BLOCK_THRESHOLD: res["action"] = "BLOCK"
                    elif score < IMPROVE_THRESHOLD: res["action"] = "IMPROVE"
                    else: res["action"] = "PASS"
                    return res
                except:
                    return {"score": 50, "action": "IMPROVE", "reason": "Format error, fallback to improvement"}
            return output
    except Exception as e:
        return {"score": 100, "action": "PASS", "reason": f"Bypass on error: {str(e)}"}

def show_notification(title, message, score):
    ps_script = f"""
    [reflection.assembly]::loadwithpartialname('System.Windows.Forms')
    $notification = New-Object System.Windows.Forms.NotifyIcon
    $notification.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon((Get-Process -id $pid).Path)
    $notification.BalloonTipIcon = 'Info'
    $notification.BalloonTipText = '{message.replace("'", "''")}'
    $notification.BalloonTipTitle = '{title.replace("'", "''")} (Score: {score})'
    $notification.Visible = $True
    $notification.ShowBalloonTip(5000)
    """
    subprocess.run(["powershell", "-Command", ps_script], capture_output=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["prompt", "response"], required=True)
    parser.add_argument("--mode", choices=["grade", "improve", "sanitize"], default="grade")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("text", nargs="?")
    args = parser.parse_args()
    content = args.text or (not sys.stdin.isatty() and sys.stdin.read())
    if not content: return

    result = grade_content(content, args.type, args.mode)
    
    if args.mode == "grade":
        if args.notify and result.get("action") != "PASS":
            show_notification(f"ShadowRefiner: {result.get('action')}", result.get("reason", ""), result.get("score", 0))
        print(json.dumps(result))
    else:
        print(result)

if __name__ == "__main__":
    main()
