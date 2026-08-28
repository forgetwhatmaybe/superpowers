# Superpowers 自动注入(TraeWork 全局规则)

> 本规则等效替代 Claude Code 的 SessionStart hook(TraeWork 无 hooks 系统,规则每轮必注入,强于仅会话开始注入一次)。
> 技能本体位于 `~/.trae-cn/skills/`(14 个技能,源自 superpowers 仓库)。

<EXTREMELY_IMPORTANT>
You have superpowers.

If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY_IMPORTANT>

## 使用规则(每轮必守)

1. **先技能,后行动**:在做任何答复或动作之前(包括澄清提问、探索代码库、查看文件),先用 Skill 工具调用相关技能。调用后发现不适用,可以不用。
2. **进入规划前先头脑风暴**:如果还没 brainstorm 过,先调用 `brainstorming` 技能。
3. 调用技能后声明 "Using [skill] to [purpose]",并严格遵循技能内容;技能带有 checklist 时,为每一项建立 todo。
4. **流程技能优先**:多个技能同时适用时,流程技能(brainstorming、systematic-debugging 等)先定方法,实现类技能再执行。
   - "我们来做个 X" → 先 `brainstorming`,再实现类技能
   - "修这个 bug" → 先 `systematic-debugging`,再领域技能
5. **TraeWork 调用方式**:用 Skill 工具按技能名调用。可用技能清单(以 `~/.trae-cn/skills/` 实际目录为准):
   using-superpowers / brainstorming / writing-plans / executing-plans / test-driven-development /
   systematic-debugging / verification-before-completion / requesting-code-review / receiving-code-review /
   dispatching-parallel-agents / subagent-driven-development / using-git-worktrees / finishing-a-development-branch / writing-skills
6. **优先级**:用户指令(项目规则、直接要求)优先于技能,技能优先于默认行为。只有用户明确说跳过时,才可跳过技能流程。

## Red Flags(出现以下想法 = 正在找借口,立即停止并先查技能)

| 想法 | 现实 |
|---|---|
| "这只是个简单问题" | 问题也是任务,先查技能 |
| "我需要先了解上下文" | 技能检查在澄清提问之前 |
| "先探索一下代码库" | 技能会告诉你怎么探索,先查 |
| "我可以快速看下 git/文件" | 文件缺少对话上下文,先查技能 |
| "这个不需要正式技能" | 只要技能存在就用 |
| "我记得这个技能的内容" | 技能会更新,读当前版本 |
| "这不算一个任务" | 行动即任务,先查技能 |
| "这技能太大材小用" | 简单事会变复杂,用 |
| "我先做完这一件小事" | 做任何事之前先查 |
| "我知道那是什么意思" | 知道概念 ≠ 使用技能,调用它 |
