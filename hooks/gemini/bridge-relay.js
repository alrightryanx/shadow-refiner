#!/usr/bin/env node

/**
 * Gemini Shadow - Universal Hook Relay
 * Replaces platform-specific scripts with a single Node.js implementation
 * for cross-platform compatibility.
 */

const net = require('net');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const { execSync } = require('child_process');

const BRIDGE_PORT = 19286;
const BRIDGE_HOST = "127.0.0.1";
const CONFIG_FILE = path.join(os.homedir(), '.gemini-shadow-config.json');
const DEBUG_LOG = path.join(os.homedir(), '.gemini-shadow-debug.log');
const REFINER_SCRIPT = "C:\\shadow\\shadow-refiner\\core\\engine.py";

// Hook type passed as first argument
const hookType = process.argv[2];

function runSentinel(text, type, mode = "grade") {
    try {
        if (!fs.existsSync(REFINER_SCRIPT)) return null;
        
        // Escape quotes for shell
        const escapedText = text.replace(/"/g, '\\"').replace(/\n/g, ' ');
        const cmd = `python "${REFINER_SCRIPT}" --type ${type} --mode ${mode} "${escapedText}"`;
        const output = execSync(cmd, { encoding: 'utf8' });
        
        if (mode === "grade") {
            return JSON.parse(output);
        }
        return output.trim();
    } catch (e) {
        logDebug(`Sentinel error: ${e.message}`);
        return null;
    }
}

function logDebug(message) {
    const ts = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const logLine = `[${ts}] ${message}${os.EOL}`;
    try {
        fs.appendFileSync(DEBUG_LOG, logLine);
    } catch (e) {
        // Silently fail if log file is not writable
    }
}

function getConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const data = fs.readFileSync(CONFIG_FILE, 'utf8');
            return JSON.parse(data);
        }
    } catch (e) {
        logDebug(`Error reading config: ${e.message}`);
    }
    return {
        bridgeHost: BRIDGE_HOST,
        bridgePort: BRIDGE_PORT,
        enabled: true
    };
}

function generateId(prefix = "msg") {
    const guid = crypto.randomBytes(4).toString('hex');
    const seconds = Math.floor(Date.now() / 1000);
    return `${prefix}_${seconds}_${guid}`;
}

function getProjectName(cwd) {
    if (!cwd) return "unknown";
    const name = path.basename(cwd);
    return name.replace(/-main$|-master$|-dev$/, "");
}

function getFriendlyToolDescription(toolName, toolInput) {
    if (!toolInput) return toolName;
    
    switch (toolName) {
        case "run_shell_command":
            let cmd = toolInput.command || "";
            if (cmd.length > 80) cmd = cmd.substring(0, 80) + "...";
            return `Run: ${cmd}`;
        case "read_file":
            return `Read: ${path.basename(toolInput.file_path || toolInput.path || "file")}`;
        case "write_file":
            return `Create: ${path.basename(toolInput.file_path || toolInput.path || "file")}`;
        case "replace":
            return `Edit: ${path.basename(toolInput.file_path || toolInput.path || "file")}`;
        case "glob":
            return `Find files: ${toolInput.pattern || "*"}`;
        case "search_file_content":
            let pattern = toolInput.pattern || toolInput.query || "";
            if (pattern.length > 40) pattern = pattern.substring(0, 40) + "...";
            return `Search: ${pattern}`;
        default:
            return toolName;
    }
}

async function readStdin() {
    return new Promise((resolve) => {
        let data = '';
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', (chunk) => {
            data += chunk;
        });
        process.stdin.on('end', () => {
            try {
                resolve(JSON.parse(data || '{}'));
            } catch (e) {
                logDebug(`Error parsing stdin JSON: ${e.message}`);
                resolve({});
            }
        });
        
        // Timeout for stdin if nothing is piped
        setTimeout(() => {
            if (data === '') resolve({});
        }, 500);
    });
}

