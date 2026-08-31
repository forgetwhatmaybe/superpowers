# superpowers 客户端接入 bundle

把 [obra/superpowers](https://github.com/obra/superpowers)(v6.3.0,MIT,见
`LICENSE`)接入各 AI 客户端的配置包。superpowers = 14 个开发流程技能 +
一条"会话启动注入引导"的 hook,核心机制见官方
`docs/porting-to-a-new-harness.md`:**引导注入是唯一硬性要求**——教会模型
"行动前先查技能",其余技能才会自动触发。

## 目录

```
skills/                      14 个技能的 vendored 副本(拷贝安装的来源)
client-bundle/
├── qwen-work/               千问办公(QwenWork):无 hooks 系统 → 全局 AGENTS.md 注入 + deploy.ps1
│   ├── QwenWork-快速部署.md 主文档:原理、步骤、验证、全项目生效、差异速查
│   ├── session-startup-superpowers.md  注入进 awareness/main/AGENTS.md 的 Session Startup 段
│   └── deploy.ps1            拷贝 14 技能到 ~/.qwenworkcn/skills + 幂等写入 AGENTS.md
├── trae-work/               TraeWork:无 hooks 系统 → 全局规则注入(每轮) + deploy.ps1
└── zcode/                   ZCode:SessionStart hook 注入(2026-08-29 新增)
    ├── ZCode-快速部署.md    主文档:原理、步骤、验证、差异速查
    ├── config-json-hooks-片段.json   合并进 ~/.zcode/cli/config.json 的 hook 注册
    └── hooks/session-start-zcode.sh  适配版引导脚本(信封固定为 hookSpecificOutput 格式)
```

## 各客户端接入方式一览

| 客户端 | 引导注入机制 | 状态 |
| --- | --- | --- |
| Claude Code | 官方插件市场一键安装,无需本 bundle | 上游原生支持 |
| ZCode | `SessionStart` hook(`~/.zcode/cli/config.json`)+ `~/.agents/skills/` 技能 | ✅ 已配置并验证 |
| TraeWork | 全局 user rule(每轮注入,等效替代 SessionStart) | ✅ 已配置 |
| 千问办公(QwenWork) | 无 hooks → 全局 `~/.qwenworkcn/awareness/main/AGENTS.md`(每会话自动加载,等效 SessionStart)+ `~/.qwenworkcn/skills/` 技能 | ✅ 已配置并验证 |

技能共享:ZCode 用软链接指向本地 superpowers 仓库 clone(`<superpowers仓库>`,
即你自己 clone 下来的本地路径,git pull 即升级);TraeWork、千问办公(QwenWork)用
拷贝式安装本仓库 vendored 的 `skills/`(千问办公技能目录 `~/.qwenworkcn/skills/` 为
用户级,所有项目共享;`git pull` 后重跑对应 `deploy.ps1` 即刷新)。上游文件
(session-start、SKILL.md)一律不改,适配只通过新增文件完成。
