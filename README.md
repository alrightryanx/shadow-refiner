# ShadowRefiner 🛡️✨

**Universal Intent Reconstruction & Quality Refinement Layer for AI CLIs.**

ShadowRefiner is a high-performance cognitive middleware designed to bridge the gap between "lazy" human thoughts and "high-fidelity" AI execution. It intercepts terminal-based AI interactions (Claude Code, Gemini, Codex) to ensure every prompt is optimized and every response meets executive standards.

## 🚀 The Core Philosophy

ShadowRefiner operates on the principle of **Aggressive Intent Reconstruction**. Instead of merely blocking poor prompts, it uses local context to rebuild them into professional instructions. It is the "Chief of Staff" for your terminal.

### Key Capabilities:
*   **Cognitive Filtering:** Analyzes entropy and intent. Kills nonsensical "sit-on-keyboard" input (<15 score).
*   **Prompt Reconstruction:** Re-engineers vague commands (e.g., "fix it") into technical plans using local environmental cues (CWD, recently touched files).
*   **Active Circuit Breaking:** Aborts requests that are guaranteed to fail, saving tokens and time.
*   **Response Auditing:** Monitors AI output for hallucinations or logic errors and triggers automatic re-rolls (`/regenerate`) if quality is subpar.
*   **Secret Firewall:** Scans and masks API keys, passwords, and PII before cloud transmission.

## 🛠️ Architecture

ShadowRefiner sits as a lightweight Python layer utilizing local inference for maximum privacy and speed.

1.  **Hooks:** Native integrations for `claude-code` and `gemini-cli` intercept traffic.
2.  **Engine:** Powered by **Local GLM 4.7 (Ollama)**, performing high-speed "Cognitive Audits."
3.  **Relay:** Communicates via **ShadowBridge** to provide unified Windows Toast and Android push notifications.
4.  **Cache:** JSON-based persistence layer ensures 0ms overhead for repeat commands.

## 📦 Installation

```bash
git clone https://github.com/alrightryanx/shadow-refiner.git
cd shadow-refiner
pip install -r requirements.txt
```

### Requirements:
*   Python 3.10+
*   [Ollama](https://ollama.ai/) running locally with `glm-4.7` (installed automatically during setup).

## ⚙️ Configuration

Tune your refinement thresholds in `config.json`:

```json
{
  "thresholds": {
    "block": 15,
    "improve": 90
  },
  "safe_commands": [
    "ls", "git status", "npm start"
  ]
}
```

## 🔌 Integrations

Included in this repository are pre-built hooks for:
*   **Claude Code:** Advanced `.claude-plugin` system.
*   **Gemini CLI:** Node.js bridge relay.
*   **ShadowBridge:** Centralized session auditing for all other CLIs (Codex, OpenCode).

---
**Part of the ShadowAI Ecosystem.**
