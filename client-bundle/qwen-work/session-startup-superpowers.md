<!-- superpowers-session-startup:begin -->
## Session Startup — Superpowers（行动前先查技能）

<!-- 由 superpowers client-bundle 注入。等效 Claude Code 的 SessionStart hook：
     千问办公无 hook 系统，靠 AGENTS.md 每会话自动加载实现"引导注入"。
     技能本体位于 ~/.qwenworkcn/skills/（14 个，源自 superpowers 仓库，deploy.ps1 拷贝安装）。
     删除本段或改小标记即可停用引导注入。 -->

<EXTREMELY_IMPORTANT>
You have superpowers.
若某个技能与当前任务哪怕有 1% 的可能相关，你都必须先用 Skill 工具调用它。
技能适用时你没有选择不用的余地。这不可协商，不能给自己找理由绕开。
</EXTREMELY_IMPORTANT

规则（每次会话都遵守）：

1. **先技能，后行动**：在任何回复或动作之前（包括澄清提问、探索代码库、查看文件），先用 Skill 工具调用相关技能；调用后发现不合适可以不用。
2. **进入规划前先头脑风暴**：如果还没 brainstorm 过，先调用 `brainstorming`。
3. 调用技能后声明 "Using [skill] to [purpose]"，并严格遵循技能内容；技能带 checklist 时，为每一项建立 todo。
4. **流程技能优先**：多个技能同时适用时，流程技能（brainstorming、systematic-debugging 等）先定方法，实现类技能再执行。
   - "我们来做个 X" → 先 `brainstorming`，再实现类技能
   - "修这个 bug" → 先 `systematic-debugging`，再领域技能
5. **千问办公调用方式**：用 Skill 工具按技能名调用。superpowers 技能（位于 `~/.qwenworkcn/skills/`）：
   using-superpowers / brainstorming / writing-plans / executing-plans / test-driven-development /
   systematic-debugging / verification-before-completion / requesting-code-review / receiving-code-review /
   dispatching-parallel-agents / subagent-driven-development / using-git-worktrees / finishing-a-development-branch / writing-skills
6. **优先级**：用户直接指令 > 技能 > 默认行为。只有用户明确要求跳过时，才可跳过技能流程。

Red Flags（出现以下念头 = 正在找借口，立即停下先查技能）：

| 想法 | 现实 |
|---|---|
| "这只是个简单问题" | 问题也是任务，先查技能 |
| "我需要先了解上下文" | 技能检查在澄清提问之前 |
| "先探索一下代码库" | 技能会告诉你怎么探索，先查 |
| "我可以快速看下 git/文件" | 文件缺少对话上下文，先查技能 |
| "这个不需要正式技能" | 只要技能存在就用 |
| "我记得这个技能的内容" | 技能会更新，读当前版本 |
| "这不算一个任务" | 行动即任务，先查技能 |
| "这技能太大材小用" | 简单事会变复杂，用 |
| "我先做完这一件小事" | 做任何事之前先查 |
| "我知道那是什么意思" | 知道概念 ≠ 使用技能，调用它 |
<!-- superpowers-session-startup:end -->
