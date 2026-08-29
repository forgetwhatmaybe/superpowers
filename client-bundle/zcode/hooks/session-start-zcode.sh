#!/usr/bin/env bash
# SessionStart hook for superpowers (ZCode adaptation)
#
# 基于上游 obra/superpowers v6.3.0 的 hooks/session-start,仅两处适配:
#  1. 输出信封固定为 hookSpecificOutput.additionalContext(Claude Code 格式)。
#     上游原版在无平台环境变量时输出顶层 additionalContext,ZCode 是否接受
#     顶层字段未验证;hookSpecificOutput.additionalContext 已由 ZCode 上已有的
#     记忆注入钩子实测可用(2026-08-24/2026-08-29,UserPromptSubmit 与
#     SessionStart 走同一注入通道)。
#  2. 引导文案中的技能名 'superpowers:using-superpowers' 改为 'using-superpowers'
#     (ZCode 从技能目录扫描加载,名字不带插件前缀)。
#
# 本脚本必须放在 superpowers 仓库的 hooks/ 目录下运行:它会读
# ${仓库根}/skills/using-superpowers/SKILL.md 作为注入内容。
# 上游文件(session-start / SKILL.md)一行未改。

set -euo pipefail

# Determine plugin root directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Read using-superpowers content
using_superpowers_content=$(cat "${PLUGIN_ROOT}/skills/using-superpowers/SKILL.md" 2>&1 || echo "Error reading using-superpowers skill")

# Escape string for JSON embedding (same as upstream: per-class substitution,
# orders of magnitude faster than a character loop).
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

using_superpowers_escaped=$(escape_for_json "$using_superpowers_content")
session_context="<EXTREMELY_IMPORTANT>\nYou have superpowers.\n\n**Below is the full content of your 'using-superpowers' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**\n\n${using_superpowers_escaped}\n</EXTREMELY_IMPORTANT>"

# ZCode 严格校验 hook 的 stdout JSON:只输出它认识的键,多余的键会让整个
# 输出被丢弃(运行标记 failed,会话继续但无注入)。因此不输出其他字段。
printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$session_context"

exit 0