function sendToBridge(message, timeoutMs = 10000) {
    return new Promise((resolve) => {
        const config = getConfig();
        if (config.enabled === false) {
            return resolve({ error: 'disabled' });
        }

        const client = new net.Socket();
        let resolved = false;

        const cleanup = () => {
            if (!resolved) {
                resolved = true;
                client.destroy();
            }
        };

        const timer = setTimeout(() => {
            logDebug("Bridge connection timed out");
            cleanup();
            resolve({ error: 'timeout' });
        }, timeoutMs);

        client.connect(config.bridgePort || BRIDGE_PORT, config.bridgeHost || BRIDGE_HOST, () => {
            // Send length-prefixed handshake
            const handshake = JSON.stringify({ type: "handshake" });
            const handshakeBuf = Buffer.from(handshake);
            const lenBuf = Buffer.alloc(4);
            lenBuf.writeInt32BE(handshakeBuf.length);
            
            client.write(lenBuf);
            client.write(handshakeBuf);
        });

        let phase = 'handshake';
        let buffer = Buffer.alloc(0);

        client.on('data', (chunk) => {
            buffer = Buffer.concat([buffer, chunk]);
            
            while (buffer.length >= 4) {
                const len = buffer.readInt32BE(0);
                if (buffer.length < 4 + len) break;
                
                const msgData = buffer.slice(4, 4 + len).toString();
                buffer = buffer.slice(4 + len);
                
                try {
                    const response = JSON.parse(msgData);
                    
                    if (phase === 'handshake') {
                        if (response.type === 'handshake_ack') {
                            phase = 'message';
                            const payload = JSON.stringify(message);
                            const payloadBuf = Buffer.from(payload);
                            const pLenBuf = Buffer.alloc(4);
                            pLenBuf.writeInt32BE(payloadBuf.length);
                            
                            client.write(pLenBuf);
                            client.write(payloadBuf);
                        } else {
                            logDebug(`Handshake failed: unexpected response ${response.type}`);
                            clearTimeout(timer);
                            cleanup();
                            resolve({ error: 'handshake_failed' });
                        }
                    } else {
                        // Response to our actual message
                        clearTimeout(timer);
                        cleanup();
                        resolve(response);
                    }
                } catch (e) {
                    logDebug(`Error parsing bridge response: ${e.message}`);
                }
            }
        });

        client.on('error', (err) => {
            logDebug(`Bridge connection error: ${err.message}`);
            clearTimeout(timer);
            cleanup();
            resolve({ error: err.message });
        });

        client.on('close', () => {
            if (!resolved) {
                clearTimeout(timer);
                resolve({ type: 'ack' }); // Generic ack if closed without response
            }
        });
    });
}

