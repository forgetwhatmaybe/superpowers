# ZCode 接入 superpowers 快速部署(其他电脑照此操作)

> 结论先行:**可以加 hook**。ZCode 支持 `SessionStart` 事件(hook 触发时脚本的
> stdout 会以 `additionalContext` 注入会话上下文),正是 superpowers 需要的
> 引导注入通道。本机(2026-08-29)已按本文配置完成:14 个技能接入 +
> SessionStart hook 注册。
>
> superpowers = obra/superpowers(本文对应 v6.3.0,MIT)。它唯一的硬性接入
> 要求(官方 `docs/porting-to-a-new-harness.md`)是:**会话启动时自动注入一段
> 引导文本**(教会模型"行动前先查技能"),ZCode 的 SessionStart hook 满足。
> 没有这一步,技能文件只是躺在磁盘上永远不会被调用——官方原话
> "bootstrap 就是整个集成"。

## 0. 前提

- Git for Windows(提供 bash.exe,标准路径 `C:\Program Files\Git\bin\bash.exe`);
- 本地有一份 superpowers 仓库 clone(v6.3.0 与 GitHub 最新一致;没有就
  `git clone --depth 1 https://github.com/obra/superpowers`)。
  **下文用 `<superpowers仓库>` 代指这份 clone 的本地路径**,操作时换成你的
  实际位置(示例:clone 到 `D:\repos\superpowers` 就把它读作
  `D:\repos\superpowers`);
- ZCode 能正常启动(技能与 hook 都在用户级配置,所有工作区生效)。

## 1. 技能接入(1 分钟,本机已完成,可跳过)

ZCode 扫描 `~/.zcode/skills/`、`~/.agents/skills/` 等目录自动发现技能;装进
`~/.agents/skills/` 还能同时给 Claude Code 等其他客户端共享。两种方式:

**A. 软链接(本机现状,推荐:仓库 git pull 即整体升级)**

管理员 cmd / 开发者模式下,对 14 个技能目录逐个:

```bat
mklink /D "%USERPROFILE%\.agents\skills\brainstorming" "<superpowers仓库>\skills\brainstorming"
```

(14 个目录名见本 bundle 顶层 `skills/`;git bash 里 `ln -s` 默认是复制,
不是软链,别用它做这一步。)

**B. 直接拷贝(零依赖)**

把本 bundle 顶层的 `skills/` 下 14 个目录整个拷到 `~/.agents/skills/`。

完成后重启 ZCode,新会话的技能列表里应出现 brainstorming / systematic-debugging /
test-driven-development / using-superpowers 等 14 个技能。

## 2. hook 注册(3 分钟)

**2.1 拷适配脚本进仓库**(和上游脚本放一起,git pull 后若上游 session-start
有大改,手动 diff 同步一次):

```
client-bundle/zcode/hooks/session-start-zcode.sh  →  <superpowers仓库>\hooks\session-start-zcode.sh
```

适配版与上游 `hooks/session-start` 的差异只有两处(见脚本头注释):输出信封
固定为 `hookSpecificOutput.additionalContext`(ZCode 上已有的记忆注入钩子实测
可用的格式;上游原版直调输出顶层 `additionalContext`,ZCode 未验证)、技能名去掉
`superpowers:` 前缀。上游文件一行未改。

**2.2 合并 hook 注册**:把 `config-json-hooks-片段.json` 里的
`"SessionStart": [...]` 整块合并进 `~/.zcode/cli/config.json` 的
`hooks` → `events`:

- config.json 不存在 → 整个片段存成该文件;
- 已存在(比如已注册过其他事件的 hook)→
  只加 SessionStart 这一个事件键,原有内容一个字别动;
  稳妥起见先备份一份(如 `config.json.bak-superpowers`),
  改完 `python -m json.tool < 文件` 验证 JSON 合法。

改完**重启 ZCode**(hook 注册在会话启动时读取)。

## 3. 验证(3 分钟)

先手动验证脚本这条链路(不依赖宿主):

```bash
echo '{}' | bash "<superpowers仓库>/hooks/session-start-zcode.sh" | python -m json.tool
```

- 输出合法 JSON,`hookSpecificOutput.additionalContext` 里含
  `<EXTREMELY_IMPORTANT>You have superpowers.` 和 using-superpowers 全文 = 通了;
  (脚本对 SKILL.md 缺失也是 fail-open:报错文本照样注入,不中断会话。)

然后重启 ZCode 开新会话做行为验收(官方验收标准):直接说
"我们来做一个 react todo list",模型应当**先触发 brainstorming 技能**,
而不是上来就写代码——说明引导注入生效、技能自动触发链路通了。

没生效时排查:确认 `hooks.enabled: true`;事件名精确为 `SessionStart`;
ZCode 日志里有该 hook 的执行记录(含 outcome / 耗时 / 错误流预览,可区分
没触发、超时还是输出校验失败);JSON 输出里不能有多余键(严格校验,多一个
键整个输出被丢弃);Windows 路径一律双反斜杠。

## 4. 与 Claude Code 官方插件的差异速查

| 项 | ZCode(手动接入) | Claude Code(官方插件市场) |
| --- | --- | --- |
| 安装 | 技能软链/拷贝 + config.json 注册 hook,全程手动 | marketplace 一键安装 |
| 技能位置 | `~/.agents/skills/`(多客户端共享)或 `~/.zcode/skills/` | 插件目录自动加载 |
| hook 注册 | `~/.zcode/cli/config.json` 顶层 `hooks`,**必须 `enabled: true`** | 插件自带 `hooks/hooks.json`,hook runner 自动启用 |
| hook 类型 | `process`(argv 直调 bash.exe),超时 `timeoutMs` 毫秒 | `command` + `shell: bash`,超时秒 |
| SessionStart 来源值 | startup / resume / clear / compact(matcher 是大小写敏感正则;**默认省略 = 全触发**) | matcher `startup\|clear\|compact` |
| 注入信封 | `hookSpecificOutput.additionalContext`(已实测) | 同 |
| 脚本 | `session-start-zcode.sh`(适配版,信封固定) | `session-start` + `run-hook.cmd`(按平台环境变量自动选信封) |

## 5. 进阶:插件方式(未实测,备选)

superpowers 仓库自带 `.claude-plugin/plugin.json` + `hooks/hooks.json`,而
ZCode 识别 `.claude-plugin/` 兼容清单、会读取插件的 `hooks/hooks.json`,且
插件携带 hook 时 hook runner 自动启用。理论上可在
**设置 → 插件管理 → 发现 → +** 添加 GitHub 仓库 `obra/superpowers` 一键安装。

未实测的原因:它的 hook 命令是
`"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start`(command 型,经
shell 执行,Windows 上靠 polyglot 包装器再找 bash),这条链路在 ZCode 的
Windows shell 环境下行为不确定。**若插件方式装完技能可用但引导注入没生效,
退回第 2 节的手动 process 注册即可**,两者不冲突(重复注入时删掉一边)。

## 6. 临时停用

- 停引导注入:把 config.json 里 SessionStart 的 hook 条目删掉(或整段注释不
  支持,JSON 无注释——建议移到备份文件),重启 ZCode;
- 停技能:把 `~/.agents/skills/` 下对应软链接/目录改名加后缀即可,ZCode 只
  扫描该目录。
