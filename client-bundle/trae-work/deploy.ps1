param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$TraeHome = "$env:USERPROFILE\.trae-cn"
)
$ErrorActionPreference = "Stop"

$srcSkills = Join-Path $RepoRoot "skills"
$dstSkills = Join-Path $TraeHome "skills"
$dstRules  = Join-Path $TraeHome "user_rules"
$ruleSrc   = Join-Path $PSScriptRoot "user-rule-superpowers.md"

if (-not (Test-Path $srcSkills)) { throw "skills source not found: $srcSkills" }
$skillDirs = Get-ChildItem $srcSkills -Directory | Where-Object {
    (Get-ChildItem $_.FullName -Recurse -File).Count -gt 0
}
if ($skillDirs.Count -eq 0) { throw "no non-empty skill dirs under $srcSkills (run: git -C $RepoRoot restore skills/)" }

New-Item -ItemType Directory -Force -Path $dstSkills, $dstRules | Out-Null
foreach ($d in $skillDirs) {
    Copy-Item $d.FullName -Destination $dstSkills -Recurse -Force
}
Copy-Item $ruleSrc -Destination (Join-Path $dstRules "rule-superpowers.md") -Force

Write-Host "deployed $($skillDirs.Count) skills -> $dstSkills"
Write-Host "deployed rule -> $dstRules\rule-superpowers.md"
Write-Host "restart TraeWork to load the new global rule"
