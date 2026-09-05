#!/usr/bin/env bash
# SessionStart hook for superpowers (WorkBuddy adaptation)
#
# 基于上游 obra/superpowers v6.3.0 的 hooks/session-start,适配自 ZCode 版,三处改动:
#  1. 输出信封固定为 hookSpecificOutput.additionalContext(CodeBuddy Code 文档明确支持
#     SessionStart 的该字段;WorkBuddy 底层即 CodeBuddy Code CLI v1.16.0+)。
#  2. 引导文案中的技能名 'superpowers:using-superpowers' 改为 'using-superpowers'
#     (WorkBuddy 从 ~/.workbuddy/skills/ 扫描加载,名字不带插件前缀)。
#  3. 目标注释改为 WorkBuddy;脚本本体逻辑与上游一致。
#
# 本脚本必须放在 <PLUGIN_ROOT>/ 目录下运行,且同级的 skills/using-superpowers/SKILL.md
# 存在:它会读该文件作为注入内容(部署时由 deploy.py 一并拷贝)。
# 上游文件(session-start / SKILL.md)一行未改。

set -euo pipefail

# 注意与 ZCode 版的目录差异:
#   ZCode      : 脚本在 <仓库>/hooks/ 下,PLUGIN_ROOT 取上级(= 仓库根),skills/ 在根下;
#   WorkBuddy  : 脚本与 skills/ 同在 ~/.workbuddy/hooks/superpowers/ 下,
#                故 PLUGIN_ROOT 直接取脚本所在目录本身,不再向上跳一级。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="${SCRIPT_DIR}"

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

# WorkBuddy 走 CodeBuddy Code 的 hook 输出契约:SessionStart 的附加上下文一律放
# hookSpecificOutput.additionalContext。stdout 只输出这一个 JSON,不夹带其它字段。
printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$session_context"

exit 0
