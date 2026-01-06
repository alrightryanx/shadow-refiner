# Claude Code Companion - User Prompt Hook
# Sends user prompts to the phone for conversation sync

. "$PSScriptRoot\companion-common.ps1"

# Debug logging
$logFile = "$env:USERPROFILE\.claude-shadow-debug.log"
$contextCacheFile = "$env:USERPROFILE\.claude-shadow-context.json"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] User-prompt hook invoked" | Add-Content $logFile

# Read hook input from stdin
$hookInput = Read-HookInput
if (-not $hookInput) {
    "[$timestamp] No hook input, exiting" | Add-Content $logFile
    exit 0
}

$sessionId = $hookInput.session_id
$prompt = $hookInput.prompt
$cwd = $hookInput.cwd

"[$timestamp] User prompt: sessionId=$sessionId, prompt=$($prompt.Substring(0, [Math]::Min(50, $prompt.Length)))..." | Add-Content $logFile

# --- ACTIVE SENTINEL INTERVENTION ---
$finalPrompt = $prompt

# 1. Sanitize Secrets (Blocking/Masking)
$sanitized = Invoke-Sentinel -Text $prompt -Type "prompt" -Mode "sanitize"
if ($sanitized -and $sanitized -ne $prompt) {
    "[$timestamp] Sentinel: Secrets masked" | Add-Content $logFile
    $finalPrompt = $sanitized
}

# 2. Grade and Decide Action
$grade = Invoke-Sentinel -Text $finalPrompt -Type "prompt" -Mode "grade"
if ($grade) {
    "[$timestamp] Sentinel: Score=$($grade.score), Action=$($grade.action)" | Add-Content $logFile
    
    if ($grade.action -eq "BLOCK") {
        "[$timestamp] Sentinel: BLOCKING prompt" | Add-Content $logFile
        $notifId = "notif_blocked_$([guid]::NewGuid().ToString('N').Substring(0,8))"
        $null = Send-ToBridge -Message @{
            type = "notification"
            payload = @{
                notificationId = $notifId
                message = "🚫 PROMPT BLOCKED: $($grade.reason). Save your credits and try again with more detail."
                summary = "ShadowRefiner: Blocked"
                notificationType = "error"
                options = @("Dismiss")
            }
        }
        
        # Kill the parent Claude process to stop the request
        Write-Error "ShadowRefiner blocked this prompt: $($grade.reason)"
        $parent = Get-Process -Id (Get-Process -Id $PID).ParentArgs.ParentProcessId -ErrorAction SilentlyContinue
        if ($parent) { Stop-Process -Id $parent.Id -Force }
        exit 1
    }
    elseif ($grade.action -eq "IMPROVE") {
        "[$timestamp] Sentinel: IMPROVING prompt" | Add-Content $logFile
        $improved = Invoke-Sentinel -Text $finalPrompt -Type "prompt" -Mode "improve"
        if ($improved) {
            $finalPrompt = $improved
            # Notify user that prompt was auto-improved
            $null = Send-ToBridge -Message @{
                type = "notification"
                payload = @{
                    message = "✨ ShadowRefiner auto-improved your vague prompt for better results."
                    summary = "ShadowRefiner: Improved"
                    notificationType = "info"
                }
            }
        }
    }
}

# Output the modified prompt back to Claude Code (if supported by hook protocol)
# Note: Currently Claude Code hook might not support modifying the prompt in-place,
# but we've blocked it if it's too bad.

# Cache the prompt context for notification enrichment
$promptPreview = if ($finalPrompt.Length -gt 100) { $finalPrompt.Substring(0, 100) + "..." } else { $finalPrompt }
$contextCache = @{
    timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    sessionId = $sessionId
    lastPromptPreview = $promptPreview
    cwd = $cwd
}
$contextCache | ConvertTo-Json -Compress | Set-Content $contextCacheFile -Force

# Build and output JSON response for the hook system
$hookOutput = @{
    action = if ($grade.action -eq "BLOCK") { "BLOCK" } else { "ALLOW" }
    modifiedPrompt = $finalPrompt
    reason = $grade.reason
}

Write-HookOutput -Output $hookOutput

# Always allow prompt to proceed if not explicitly blocked
exit 0
