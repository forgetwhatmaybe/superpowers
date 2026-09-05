# WorkBuddy-快速部署(superpowers 引导注入)

> 前提:WorkBuddy 桌面版(底层 CodeBuddy Code CLI v1.16.0+,**原生支持 hooks**)。
> 注册处:`~/.workbuddy/settings.json`;技能目录:`~/.workbuddy/skills/`(用户级,所有项目共享)。
> 预计耗时 1 分钟。纯本地运行,无密钥。

## 0. 原理一句话

superpowers = 14 个开发流程技能 + 一条「会话启动注入引导」的 hook。按上游
`docs/porting-to-a-new-harness.md`:**引导注入是唯一硬性要求**——每次会话启动时把
`using-superpowers/SKILL.md` 全文注入上下文,教会模型「行动前先查技能」,其余 13 个技能
才会自动触发。WorkBuddy 有原生 hooks,因此走与 ZCode 相同的 `SessionStart` hook 路径,
不需要像 QwenWork / TraeWork 那样退而求其次用全局规则/AGENTS.md 注入。

| 项 | 值 |
| --- | --- |
| 事件 | `SessionStart`(无 matcher,所有会话来源都触发) |
| 输出信封 | `hookSpecificOutput.additionalContext` |
| 引导脚本 | `~/.workbuddy/hooks/superpowers/session-start-workbuddy.sh` |
| 技能落点 | `~/.workbuddy/skills/`(14 个,拷贝式) |

## 1. 一键部署

在本目录(`client-bundle/workbuddy`)执行:

```
python deploy.py                 # 部署(幂等,可重复跑)
python deploy.py --uninstall     # 卸载(摘 hook + 删这 14 个技能,其它技能不动)
python deploy.py --repo <路径>   # 指定 superpowers 仓库路径(默认本文件上两级)
```

做四件事:

1. 拷 vendored 的 14 个技能 → `~/.workbuddy/skills/`(**其它已有技能一个不动**);
2. 拷引导脚本 + `using-superpowers` 副本 → `~/.workbuddy/hooks/superpowers/`;
3. 备份 `settings.json`,再幂等合并 `SessionStart`(name=`superpowers-bootstrap`,
   timeout 单位=**秒**)—— 按 name 去重,重复跑不叠加,**绝不动** crap-gate / tcdb-* 等既有键;
4. 不经宿主直接跑一次引导脚本做链路自检。

升级:`git pull` 后重跑 `deploy.py` 即刷新全部技能。

## 2. 验证

- **链路自检(不需重启,部署已自动跑)**:脚本应输出含 `hookSpecificOutput.additionalContext`
  的 JSON,上下文 ≥ 3000 字符(实测 3642)。若只有几百字符且正文是
  `No such file or directory`,说明 `PLUGIN_ROOT` 算错——见第 4 节已知坑。
- **技能就位(立即可查)**:`~/.workbuddy/skills/` 下应出现 14 个目录
  (brainstorming / dispatching-parallel-agents / executing-plans /
  finishing-a-development-branch / receiving-code-review / requesting-code-review /
  subagent-driven-development / systematic-debugging / test-driven-development /
  using-git-worktrees / using-superpowers / verification-before-completion /
  writing-plans / writing-skills)。
- **触发词验证(部署后延迟验证)**:hooks 在**会话启动时**快照加载,必须重启 WorkBuddy
  新开会话。新会话里说「帮我做个功能」,确认 agent 先调用 `brainstorming` 等技能再动手。
  ⚠️ 自动化会话里**不要**让脚本自动重启 WorkBuddy——会杀掉正在执行部署的会话本身。

## 3. 已知坑(本机实测 2026-09-05)

- **`PLUGIN_ROOT` 目录层级与 ZCode 不同**:ZCode 版脚本放在 `<仓库>/hooks/` 下,
  `PLUGIN_ROOT` 取上级(仓库根),`skills/` 在根下;WorkBuddy 版脚本与 `skills/` 同在
  `~/.workbuddy/hooks/superpowers/` 下,**`PLUGIN_ROOT` 必须直接取脚本所在目录本身**。
  照抄 ZCode 版的 `"${SCRIPT_DIR}/.."` 会跳到 `~/.workbuddy/hooks/` 去找 `skills/`,
  `cat` 失败静默降级成一句错误文案(不报错、退出码仍 0,极难发现)。
- **Windows 上 hooks 强制走 Git Bash**,且只支持 `command` 字符串(不支持 exec 的
  `command`+`args` 数组)。deploy.py 固定生成 `bash "<脚本正斜杠路径>"`,
  显式调 bash 而不依赖 `.sh` 的 exec bit 在 Windows 上是否保留。
- **hooks 快照机制**:直接编辑 settings.json 不会立即生效,需在 `/hooks` 面板审核或重启客户端。
- **matcher 一律省略**:上游 `hooks.json` 用 `startup|clear|compact` 排除 resume,
  但 WorkBuddy 是否给 SessionStart 传来源值未验证,带 matcher 有永不触发的风险。

## 4. 回滚 / 临时停用

- 回滚:从任意 `settings.json.bak-superpowers-*` 覆盖回去,或 `python deploy.py --uninstall`。
- 临时停用:注释掉 settings.json 里那条 SessionStart 即可,技能文件留着无害
  (只是不再自动引导,手动调 Skill 工具仍可用)。

## 5. 与其他客户端差异速查

| | ZCode | QwenWork | TraeWork | **WorkBuddy** |
|---|---|---|---|---|
| 注入机制 | `SessionStart` hook | 全局 `AGENTS.md` 每会话加载 | 全局 user rule 每轮 | **`SessionStart` hook** |
| 注册处 | `~/.zcode/cli/config.json` | `~/.qwenworkcn/awareness/main/AGENTS.md` | 全局规则 | `~/.workbuddy/settings.json` |
| hook 形式 | process(argv 数组) | — | — | **command 字符串(Git Bash)** |
| 技能落点 | `~/.agents/skills/`(软链仓库) | `~/.qwenworkcn/skills/`(拷贝) | — | `~/.workbuddy/skills/`(拷贝) |
| 是否有 hooks | ✅ | ❌ | ❌ | ✅ |
| 部署脚本 | 手工合 config.json | deploy.ps1 | deploy.ps1 | **deploy.py**(幂等+自检+卸载) |

## 6. 实测记录(2026-09-05,Windows · WorkBuddy)

- 14 个技能拷贝就位,原有 8 个用户技能零改动 ✅
- 引导脚本链路自检:exit 0,上下文 3642 字符,信封校验 OK ✅
- settings.json 幂等合并:`PostToolUse/crap-gate` 与 `SessionStart/superpowers-bootstrap`
  共存互不干扰;claw / sandbox / enabledPlugins / enableModelOptimization 四个原有键零改动 ✅
- 延迟验证项(需用户重启 WorkBuddy 后新会话确认):触发词验证
