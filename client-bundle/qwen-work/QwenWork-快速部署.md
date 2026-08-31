# 千问办公(QwenWork)接入 superpowers 快速部署(其他电脑照此操作)

> 结论先行:**可以接入,且一次配置对所有项目生效**。千问办公(千问办公/QwenWork)**没有 hooks 系统**
> (不像 ZCode / Claude Code 有 `SessionStart` hook),但 superpowers 唯一的硬性接入要求
> ——官方 `docs/porting-to-a-new-harness.md` 说的**"会话启动时自动注入一段引导"**(教会模型
> "行动前先查技能")——可以等效满足:把引导写进 `~/.qwenworkcn/awareness/main/AGENTS.md`。
> 这是千问办公 awareness 模式下**每次会话都会自动加载**的全局操作手册,注入一次即对所有项目、
> 所有新会话生效(覆盖面等效于"每轮注入",强于仅在会话开始注入一次的 hook)。
> 技能本体则拷进用户级 `~/.qwenworkcn/skills/`——同样是全局作用域,不按工作区隔离。
>
> superpowers = obra/superpowers(本文对应 v6.3.0,MIT)。

## 0. 前提

- Windows(或 macOS)上装好千问办公,能正常启动;
- 有 PowerShell(Windows 自带的 `powershell.exe` 即可,**普通权限、无需管理员**);
- 本地有一份 superpowers 仓库 clone(v6.3.0 与 GitHub 最新一致;没有就
  `git clone --depth 1 https://github.com/forgetwhatmaybe/superpowers`)。
  **下文用 `<superpowers仓库>` 代指这份 clone 的本地路径**,示例:clone 到
  `D:\repos\superpowers` 就把它读作 `D:\repos\superpowers`;
- 配置全部落在用户级目录 `~/.qwenworkcn/`,不区分工作区 → **所有项目自动启用**。

## 1. 一键部署(推荐,1 分钟)

普通 PowerShell 执行:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File "<superpowers仓库>\client-bundle\qwen-work\deploy.ps1"
```

脚本做两件事(幂等,可反复重跑):

1. 把仓库顶层 `skills/` 下 14 个技能目录**拷贝安装**进 `~/.qwenworkcn/skills/`
   (千问办公官方技能布局只认纯目录,**不支持软链接**,故用拷贝而非 ZCode 那套软链方案);
2. 把本 bundle 的 `session-startup-superpowers.md` 作为一段带
   `<!-- superpowers-session-startup:begin --> / :end -->` 标记的 "Session Startup" 内容,
   写入 `~/.qwenworkcn/awareness/main/AGENTS.md`:文件里没有该段则追加,已有则**整段替换**
   (不会重复堆叠)。

完成后**重启千问办公并开一个新会话**让引导注入生效。

## 2. 手动部署(零脚本,等价)

**A. 技能**:把 `<superpowers仓库>\skills\` 下 14 个目录整个拷到 `~/.qwenworkcn/skills/`。

**B. 引导注入**:打开 `~/.qwenworkcn/awareness/main/AGENTS.md`(不存在就新建),把本 bundle
`session-startup-superpowers.md` 的内容粘进去。强烈建议保留首尾那对
`superpowers-session-startup:begin / :end` 标记——方便以后一键整段替换或删除。

## 3. 验证(3 分钟)

**技能发现是实时的**:千问办公重扫 `~/.qwenworkcn/skills/` 后,可用技能列表(设置 → 技能,
或会话内的技能清单)应出现 brainstorming / systematic-debugging / test-driven-development /
writing-plans / using-superpowers 等 14 个,状态均为"已启用/未禁用"。

**引导注入发生在会话启动时**,所以行为验收要**重启千问办公、开一个新会话**做(官方对任何
harness 的验收标准):直接说"我们来做一个 react todo list",模型应当**先触发 brainstorming
技能**、而不是上来就写代码——说明"引导注入 → 技能自动触发"链路通了。

没生效时排查:① 确认 `~/.qwenworkcn/awareness/main/AGENTS.md` 里那段确实在 begin/end 标记之间
且未被别的内容截断;② 确认该会话跑在 awareness 模式(千问办公常态);③ 技能是否被误标 disabled
(设置 → 技能里查 `disabled`);④ Windows PowerShell 5.1 读取含中文的 `.ps1` 需 **UTF-8 with BOM**
(本仓库的 `deploy.ps1` 已按 BOM 保存;若你自行改动后出现中文乱码/命令被吞,多半是丢了 BOM)。

## 4. 全项目生效说明(为什么不用逐项目配)

- **技能层**:`~/.qwenworkcn/skills/` 是用户级目录,千问办公不按工作区隔离技能,所有项目共享同一份技能清单;
- **引导层**:`~/.qwenworkcn/awareness/` 下只有 `main` 这一个 agent,其 `AGENTS.md` 是跨所有
  会话 / 工作区自动加载的唯一全局手册;`~/.qwenworkcn/projects/` 各目录只存会话记录,不含
  覆盖用的 per-project 上下文文件;
- **唯一例外**:若你在某个工作区目录里自己放了同名 `AGENTS.md` / `CLAUDE.md`,按千问办公的优先级
  "用户直接指令 > 技能 > 默认行为",那份会**局部覆盖**全局手册。默认不存在此文件,故全局注入不被破坏。

## 5. 与其他客户端的差异速查

| 项 | 千问办公 | ZCode | TraeWork | Claude Code |
| --- | --- | --- | --- | --- |
| 引导注入通道 | 全局 `awareness/main/AGENTS.md`(每会话自动加载) | `SessionStart` hook(`config.json`) | 全局 user rule(每轮注入) | 官方插件自带 hook |
| hooks 系统 | 无 → 用 AGENTS.md 等效 | 有 | 无 → user rule 等效 | 有(插件自带) |
| 技能位置 | `~/.qwenworkcn/skills/`(纯目录,拷贝) | `~/.agents/skills/`(软链/拷贝) | `~/.trae-cn/skills/`(拷贝) | 插件目录自动加载 |
| 作用域 | 用户级 = 所有项目 | 用户级 = 所有工作区 | 全局 | 全局 |
| 升级方式 | `git pull` 后重跑 `deploy.ps1` | 软链:pull 即升级 | 重跑 `deploy.ps1` | 插件更新 |
| 是否需管理员 | 否 | 软链需开发者模式/管理员 | 否 | 否 |
| 注入信封 | 无(Markdown 直接进上下文) | `hookSpecificOutput.additionalContext` | 无(规则直接进上下文) | `additionalContext` |
| 上游文件改动 | 无(仅新增本 bundle 文件) | 无 | 无 | — |

## 6. 临时停用

- **停引导注入**:删掉 `~/.qwenworkcn/awareness/main/AGENTS.md` 里 `superpowers-session-startup:begin`
  与 `:end` 之间那一段(或整段移到备份),保存即生效,无需重装千问办公;
- **停技能**:把 `~/.qwenworkcn/skills/` 下对应技能目录改名 / 移出即可,千问办公只扫描该目录;
- **恢复**:重跑 `deploy.ps1`。

## 7. 与仓库 vendored skills 的关系

本 bundle 复用仓库顶层 `skills/`(与 TraeWork 共用同一份 vendored 副本,源自 obra/superpowers
v6.3.0,MIT)。上游文件(session-start、SKILL.md)一行未改,千问办公适配仅通过本
`client-bundle/qwen-work/` 下的新增文件完成。
