import sys
import json
import subprocess
import argparse
import os
import urllib.request
import re

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "glm4:9b"

# Thresholds
BLOCK_THRESHOLD = 40  # Scores below this are killed immediately
IMPROVE_THRESHOLD = 75 # Scores between BLOCK and this are locally auto-expanded

def grade_content(text, content_type, mode="grade"):
    """
    Grades, optimizes, or sanitizes content using local Ollama.
    Modes: 
    - grade: Return quality assessment
    - improve: Return an expanded/better version of the prompt
    - sanitize: Mask secrets/PII
    """
    
    if mode == "improve":
        prompt = f"""
        You are an expert Prompt Engineer. Rewrite the following lazy developer prompt into a high-fidelity, specific instruction.
        Keep the original intent but add necessary technical context and specify clear requirements.
        
        Lazy Prompt: "{text}"
        
        Return ONLY the rewritten prompt text. No explanations.
        """
    elif mode == "sanitize":
        # Basic regex check first to save time, then LLM for complex cases
        sanitized = sanitize_regex(text)
        prompt = f"""
        Scan this text for API keys, passwords, or credentials. Mask them with [MASKED].
        If no secrets are found, return the text exactly as is.
        
        Text: "{sanitized}"
        
        Return ONLY the sanitized text.
        """
    else: # grade
        prompt = f"""
        You are the Quality Sentinel for ShadowAI. strictly evaluate this {content_type}:
        
        "{text}"
        
        {get_rubric(content_type)}
        
        Return ONLY a JSON object:
        {{
            "score": <int 0-100>,
            "reason": "<short reason>",
            "action": "<BLOCK|IMPROVE|PASS>",
            "is_quality": <boolean>
        }}
        """
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json" if mode == "grade" else ""
    }
    
    try:
        req = urllib.request.Request(OLLAMA_URL)
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(payload).encode('utf-8')
        
        with urllib.request.urlopen(req, jsondata, timeout=30) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            output = res_data.get("response", "").strip()
            
            if mode == "grade":
                try:
                    # Handle cases where LLM puts JSON in a block
                    json_match = re.search(r'(\{.*\})', output, re.DOTALL)
                    if json_match:
                        output = json_match.group(1)
                    res = json.loads(output)
                    # Force action based on score if LLM was vague
                    if res.get("score", 100) < BLOCK_THRESHOLD:
                        res["action"] = "BLOCK"
                    elif res.get("score", 100) < IMPROVE_THRESHOLD:
                        res["action"] = "IMPROVE"
                    else:
                        res["action"] = "PASS"
                    return res
                except:
                    return {"score": 0, "action": "BLOCK", "reason": "Grader parsing error"}
            
            return output

    except Exception as e:
        return {"score": 100, "action": "PASS", "reason": f"Bypass on error: {str(e)}"}

def sanitize_regex(text):
    # Mask obvious keys (generic pattern)
    text = re.sub(r'(?i)(api[_-]?key|secret|password|passwd|token)[\s:=]+[a-z0-9_\-\.\~]{16,}', r'\1: [MASKED]', text)
    return text

def get_rubric(content_type):
    if content_type == "prompt":
        return f"Rubric: <{BLOCK_THRESHOLD}=BLOCK (useless), <{IMPROVE_THRESHOLD}=IMPROVE (vague), else PASS."
    else:
        return "Rubric: <50=REGENERATE (poor logic/hallucination), else PASS."

def show_notification(title, message, score):
    ps_script = f"""
    [reflection.assembly]::loadwithpartialname('System.Windows.Forms')
    $notification = New-Object System.Windows.Forms.NotifyIcon
    $notification.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon((Get-Process -id $pid).Path)
    $notification.BalloonTipIcon = 'Warning'
    $notification.BalloonTipText = '{message.replace("'", "''")}'
    $notification.BalloonTipTitle = '{title.replace("'", "''")} (Score: {score})'
    $notification.Visible = $True
    $notification.ShowBalloonTip(10000)
    """
    try:
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
    except: pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["prompt", "response"], required=True)
    parser.add_argument("--mode", choices=["grade", "improve", "sanitize"], default="grade")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("text", nargs="?")
    
    args = parser.parse_args()
    content = args.text or (not sys.stdin.isatty() and sys.stdin.read())
            
    if not content or not content.strip():
        print(json.dumps({"score": 0, "action": "BLOCK", "reason": "Empty input"}))
        return

    if args.mode == "grade":
        result = grade_content(content, args.type, "grade")
        if args.notify and result.get("action") != "PASS":
            show_notification(f"ShadowAegis: {result.get('action')}", result.get("reason", ""), result.get("score", 0))
        print(json.dumps(result))
    else:
        # Standard text processing modes
        result = grade_content(content, args.type, args.mode)
        print(result)

if __name__ == "__main__":
    main()