async function run() {
    logDebug(`Hook Relay invoked for: ${hookType}`);
    const hookInput = await readStdin();
    const config = getConfig();
    
    const sessionId = hookInput.session_id || hookInput.sessionId || `gemini_${Math.floor(Date.now()/1000)}`;
    const cwd = hookInput.cwd || hookInput.working_directory || process.cwd();
    const projectName = getProjectName(cwd);

    let messageType = "";
    let payload = {
        hostname: os.hostname(),
        cwd: cwd,
        projectName: projectName,
        provider: "gemini"
    };

    switch (hookType) {
        case 'UserPromptSubmit':
            let userPrompt = hookInput.prompt || "";
            
            if (userPrompt) {
                // 1. Sanitize Secrets
                const sanitized = runSentinel(userPrompt, "prompt", "sanitize");
                if (sanitized && sanitized !== userPrompt) {
                    userPrompt = sanitized;
                }

                // 2. Grade and Intervene
                const grade = runSentinel(userPrompt, "prompt", "grade");
                if (grade) {
                    if (grade.action === "BLOCK") {
                        await sendToBridge({
                            type: "notification",
                            sessionId: sessionId,
                            payload: {
                                ...payload,
                                message: `🚫 ShadowRefiner Blocked Prompt: ${grade.reason}`,
                                summary: "ShadowRefiner: Blocked",
                                notificationType: "error"
                            }
                        });
                        console.error(`ShadowRefiner blocked this prompt: ${grade.reason}`);
                        process.exit(1);
                    } else if (grade.action === "IMPROVE") {
                        const improved = runSentinel(userPrompt, "prompt", "improve");
                        if (improved) {
                            userPrompt = improved;
                            await sendToBridge({
                                type: "notification",
                                sessionId: sessionId,
                                payload: {
                                    ...payload,
                                    message: "✨ ShadowRefiner auto-improved your vague prompt.",
                                    summary: "ShadowRefiner: Improved",
                                    notificationType: "info"
                                }
                            });
                        }
                    }
                }
            }
            
            messageType = "session_message";
            payload.role = "user";
            payload.content = userPrompt;
            break;

        case 'AfterAgent':
            const assistantResponse = hookInput.response || hookInput.content || "";
            if (assistantResponse) {
                const grade = runSentinel(assistantResponse, "response", "grade");
                if (grade && (grade.action === "REGENERATE" || grade.score < 50)) {
                    await sendToBridge({
                        type: "notification",
                        sessionId: sessionId,
                        payload: {
                            ...payload,
                            message: `⚠️ ShadowRefiner detected poor response: ${grade.reason}`,
                            summary: "ShadowRefiner: Quality Warning",
                            notificationType: "error",
                            options: ["Regenerate", "Dismiss"]
                        }
                    });
                }
            }
            messageType = "after_agent";
            break;

        case 'Notification':
        case 'AfterTool':
            messageType = "after_tool";
            payload.toolName = hookInput.tool_name || hookInput.toolName || hookInput.name || "";
            payload.success = hookInput.success !== false;
            break;
        case 'BeforeTool':
            const toolName = hookInput.tool_name || hookInput.toolName || hookInput.name || "";
            const toolInput = hookInput.tool_input || hookInput.toolInput || hookInput.input || {};
            
            const dangerousTools = ["run_shell_command", "write_file", "replace", "delete_file"];
            if (dangerousTools.includes(toolName)) {
                const requestId = generateId("req");
                const description = getFriendlyToolDescription(toolName, toolInput);
                
                const response = await sendToBridge({
                    type: "permission_request",
                    id: generateId(),
                    sessionId: sessionId,
                    timestamp: Date.now(),
                    provider: "gemini",
                    payload: {
                        ...payload,
                        requestId: requestId,
                        toolName: toolName,
                        toolInput: toolInput,
                        description: description,
                        options: ["Approve", "Deny", "Always Allow"],
                        promptType: "PERMISSION"
                    }
                }, 60000); // 60s timeout for permission

                const approved = response.approved !== undefined ? response.approved : response.allow;
                if (response.type === "approval_response" && (approved === true || approved === "true")) {
                    logDebug(`Tool ${toolName} approved`);
                    console.log(JSON.stringify({ continue: true }));
                } else {
                    logDebug(`Tool ${toolName} denied`);
                    console.log(JSON.stringify({ continue: false, reason: "User denied permission via ShadowAI" }));
                }
                return;
            }
            
            // Auto-allow safe tools
            console.log(JSON.stringify({ continue: true }));
            return;

        default:
            logDebug(`Unknown hook type: ${hookType}`);
            return;
    }

    if (messageType) {
        await sendToBridge({
            type: messageType,
            id: generateId(),
            sessionId: sessionId,
            timestamp: Date.now(),
            provider: "gemini",
            payload: payload
        });
    }
}

run().catch(err => {
    logDebug(`Fatal error in hook relay: ${err.stack}`);
    // Ensure we don't block the CLI on fatal relay errors
    if (hookType === 'BeforeTool') {
        console.log(JSON.stringify({ continue: true }));
    }
});
