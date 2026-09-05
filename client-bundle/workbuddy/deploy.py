# -*- coding: utf-8 -*-
"""superpowers 技能集 · WorkBuddy 一键部署/卸载(跨机器通用,不绑定盘符)。

用法:
    python deploy.py                  # 部署(幂等,可重复跑)
    python deploy.py --uninstall      # 卸载(摘 hook + 删 14 技能,其它技能不动)
    python deploy.py --repo <路径>    # 指定 superpowers 仓库路径(默认本文件的上两级)

做四件事:
  1. 拷贝 vendored 的 14 个技能到 ~/.workbuddy/skills/(用户级,所有项目共享);
  2. 拷贝会话启动引导脚本 + using-superpowers 技能到 ~/.workbuddy/hooks/superpowers/;
  3. 备份 settings.json,再幂等合并 SessionStart hook(name=superpowers-bootstrap)
     进 ~/.workbuddy/settings.json 顶层 hooks 块 —— 按 name 去重,重复跑不叠加,
     绝不动 crap-gate / tcdb-* 等既有键与其它顶层键;
  4. 不经宿主直接跑一次引导脚本做链路自检(应输出含 additionalContext 的 JSON)。

引导注入是 superpowers 唯一的硬性要求:教会模型"行动前先查技能",其余 13 个技能
才会自动触发。上游技能文件一律不改,适配只通过新增文件完成。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

NAME = "superpowers-bootstrap"
TIMEOUT = 15
SKILL_NAMES = [
    "brainstorming", "dispatching-parallel-agents", "executing-plans",
    "finishing-a-development-branch", "receiving-code-review",
    "requesting-code-review", "subagent-driven-development",
    "systematic-debugging", "test-driven-development", "using-git-worktrees",
    "using-superpowers", "verification-before-completion", "writing-plans",
    "writing-skills",
]

HERE = os.path.dirname(os.path.abspath(__file__))


def repo_root(args_repo):
    if args_repo:
        return os.path.abspath(args_repo)
    return os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))


def install(repo, home):
    skills_src = os.path.join(repo, "skills")
    skills_dst = os.path.join(home, ".workbuddy", "skills")
    hook_dir = os.path.join(home, ".workbuddy", "hooks", "superpowers")

    # 1. 14 个技能 -> 用户级技能目录(其它已有技能一个不动)
    os.makedirs(skills_dst, exist_ok=True)
    n = 0
    for name in SKILL_NAMES:
        src = os.path.join(skills_src, name)
        dst = os.path.join(skills_dst, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            n += 1
    print("[1/4] %d 个技能 -> %s" % (n, skills_dst))

    # 2. 引导脚本 + using-superpowers 副本(供脚本按 PLUGIN_ROOT/skills/... 读取)
    os.makedirs(hook_dir, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "hooks", "session-start-workbuddy.sh"),
                 os.path.join(hook_dir, "session-start-workbuddy.sh"))
    ups = os.path.join(hook_dir, "skills", "using-superpowers")
    os.makedirs(ups, exist_ok=True)
    shutil.copy2(os.path.join(skills_src, "using-superpowers", "SKILL.md"),
                 os.path.join(ups, "SKILL.md"))
    print("[2/4] 引导脚本 -> %s" % hook_dir)
    return hook_dir


def merge(settings, hook_dir):
    cfg = {}
    if os.path.isfile(settings):
        try:
            cfg = json.load(open(settings, encoding="utf-8-sig"))
        except Exception:
            cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    hooks = cfg.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        cfg["hooks"] = hooks

    script = os.path.join(hook_dir, "session-start-workbuddy.sh").replace("\\", "/")
    # WorkBuddy 在 Windows 上强制用 Git Bash 执行 command 字符串;显式 bash 调用最稳
    # (不依赖 .sh 的 exec bit 在 Windows 上的保留情况)
    cmd = 'bash "%s"' % script
    handler = {"type": "command", "command": cmd, "name": NAME, "timeout": TIMEOUT}

    for event in list(hooks.keys()):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        for d in entries:
            if isinstance(d, dict) and isinstance(d.get("hooks"), list):
                d["hooks"] = [x for x in d["hooks"]
                              if not (isinstance(x, dict) and x.get("name") == NAME)]
    hooks["SessionStart"] = [
        d for d in hooks.get("SessionStart", [])
        if not (isinstance(d, dict) and isinstance(d.get("hooks"), list) and not d["hooks"])]
    hooks["SessionStart"].append({"hooks": [handler]})

    if os.path.isfile(settings):
        shutil.copy2(settings, settings + ".bak-superpowers-" + time.strftime("%Y%m%d-%H%M%S"))
    tmp = settings + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, settings)
    print("[3/4] SessionStart hook 幂等合并 -> %s" % settings)
    print("      command = %s" % cmd)


def self_check(hook_dir):
    script = os.path.join(hook_dir, "session-start-workbuddy.sh")
    bash = shutil.which("bash") or "bash"
    r = subprocess.run([bash, script], capture_output=True)
    ok = False
    try:
        j = json.loads(r.stdout.decode("utf-8"))
        ctx = j.get("hookSpecificOutput", {}).get("additionalContext", "")
        ok = isinstance(ctx, str) and "using-superpowers" in ctx and len(ctx) > 500
    except Exception:
        pass
    print("[4/4] 链路自检 exit=%d,引导上下文 %d 字符,信封校验 %s"
          % (r.returncode, len(r.stdout), "OK" if ok else "失败"))
    if not ok and r.stderr:
        print("      stderr: %s" % r.stderr.decode("utf-8", "replace")[:300])


def uninstall(settings, home):
    skills_dst = os.path.join(home, ".workbuddy", "skills")
    hook_dir = os.path.join(home, ".workbuddy", "hooks", "superpowers")
    if os.path.isfile(settings):
        try:
            cfg = json.load(open(settings, encoding="utf-8-sig"))
        except Exception:
            cfg = {}
        hooks = cfg.get("hooks") if isinstance(cfg, dict) else None
        if isinstance(hooks, dict):
            for event in list(hooks.keys()):
                entries = hooks.get(event)
                if not isinstance(entries, list):
                    continue
                cleaned = []
                for d in entries:
                    if isinstance(d, dict) and isinstance(d.get("hooks"), list):
                        d["hooks"] = [x for x in d["hooks"]
                                      if not (isinstance(x, dict) and x.get("name") == NAME)]
                    cleaned.append(d)
                hooks[event] = [d for d in cleaned
                                if not (isinstance(d, dict)
                                        and isinstance(d.get("hooks"), list) and not d["hooks"])]
            shutil.copy2(settings, settings + ".bak-superpowers-uninstall-"
                         + time.strftime("%Y%m%d-%H%M%S"))
            with open(settings + ".tmp", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(settings + ".tmp", settings)
    for name in SKILL_NAMES:  # 只删 superpowers 装的那 14 个,用户其它技能不动
        shutil.rmtree(os.path.join(skills_dst, name), ignore_errors=True)
    shutil.rmtree(hook_dir, ignore_errors=True)
    print("已卸载 superpowers(name=%s):hook 摘除 + 14 个技能删除" % NAME)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--settings", default=None)
    args = ap.parse_args()

    home = os.path.expanduser("~")
    settings = args.settings or os.path.join(home, ".workbuddy", "settings.json")
    if args.uninstall:
        uninstall(settings, home)
        return

    repo = repo_root(args.repo)
    if not os.path.isdir(os.path.join(repo, "skills")):
        print("找不到 superpowers 仓库 skills/ 目录: %s" % repo)
        sys.exit(1)
    hook_dir = install(repo, home)
    merge(settings, hook_dir)
    self_check(hook_dir)
    print("\n部署完成。WorkBuddy 的 hooks 在会话启动时加载 —— 需重启 WorkBuddy 新开会话才生效。")


if __name__ == "__main__":
    main()
