<#
  QwenWork (千问办公) 接入 superpowers 的一键部署脚本
  等效 TraeWork 的 deploy.ps1：千问办公无 hooks 系统，用
    1) 拷贝 14 个技能 -> ~/.qwenworkcn/skills/
    2) 把引导注入块写进 ~/.qwenworkcn/awareness/main/AGENTS.md 的 Session Startup 段
  AGENTS.md 每次会话自动加载 = superpowers 唯一硬性要求的"引导注入"通道。

  用法（普通 powershell 即可，无需管理员）：
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy.ps1
  仓库 git pull 升级后重跑本脚本即可让千问办公同步到最新技能。
#>
param(
    [string]$RepoRoot  = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$QwenHome  = "$env:USERPROFILE\.qwenworkcn"
)
$ErrorActionPreference = "Stop"

$srcSkills  = Join-Path $RepoRoot "skills"
$dstSkills  = Join-Path $QwenHome "skills"
$agentsMd   = Join-Path $QwenHome "awareness\main\AGENTS.md"
$snippetSrc = Join-Path $PSScriptRoot "session-startup-superpowers.md"

if (-not (Test-Path $srcSkills))  { throw "skills source not found: $srcSkills" }
if (-not (Test-Path $snippetSrc)) { throw "snippet not found: $snippetSrc" }

# --- 1. copy the 14 skills ---
$skillDirs = Get-ChildItem $srcSkills -Directory | Where-Object {
    (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue).Count -gt 0 -and
    (Test-Path (Join-Path $_.FullName "SKILL.md"))
}
if ($skillDirs.Count -eq 0) { throw "no skills with SKILL.md under $srcSkills (run: git -C $RepoRoot restore skills/)" }

New-Item -ItemType Directory -Force -Path $dstSkills | Out-Null
foreach ($d in $skillDirs) {
    Copy-Item $d.FullName -Destination $dstSkills -Recurse -Force
}
Write-Host "deployed $($skillDirs.Count) skills -> $dstSkills"

# --- 2. inject the Session Startup block into AGENTS.md (idempotent) ---
$snippet = Get-Content $snippetSrc -Raw -Encoding UTF8
New-Item -ItemType Directory -Force -Path (Split-Path $agentsMd -Parent) | Out-Null
if (-not (Test-Path $agentsMd)) { "# AGENTS.md`r`n" | Set-Content $agentsMd -Encoding UTF8 }

$begin  = "<!-- superpowers-session-startup:begin -->"
$end    = "<!-- superpowers-session-startup:end -->"
$agents = Get-Content $agentsMd -Raw -Encoding UTF8

if ($agents -match [regex]::Escape($begin)) {
    # replace the whole begin/end block with the latest snippet (snippet carries its own markers)
    $pre    = $agents.Substring(0, $agents.IndexOf($begin))
    $endIdx = $agents.IndexOf($end) + $end.Length
    $post   = $agents.Substring($endIdx)
    $new    = $pre + $snippet.TrimEnd() + $post
    [System.IO.File]::WriteAllText($agentsMd, $new, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "AGENTS.md Session Startup block updated -> $agentsMd"
} else {
    $block = "`r`n" + $snippet.TrimEnd() + "`r`n"
    Add-Content $agentsMd -Value $block -Encoding UTF8
    Write-Host "AGENTS.md Session Startup block appended -> $agentsMd"
}

Write-Host ""
Write-Host "Done. Restart QwenWork and open a new session to activate the bootstrap."
Write-Host "Verify: in a new session say 'build me a react todo list' -> it should invoke brainstorming first, not write code."
