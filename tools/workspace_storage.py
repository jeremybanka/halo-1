"""Shared, conservative storage admission and retention for local N64 work.

Only positively inventoried outputs of new, successful managed builds are
eligible for cleanup. Existing builds, source, assets and arbitrary .bin files
are never adopted as disposable. All worktrees share the main checkout's state.
"""

from contextlib import contextmanager
import contextvars
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import time
import uuid

GIB = 1024 ** 3
ACTIVE = contextvars.ContextVar("workspace_storage_run", default=None)
DEFAULTS = {
    "version": 1, "minimum_free_gib": 20, "warning_free_gib": 30,
    "default_build_peak_gib": 1, "cleanup_minimum_age_hours": 48,
    "worktree_directory_suffix": "-worktrees", "branch_prefix": "jeremybanka/",
}
PROTECTED = re.compile(r"(^|[-_.])(accepted|baseline|checkpoint|current|final|release|before|reference|play|playable|assets?|banks?|snapshots?)([-_.]|$)", re.I)


class StorageError(RuntimeError):
    pass


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).strip()


def worktrees(root):
    raw = subprocess.check_output(["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"])
    return [Path(os.fsdecode(field[9:])).resolve() for field in raw.split(b"\0") if field.startswith(b"worktree ")]


def main_root(root):
    trees = worktrees(root)
    if not trees:
        raise StorageError("No main worktree found")
    return trees[0]


