#!/usr/bin/env python3
"""Create isolated worktrees, reserve storage, pin artifacts, and review cleanup."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from workspace_storage import GIB, PROTECTED, Policy, StorageError, StorageRun, git, nearest_existing, worktrees
import shutil

GUARD_ENTRY = '''if __name__ == "__main__":
    # Shared workspace storage guard; legacy worktree locations remain valid.
    _common = Path(subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True).strip())
    _policy_tools = _common.parent / "tools"
    if (_policy_tools / "workspace_storage.py").is_file() or (_common.parent / "workspace-policy.json").is_file():
        sys.path.insert(0, str(_policy_tools))
        from workspace_storage import build_entry, run_command as _storage_run_command
        build_entry(ROOT, main)
    else:
        # A historical branch on a machine that has not adopted this policy.
        main()
'''


def install_guard(root):
    """Add a small shared-policy entry; do not rewrite branch-specific build code."""
    root = Path(root).resolve()
    path = root / "port/n64/build.py"
    if not path.exists():
        return False
    source = path.read_text()
    installed = "# Shared workspace storage guard" in source
    parser_line = "    parser = argparse.ArgumentParser(description=__doc__)\n"
    entry = 'if __name__ == "__main__":\n    main()\n'
    command = "        subprocess.run(\n"
    if not installed and (source.count(parser_line) != 1 or not source.endswith(entry) or source.count(command) != 1):
        raise StorageError(f"Build script needs manual compatibility review: {path}")
    shared = Policy(root).shared_root
    # The Git common directory anchors the same policy for all linked worktrees.
    if installed:
        start = source.rfind('if __name__ == "__main__":\n')
        if start < 0:
            raise StorageError(f"Missing guarded build entry: {path}")
        result = source[:start] + GUARD_ENTRY
    else:
        result = source.replace(parser_line, parser_line + '    parser.add_argument("--keep-dfs", action="store_true", help="Retain the packaged filesystem for explicit repacking/debugging")\n', 1)
        result = result.replace(command, '        globals().get("_storage_run_command", subprocess.run)(\n', 1)
        result = result[:-len(entry)] + GUARD_ENTRY
    if result == source:
        return False
    compile(result, str(path), "exec")
    # Save the exact predecessor for review/recovery without altering Git history.
    from workspace_storage import digest
    backup = shared / ".workspace/guard-backups" / (digest(path) + ".py")
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(source)
    if path.read_text() != source:
        raise StorageError(f"Build script changed during installation: {path}")
    path.write_text(result)
    return True


def status(policy):
    state = policy.read()
    trees = worktrees(policy.root)
    leases = policy.leases(state)
    return {
        "main_checkout": str(policy.shared_root),
        "worktree_root": str(policy.shared_root.parent / (policy.shared_root.name + policy.config["worktree_directory_suffix"])),
        "free_gib": round(shutil.disk_usage(policy.root).free / GIB, 2),
        "limits": policy.config,
        "active_reservations": leases,
        "pin_count": len(state["pins"]),
        "pins_file": str(policy.state_file),
        "worktrees": [{"path": str(tree), "legacy_nested_location": any(tree != other and tree.is_relative_to(other) for other in trees),
                       "guard_installed": (tree / "port/n64/build.py").exists() and "# Shared workspace storage guard" in (tree / "port/n64/build.py").read_text()}
                      for tree in trees],
    }


def protect_existing(policy):
    """Register existing inputs/baselines/current artifacts without changing them."""
    trees = worktrees(policy.root)
    pins = {}
    newest = {}
    for tree in trees:
        for path in (tree / "halo64-assets", tree / "build/n64"):
            if path.exists():
                pins[str(path.resolve())] = "Existing private assets or legacy archive"
        build = tree / "build"
        if not build.is_dir() or build.is_symlink():
            continue
        for directory, dirs, files in os.walk(build, followlinks=False):
            parent = Path(directory)
            dirs[:] = [name for name in dirs if name not in {".git", ".workspace"} and not (parent / name).is_symlink()]
            # Source checkouts are inventoried from their own build root; never
            # classify a nested source tree as a disposable artifact directory.
            dirs[:] = [name for name in dirs if (parent / name).resolve() not in trees]
            for name in list(dirs):
                if PROTECTED.search(name):
                    pins[str((parent / name).resolve())] = "Existing baseline, release, reference or asset directory"
            for name in files:
                path = parent / name
                if path.suffix == ".z64" and not path.is_symlink():
                    stamp = path.stat().st_mtime_ns
                    if tree not in newest or stamp > newest[tree][0]:
                        newest[tree] = (stamp, path)
    for _, rom in newest.values():
        if any(tree.is_relative_to(rom.parent) for tree in trees):
            pins[str(rom.resolve())] = "Existing current ROM (directory contains source worktree)"
        else:
            pins[str(rom.parent.resolve())] = "Existing latest build in its checkout"
    with policy.locked() as state:
        for path, reason in pins.items():
            state["pins"].setdefault(path, {"reason": reason, "created": time.time()})
        for tree in trees:
            state["worktrees"].setdefault(str(tree), {"status": "grandfathered", "owner": "existing checkout", "purpose": git(tree, "branch", "--show-current") or "detached reference"})
    return {"protected_paths": len(pins), "registered_worktrees": len(trees), "artifacts_modified": 0}


def add_worktree(policy, args):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", args.task):
        raise StorageError("Task names use lowercase letters, numbers, and hyphens")
    parent = policy.shared_root.parent / (policy.shared_root.name + policy.config["worktree_directory_suffix"])
    target = parent / args.task
    if parent.is_symlink() or any(target.resolve().is_relative_to(tree) for tree in worktrees(policy.root)):
        raise StorageError("Worktrees must be outside all existing checkouts")
    if target.exists():
        raise StorageError(f"Destination already exists: {target}")
    # Admission uses the repository volume; reject another volume to avoid an
    # estimate reserved against the wrong filesystem.
    if nearest_existing(parent).stat().st_dev != policy.shared_root.stat().st_dev:
        raise StorageError("Create worktrees on the repository volume")
    branch = policy.config["branch_prefix"] + args.task
    base = git(policy.root, "rev-parse", "--verify", "--end-of-options", args.base + "^{commit}")
    # The worktree itself is source, never a managed/disposable output.
    with StorageRun(policy, target, peak_gib=args.peak_gib, kind="worktree") as run:
        parent.mkdir(parents=True, exist_ok=True)
        run.command(["git", "-C", str(policy.root), "worktree", "add", "-b", branch, str(target), base])
        # New branches made from older commits still receive the mandatory
        # guidance and the same guard. No existing source changes are discarded.
        guidance = target / "AGENTS.md"
        if not guidance.exists():
            guidance.write_text((policy.shared_root / "AGENTS.md").read_text())
        elif "WORKSPACE_POLICY.md" not in guidance.read_text():
            with guidance.open("a") as stream:
                stream.write("\n\n# Workspace storage\n\nFollow [WORKSPACE_POLICY.md](WORKSPACE_POLICY.md). "
                             "Use tools/workspace.py for new worktrees and disk-heavy commands. "
                             "Preserve existing worktrees, builds, baselines and assets.\n")
        for name in ("WORKSPACE_POLICY.md", "workspace-policy.json"):
            source = policy.shared_root / name
            if source.exists() and not (target / name).exists():
                shutil.copyfile(source, target / name)
        for name in ("workspace.py", "workspace_storage.py"):
            target_tool = target / "tools" / name
            if not target_tool.exists():
                target_tool.parent.mkdir(exist_ok=True)
                shutil.copyfile(policy.shared_root / "tools" / name, target_tool)
        install_guard(target)
        with policy.locked() as state:
            state["worktrees"][str(target)] = {"owner": args.owner, "task": args.task, "branch": branch,
                                                "base": git(target, "rev-parse", "HEAD"), "status": "active"}
    return {"path": str(target), "branch": branch}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="A checkout of this repository")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status", help="Report capacity, reservations, pins and legacy locations")
    sub.add_parser("install-guards", help="Install/update the shared guard in registered N64 checkouts")
    sub.add_parser("protect-existing", help="Pin existing inputs, baselines and latest builds; never remove them")
    cleanup = sub.add_parser("cleanup", help="Dry-run expired managed intermediates; legacy artifacts are excluded")
    cleanup.add_argument("--apply", action="store_true")
    pin = sub.add_parser("pin", help="Protect a current build, baseline or asset directory")
    pin.add_argument("path", type=Path)
    pin.add_argument("--reason", required=True)
    tree = sub.add_parser("worktree-add", help="Create a task worktree in the external sibling directory")
    tree.add_argument("task")
    tree.add_argument("--owner", required=True)
    tree.add_argument("--base", default="HEAD")
    tree.add_argument("--peak-gib", type=float, default=1)
    run = sub.add_parser("run", help="Guard a batch import/extraction/matrix command (not an interactive app)")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--peak-gib", type=float, required=True, help="Maximum estimated additional output size")
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        policy = Policy(args.root)
        if args.action == "status":
            result = status(policy)
        elif args.action == "install-guards":
            result = {str(tree): install_guard(tree) for tree in worktrees(policy.root)}
        elif args.action == "protect-existing":
            result = protect_existing(policy)
        elif args.action == "pin":
            path = args.path if args.path.is_absolute() else policy.root / args.path
            policy.pin(path, args.reason)
            result = {"pinned": str(path.resolve()), "reason": args.reason}
        elif args.action == "cleanup":
            result = policy.cleanup(apply=args.apply)
        elif args.action == "worktree-add":
            result = add_worktree(policy, args)
        else:
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            if not command:
                raise StorageError("A batch command is required after --")
            output = args.output if args.output.is_absolute() else policy.root / args.output
            with StorageRun(policy, output, peak_gib=args.peak_gib) as job:
                job.command(command, cwd=policy.root)
            result = {"run": job.id, "status": "complete"}
        print(json.dumps(result, indent=2))
        return 0
    except (StorageError, subprocess.CalledProcessError, OSError, ValueError) as error:
        parser.exit(1, f"workspace: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