def nearest_existing(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path


def no_symlinks(path, boundary):
    path = Path(os.path.abspath(path))
    boundary = Path(boundary).resolve()
    if not path.is_relative_to(boundary):
        raise StorageError(f"Output is outside its checkout: {path}")
    for part in (path, *path.parents):
        if part == boundary:
            break
        if part.is_symlink():
            raise StorageError(f"Refusing a symlink in an output/cleanup path: {part}")
    return path


def fingerprint(path):
    s = Path(path).lstat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def allocated(path):
    total = 0
    if not Path(path).exists():
        return total
    for directory, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [n for n in dirs if not (Path(directory) / n).is_symlink()]
        for name in files:
            p = Path(directory) / name
            if not p.is_symlink():
                try:
                    s = p.stat()
                    total += getattr(s, "st_blocks", 0) * 512 or s.st_size
                except FileNotFoundError:
                    pass
    return total


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Policy:
    def __init__(self, root, *, shared_root=None):
        self.root = Path(root).resolve()
        self.shared_root = Path(shared_root).resolve() if shared_root else main_root(self.root)
        config = self.shared_root / "workspace-policy.json"
        self.config = {**DEFAULTS, **(json.loads(config.read_text()) if config.exists() else {})}
        if self.config["version"] != 1:
            raise StorageError("Unsupported workspace policy version")
        for key in ("minimum_free_gib", "warning_free_gib", "default_build_peak_gib", "cleanup_minimum_age_hours"):
            value = self.config[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise StorageError(f"Invalid positive storage limit: {key}")
        if self.config["warning_free_gib"] < self.config["minimum_free_gib"]:
            raise StorageError("Storage warning must be at or above the safety floor")
        if not re.fullmatch(r"-[A-Za-z0-9-]+", self.config["worktree_directory_suffix"]):
            raise StorageError("Worktree directory suffix must be a simple sibling name")
        self.state_dir = self.shared_root / ".workspace"
        self.state_file = self.state_dir / "state.json"

    def read(self):
        if not self.state_file.exists():
            return {"leases": {}, "pins": {}, "current": {}, "worktrees": {}}
        return json.loads(self.state_file.read_text())

    @contextmanager
    def locked(self):
        # Local N64 tooling runs on POSIX; never silently omit the shared lock.
        try:
            import fcntl
        except ImportError as error:
            raise StorageError("Workspace storage guards require POSIX file locking") from error
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.state_dir / "lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                state = self.read()
                yield state
                atomic_json(self.state_file, state)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def leases(self, state):
        host = socket.gethostname()
        # A foreign-host record is retained conservatively, never guessed stale.
        return {key: value for key, value in state["leases"].items()
                if value["host"] != host or alive(value["pid"])}

    def pinned(self, path, state):
        path = Path(path).resolve()
        return any(path.is_relative_to(Path(pin)) for pin in state["pins"])

    def validate_output(self, path):
        path = no_symlinks(path, self.root)
        if not path.is_relative_to(self.root / "build") or path == self.root / "build":
            raise StorageError("Build output must be a dedicated directory below this checkout's build/")
        trees = worktrees(self.root)
        owners = [tree for tree in trees if path.is_relative_to(tree)]
        if not owners or max(owners, key=lambda p: len(p.parts)) != self.root:
            raise StorageError("Output belongs to another worktree")
        if any(tree.is_relative_to(path) for tree in trees):
            raise StorageError("Output contains a source worktree")
        if any(part in {"halo64-assets", "assets", "_asset-snapshots", "frontend-files"} for part in path.relative_to(self.root).parts):
            raise StorageError("Asset directories cannot be managed build outputs")
        if self.pinned(path, self.read()):
            raise StorageError(f"Output is pinned; choose a fresh directory: {path}")
        if any(Path(pin).is_relative_to(path) for pin in self.read()["pins"]):
            raise StorageError(f"Output contains pinned artifacts: {path}")
        return path

    def pin(self, path, reason):
        path = Path(path).resolve(strict=True)
        if not reason.strip():
            raise StorageError("A retention reason is required")
        with self.locked() as state:
            state["pins"][str(path)] = {"reason": reason, "created": time.time()}

    def validate_worktree_output(self, path):
        path = Path(path).absolute()
        parent = self.shared_root.parent / (self.shared_root.name + self.config["worktree_directory_suffix"])
        if path.parent != parent or parent.is_symlink() or path.exists():
            raise StorageError("New source worktrees require a fresh external sibling destination")
        if any(path.resolve().is_relative_to(tree) for tree in worktrees(self.root)):
            raise StorageError("Source worktrees cannot be nested")
        return path

    def cleanup(self, *, apply=False):
        removed = []
        candidates = []
        with self.locked() as state:
            active = self.leases(state)
            current = set(state["current"].values())
            run_dir = self.state_dir / "runs"
            for record in sorted(run_dir.glob("*.json")) if run_dir.exists() else []:
                run = json.loads(record.read_text())
                if (run.get("kind") != "n64-build" or run["status"] != "complete" or run["id"] in active or run["id"] in current
                        or run.get("keep") or time.time() - run["finished"] < self.config["cleanup_minimum_age_hours"] * 3600):
                    continue
                output = Path(run["output"])
                owner = Path(run["root"])
                if self.pinned(output, state) or any(PROTECTED.search(part) for part in output.relative_to(owner / "build").parts):
                    continue
                try:
                    no_symlinks(output, owner)
                    rom = Path(run["rom"]["path"])
                    no_symlinks(rom, owner)
                    if digest(rom) != run["rom"]["sha256"]:
                        continue
                except (OSError, StorageError):
                    continue
                for entry in run.get("disposable", []):
                    path = Path(entry["path"])
                    try:
                        no_symlinks(path, owner)
                        if not path.is_relative_to(output) or not self.disposable_name(path, output, rom):
                            continue
                        if self.pinned(path, state) or not path.is_file() or fingerprint(path) != entry["fingerprint"] or digest(path) != entry["sha256"]:
                            continue
                        candidates.append({**entry, "checkout_root": str(owner), "run": run["id"]})
                    except (OSError, StorageError):
                        continue
            if apply and candidates:
                # One batch receipt, written before any unlink. An interrupted
                # sweep retains the original candidate identities for recovery.
                receipt = self.state_dir / "receipts" / (uuid.uuid4().hex + ".json")
                result = {"action": "remove managed intermediates", "files": candidates, "removed": []}
                atomic_json(receipt, result)
                try:
                    for entry in candidates:
                        path = Path(entry["path"])
                        try:
                            no_symlinks(path, entry["checkout_root"])
                            if fingerprint(path) != entry["fingerprint"] or digest(path) != entry["sha256"]:
                                continue
                            path.unlink()
                            removed.append(entry)
                        except (OSError, StorageError):
                            continue
                finally:
                    result["removed"] = removed
                    atomic_json(receipt, result)
        return {"apply": apply, "files": candidates, "removed": removed,
                "eligible_bytes": sum(e["bytes"] for e in candidates)}

    @staticmethod
    def disposable_name(path, output, rom):
        return (path == output / "frontend.dfs"
                or path.parent == output / "objects" and path.suffix == ".o"
                or path in [rom.with_suffix(suffix) for suffix in (".elf", ".stripped", ".sym", ".map")])


class StorageRun:
    def __init__(self, policy, output, *, peak_gib=None, kind="command", keep=False, ephemeral=False):
        self.policy = policy
        self.output = Path(output).absolute()
        self.peak = policy.config["default_build_peak_gib"] if peak_gib is None else peak_gib
        if not math.isfinite(self.peak) or self.peak <= 0:
            raise StorageError("Peak storage estimate must be positive and finite")
        self.kind, self.keep = kind, keep
        self.ephemeral = ephemeral
        self.id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
        self.record_path = policy.state_dir / "runs" / (self.id + ".json")
        self.token = None

    def __enter__(self):
        self.output = (self.policy.validate_worktree_output(self.output) if self.kind == "worktree"
                       else self.policy.validate_output(self.output))
        if self.kind == "n64-build" and self.output.exists() and (
                any(self.output.glob("*.z64")) or any(self.output.glob("*.build.json")) or (self.output / "frontend.dfs").exists()):
            raise StorageError(f"Preserving existing build products; choose a fresh --output-dir: {self.output}")
        # Automatic retention is restricted to previously registered managed runs.
        self.policy.cleanup(apply=True)
        mount = nearest_existing(self.output)
        self.device = mount.stat().st_dev
        self.initial_bytes = allocated(self.output)
        with self.policy.locked() as state:
            state["leases"] = self.policy.leases(state)
            ancestors = set()
            parent_id = os.environ.get("HALO_WORKSPACE_PARENT_RUN")
            while parent_id in state["leases"] and parent_id not in ancestors:
                parent = state["leases"][parent_id]
                if parent["host"] != socket.gethostname() or not self.output.is_relative_to(Path(parent["output"])):
                    break
                if self.peak * GIB > parent["budget_bytes"]:
                    raise StorageError("Nested job estimate exceeds its parent batch budget")
                ancestors.add(parent_id)
                parent_id = parent.get("parent")
            if any(key not in ancestors and (Path(v["output"]) == self.output or self.output.is_relative_to(Path(v["output"])) or Path(v["output"]).is_relative_to(self.output)) for key, v in state["leases"].items()):
                raise StorageError("Another managed job owns this output directory")
            reserved = sum(v["bytes"] for key, v in state["leases"].items() if key not in ancestors and v["device"] == self.device)
            free = shutil.disk_usage(mount).free
            own_reservation = 0 if ancestors else int(self.peak * GIB)
            required = int(self.policy.config["minimum_free_gib"] * GIB) + own_reservation + reserved
            if free < required:
                raise StorageError(f"Storage limit: {free/GIB:.2f} GiB free; need {required/GIB:.2f} GiB "
                                   f"({self.peak:g} GiB job + {reserved/GIB:.2f} GiB reserved + "
                                   f"{self.policy.config['minimum_free_gib']:g} GiB safety floor). "
                                   "Use tools/workspace.py status/cleanup; assets and legacy builds will not be deleted automatically.")
            self.lease = {"pid": os.getpid(), "host": socket.gethostname(), "device": self.device,
                          "bytes": own_reservation, "budget_bytes": int(self.peak * GIB),
                          "parent": os.environ.get("HALO_WORKSPACE_PARENT_RUN") if ancestors else None,
                          "output": str(self.output), "started": time.time()}
            state["leases"][self.id] = self.lease
            self.record = {"id": self.id, "root": str(self.policy.root), "output": str(self.output),
                           "status": "running", "kind": self.kind, "keep": self.keep,
                           "ephemeral": self.ephemeral, **self.lease}
            self.record["source_commit"] = git(self.policy.root, "rev-parse", "HEAD")
            self.record["limits"] = dict(self.policy.config)
            if self.kind == "n64-build":
                import sys
                self.record["build_arguments"] = sys.argv[1:]
            atomic_json(self.record_path, self.record)
        if free < self.policy.config["warning_free_gib"] * GIB:
            print(f"Storage warning: {free/GIB:.2f} GiB free; reserve is enforced.", flush=True)
        self.token = ACTIVE.set(self)
        return self

    def check(self):
        free = shutil.disk_usage(nearest_existing(self.output)).free
        if free < self.policy.config["minimum_free_gib"] * GIB:
            raise StorageError("Safety floor reached; stopping only the command launched by this storage guard")
        if allocated(self.output) - self.initial_bytes > self.peak * GIB:
            raise StorageError(f"Job exceeded its {self.peak:g} GiB output growth budget")

    def command(self, command, **kwargs):
        self.check()
        kwargs = {**kwargs, "start_new_session": True,
                  "env": {**os.environ, **(kwargs.get("env") or {}), "HALO_WORKSPACE_PARENT_RUN": self.id}}
        check = kwargs.pop("check", True)
        if kwargs.get("capture_output") or "input" in kwargs or kwargs.get("stdout") == subprocess.PIPE or kwargs.get("stderr") == subprocess.PIPE:
            raise StorageError("Managed commands stream output; capture it to a file instead")
        process = subprocess.Popen([str(part) for part in command], **kwargs)
        try:
            while process.poll() is None:
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
                self.check()
            self.check()
            if check and process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
            return subprocess.CompletedProcess(command, process.returncode)
        except BaseException:
            # The process group was created here; never signal existing apps/jobs.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise

    def finish_build(self):
        verified = []
        for manifest in self.output.glob("*.build.json"):
            data = json.loads(manifest.read_text())
            info = data["rom"]
            rom = self.output / Path(info["path"]).name
            no_symlinks(rom, self.policy.root)
            if not rom.is_file() or rom.stat().st_size != info["bytes"] or digest(rom) != info["sha256"]:
                raise StorageError("ROM verification failed; preserving all intermediates")
            verified.append((rom, info))
        if len(verified) != 1:
            raise StorageError("Expected one verified ROM and manifest; preserving intermediates")
        rom, info = verified[0]
        self.record["rom"] = {**info, "path": str(rom)}
        self.record["asset_commit"] = data.get("asset_commit")
        self.record["toolchain"] = data.get("toolchain")
        self.record["build_manifest_sha256"] = digest(next(self.output.glob("*.build.json")))
        disposable = list((self.output / "objects").glob("*.o")) + [rom.with_suffix(s) for s in (".elf", ".stripped", ".sym", ".map")]
        dfs = self.output / "frontend.dfs"
        if dfs.exists():
            no_symlinks(dfs, self.policy.root)
            dfs_info = {"path": str(dfs), "bytes": dfs.stat().st_size, "sha256": digest(dfs), "fingerprint": fingerprint(dfs)}
            self.record["packaged_filesystem"] = dfs_info
            # Persist verification evidence before removing a newly created intermediate.
            atomic_json(self.record_path, self.record)
            if not self.keep and not self.policy.pinned(self.output, self.policy.read()):
                dfs.unlink()
                self.record["packaged_filesystem_removed"] = True
            else:
                disposable.append(dfs)
        self.record["disposable"] = []
        for path in disposable:
            if path.is_file():
                no_symlinks(path, self.policy.root)
                self.record["disposable"].append({"path": str(path), "bytes": path.stat().st_size,
                                                  "fingerprint": fingerprint(path), "sha256": digest(path)})

    def __exit__(self, typ, error, tb):
        try:
            if typ is None:
                self.check()
                if self.kind == "n64-build":
                    self.finish_build()
                self.record["status"] = "complete"
            else:
                self.record.update(status="failed", error=str(error))
        except BaseException as failure:
            self.record.update(status="failed", error=str(failure))
            raise
        finally:
            self.record["finished"] = time.time()
            atomic_json(self.record_path, self.record)
            with self.policy.locked() as state:
                state["leases"].pop(self.id, None)
                if self.record["status"] == "complete" and self.kind == "n64-build" and not self.ephemeral:
                    state["current"][str(self.policy.root)] = self.id
            ACTIVE.reset(self.token)


def run_command(command, **kwargs):
    run = ACTIVE.get()
    return run.command(command, **kwargs) if run else subprocess.run(command, **kwargs)


def build_entry(root, main):
    """Compatibility entry installed in all current N64 build scripts."""
    import sys
    if "--help" in sys.argv or "-h" in sys.argv:
        return main()
    output = None
    for index, arg in enumerate(sys.argv[1:], 1):
        if arg == "--output-dir" and index + 1 < len(sys.argv):
            output = Path(sys.argv[index + 1])
        elif arg.startswith("--output-dir="):
            output = Path(arg.split("=", 1)[1])
    if output is None:
        output = Path(root) / "build/runs" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
        sys.argv.extend(["--output-dir", str(output)])
    try:
        with StorageRun(Policy(root), output, kind="n64-build", keep="--keep-dfs" in sys.argv,
                        ephemeral=os.environ.get("HALO_WORKSPACE_EPHEMERAL") == "1"):
            return main()
    except StorageError as error:
        raise SystemExit(f"build.py: {error}") from error
