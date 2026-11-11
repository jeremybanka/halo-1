"""Safety and integration checks using temporary repositories and tiny files."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import workspace
import workspace_storage as storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="halo-storage-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        (self.root / "README.md").write_text("fixture\n")
        (self.root / "AGENTS.md").write_text("Fixture policy\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.policy = storage.Policy(self.root)
        mock = patch("workspace_storage.shutil.disk_usage", return_value=shutil._ntuple_diskusage(200 * storage.GIB, 100 * storage.GIB, 100 * storage.GIB))
        mock.start()
        self.addCleanup(mock.stop)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True, stderr=subprocess.PIPE).strip()

    def out(self, name):
        return self.root / "build" / name

    def completed(self, name, *, keep=False, bad_hash=False):
        output = self.out(name)
        job = storage.StorageRun(self.policy, output, kind="n64-build", keep=keep)
        with job:
            output.mkdir(parents=True)
            rom = output / "game.z64"
            rom.write_bytes(b"tiny ROM")
            (output / "game.build.json").write_text(json.dumps({"rom": {"path": str(rom), "bytes": rom.stat().st_size, "sha256": "wrong" if bad_hash else storage.digest(rom)}}))
            (output / "frontend.dfs").write_bytes(b"filesystem")
            (output / "objects").mkdir()
            (output / "objects/main.o").write_bytes(b"object")
            (output / "game.elf").write_bytes(b"link")
            (output / "candidate.bin").write_bytes(b"never classify arbitrary state/asset files")
        return job

    def expire(self, job):
        data = json.loads(job.record_path.read_text())
        data["finished"] = time.time() - 72 * 3600
        storage.atomic_json(job.record_path, data)
        with self.policy.locked() as state:
            state["current"].clear()

    def test_low_space_refuses_before_creating_output(self):
        with patch("workspace_storage.shutil.disk_usage", return_value=shutil._ntuple_diskusage(30 * storage.GIB, 10 * storage.GIB, int(20.5 * storage.GIB))):
            with self.assertRaisesRegex(storage.StorageError, "Storage limit"):
                with storage.StorageRun(self.policy, self.out("refused")):
                    self.fail("job admitted")
        self.assertFalse(self.out("refused").exists())
        self.assertEqual(self.policy.read()["leases"], {})

    def test_concurrent_jobs_cannot_claim_same_space(self):
        with patch("workspace_storage.shutil.disk_usage", return_value=shutil._ntuple_diskusage(50 * storage.GIB, 25 * storage.GIB, 25 * storage.GIB)):
            with storage.StorageRun(self.policy, self.out("one"), peak_gib=4):
                with self.assertRaisesRegex(storage.StorageError, "reserved"):
                    with storage.StorageRun(self.policy, self.out("two"), peak_gib=4):
                        self.fail("overcommitted")
        self.assertEqual(self.policy.read()["leases"], {})

    def test_nested_jobs_share_budget_but_not_unrelated_jobs(self):
        with storage.StorageRun(self.policy, self.out("matrix"), peak_gib=4) as parent:
            with patch.dict(os.environ, {"HALO_WORKSPACE_PARENT_RUN": parent.id}):
                with storage.StorageRun(self.policy, self.out("matrix/child"), peak_gib=1) as child:
                    self.assertEqual(child.lease["bytes"], 0)
                    self.assertEqual(child.lease["parent"], parent.id)
                with self.assertRaisesRegex(storage.StorageError, "exceeds"):
                    with storage.StorageRun(self.policy, self.out("matrix/too-big"), peak_gib=5):
                        pass

    def test_existing_build_and_asset_symlink_are_preserved(self):
        output = self.out("old")
        output.mkdir(parents=True)
        rom = output / "old.z64"
        rom.write_bytes(b"preserve")
        with self.assertRaisesRegex(storage.StorageError, "Preserving existing"):
            with storage.StorageRun(self.policy, output, kind="n64-build"):
                pass
        self.assertEqual(rom.read_bytes(), b"preserve")
        assets = self.root / "halo64-assets/assets"
        assets.mkdir(parents=True)
        (self.root / "build/shared").symlink_to(assets)
        with self.assertRaisesRegex(storage.StorageError, "symlink"):
            with storage.StorageRun(self.policy, self.out("shared/new")):
                pass

    def test_reservations_are_shared_across_processes(self):
        script = '''import sys,time,shutil
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import workspace_storage as s
s.shutil.disk_usage=lambda _:shutil._ntuple_diskusage(50*s.GIB,25*s.GIB,25*s.GIB)
root,out,marker,release=map(Path,sys.argv[2:])
try:
    with s.StorageRun(s.Policy(root),out,peak_gib=4):
        marker.write_text('admitted')
        until=time.monotonic()+10
        while not release.exists() and time.monotonic()<until:time.sleep(.02)
except s.StorageError:sys.exit(7)
'''
        tools = str(Path(storage.__file__).parent)
        marker = self.root / "first-admitted"
        release = self.root / "release-first"
        first = subprocess.Popen([sys.executable, "-c", script, tools, str(self.root), str(self.out("one")), str(marker), str(release)], stdout=subprocess.DEVNULL)
        try:
            until = time.monotonic() + 5
            while not marker.exists() and first.poll() is None and time.monotonic() < until:
                time.sleep(.02)
            self.assertTrue(marker.exists())
            second = subprocess.run([sys.executable, "-c", script, tools, str(self.root), str(self.out("two")), str(self.root / "second-admitted"), str(release)], capture_output=True, timeout=5)
            self.assertEqual(second.returncode, 7, second.stderr)
            self.assertFalse((self.root / "second-admitted").exists())
        finally:
            release.write_text("finish")
            first.wait(timeout=5)
        self.assertEqual(self.policy.read()["leases"], {})

    def test_success_removes_only_new_verified_dfs(self):
        job = self.completed("new")
        self.assertFalse((job.output / "frontend.dfs").exists())
        self.assertTrue((job.output / "game.z64").exists())
        self.assertTrue((job.output / "candidate.bin").exists())
        data = json.loads(job.record_path.read_text())
        self.assertEqual(data["status"], "complete")
        self.assertTrue(data["packaged_filesystem_removed"])

    def test_failed_rom_verification_preserves_intermediates(self):
        with self.assertRaisesRegex(storage.StorageError, "verification failed"):
            self.completed("bad", bad_hash=True)
        self.assertTrue((self.out("bad") / "frontend.dfs").exists())
        self.assertEqual(self.policy.read()["leases"], {})
        record = next((self.policy.state_dir / "runs").glob("*.json"))
        self.assertEqual(json.loads(record.read_text())["status"], "failed")

    def test_cleanup_is_dry_run_and_never_deletes_rom_or_unmanaged_files(self):
        job = self.completed("old")
        self.expire(job)
        unmanaged = self.out("legacy/frontend.dfs")
        unmanaged.parent.mkdir()
        unmanaged.write_bytes(b"legacy")
        plan = self.policy.cleanup()
        self.assertEqual(len(plan["files"]), 2)
        self.assertTrue((job.output / "objects/main.o").exists())
        result = self.policy.cleanup(apply=True)
        self.assertEqual(len(result["removed"]), 2)
        self.assertTrue((job.output / "game.z64").exists())
        self.assertTrue((job.output / "game.build.json").exists())
        self.assertTrue((job.output / "candidate.bin").exists())
        self.assertEqual(unmanaged.read_bytes(), b"legacy")

    def test_current_pinned_keep_and_baseline_runs_are_protected(self):
        current = self.completed("current-build")
        self.assertEqual(self.policy.cleanup(apply=True)["removed"], [])
        for name, keep in (("pinned", False), ("debug", True), ("accepted-baseline", False)):
            job = self.completed(name, keep=keep)
            self.expire(job)
            if name == "pinned":
                self.policy.pin(job.output, "accepted result")
            self.assertEqual(self.policy.cleanup(apply=True)["removed"], [])
        self.assertTrue((current.output / "game.z64").exists())

    def test_changed_file_and_symlink_are_not_cleanup_candidates(self):
        job = self.completed("old")
        self.expire(job)
        obj = job.output / "objects/main.o"
        obj.write_bytes(b"changed")
        elf = job.output / "game.elf"
        elf.unlink()
        asset = self.root / "asset"
        asset.write_bytes(b"source")
        elf.symlink_to(asset)
        self.assertEqual(self.policy.cleanup(apply=True)["removed"], [])
        self.assertEqual(asset.read_bytes(), b"source")

    def test_injected_asset_path_cannot_be_deleted(self):
        job = self.completed("old")
        self.expire(job)
        asset = self.root / "halo64-assets/source.o"
        asset.parent.mkdir()
        asset.write_bytes(b"source")
        data = json.loads(job.record_path.read_text())
        data["disposable"] = [{"path": str(asset), "bytes": asset.stat().st_size, "fingerprint": storage.fingerprint(asset), "sha256": storage.digest(asset)}]
        storage.atomic_json(job.record_path, data)
        self.assertEqual(self.policy.cleanup(apply=True)["removed"], [])
        self.assertTrue(asset.exists())

    def test_guard_stops_only_its_own_over_budget_child(self):
        code = "import sys,time;from pathlib import Path;p=Path(sys.argv[1]);p.mkdir(parents=True);(p/'partial').write_bytes(b'x'*1000);time.sleep(20)"
        real_killpg = os.killpg
        with patch("workspace_storage.os.killpg", wraps=real_killpg) as killpg:
            with self.assertRaisesRegex(storage.StorageError, "growth budget"):
                with storage.StorageRun(self.policy, self.out("over-budget"), peak_gib=0.0000001) as job:
                    job.command([sys.executable, "-c", code, str(job.output)])
            self.assertTrue(killpg.called)
            self.assertTrue(all(call.args[0] != os.getpgrp() for call in killpg.call_args_list))
        self.assertTrue((self.out("over-budget") / "partial").exists())
        self.assertEqual(self.policy.read()["leases"], {})

    def test_running_child_is_stopped_when_free_space_drops(self):
        code = "import time;time.sleep(20)"
        high = shutil._ntuple_diskusage(200 * storage.GIB, 100 * storage.GIB, 100 * storage.GIB)
        low = shutil._ntuple_diskusage(200 * storage.GIB, 181 * storage.GIB, 19 * storage.GIB)
        with storage.StorageRun(self.policy, self.out("floor-test")) as job:
            with patch("workspace_storage.shutil.disk_usage", side_effect=[high, low]):
                with self.assertRaisesRegex(storage.StorageError, "Safety floor"):
                    job.command([sys.executable, "-c", code])

    def test_ephemeral_build_does_not_replace_current_build(self):
        current = self.completed("retained-current")
        output = self.out("temporary-sd")
        with storage.StorageRun(self.policy, output, kind="n64-build", ephemeral=True):
            output.mkdir(parents=True)
            rom = output / "game.z64"
            rom.write_bytes(b"temporary")
            (output / "game.build.json").write_text(json.dumps({"rom": {"path": str(rom), "bytes": rom.stat().st_size, "sha256": storage.digest(rom)}}))
        self.assertEqual(self.policy.read()["current"][str(self.root)], current.id)

    def test_protect_existing_records_assets_and_current_without_modifying_them(self):
        assets = self.root / "halo64-assets/assets"
        assets.mkdir(parents=True)
        source = assets / "source.map"
        source.write_bytes(b"original")
        baseline = self.out("accepted-baseline")
        baseline.mkdir(parents=True)
        (baseline / "game.z64").write_bytes(b"baseline")
        current = self.out("newest")
        current.mkdir(parents=True)
        (current / "game.z64").write_bytes(b"current")
        before = {p: storage.fingerprint(p) for p in (source, baseline / "game.z64", current / "game.z64")}
        result = workspace.protect_existing(self.policy)
        self.assertEqual(result["artifacts_modified"], 0)
        self.assertTrue(self.policy.pinned(source, self.policy.read()))
        self.assertTrue(self.policy.pinned(baseline, self.policy.read()))
        self.assertTrue(self.policy.pinned(current, self.policy.read()))
        self.assertEqual(before, {p: storage.fingerprint(p) for p in before})

    def test_invalid_limits_fail_closed(self):
        (self.root / "workspace-policy.json").write_text(json.dumps({"minimum_free_gib": 0}))
        with self.assertRaisesRegex(storage.StorageError, "Invalid positive"):
            storage.Policy(self.root)

    def test_completed_batch_records_do_not_break_future_admission(self):
        with storage.StorageRun(self.policy, self.out("first-batch")):
            pass
        with storage.StorageRun(self.policy, self.out("next-batch")):
            pass
        self.assertEqual(self.policy.cleanup(apply=True)["removed"], [])

    def test_stale_reservation_does_not_block_new_job(self):
        with self.policy.locked() as state:
            state["leases"]["dead"] = {"pid": 99999999, "host": __import__('socket').gethostname(),
                "device": self.root.stat().st_dev, "bytes": 1000 * storage.GIB, "budget_bytes": 1000 * storage.GIB,
                "output": str(self.out("stale"))}
        with storage.StorageRun(self.policy, self.out("new-job")):
            self.assertNotIn("dead", self.policy.read()["leases"])

    def test_output_cannot_contain_a_pinned_asset(self):
        asset = self.out("import/source.map")
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"asset")
        self.policy.pin(asset, "source asset")
        with self.assertRaisesRegex(storage.StorageError, "contains pinned"):
            with storage.StorageRun(self.policy, asset.parent):
                pass

    def test_worktree_creation_uses_external_sibling(self):
        # Simulate creating from a commit older than the uncommitted policy.
        tools = self.root / "tools"
        tools.mkdir()
        for name in ("workspace.py", "workspace_storage.py"):
            shutil.copyfile(Path(storage.__file__).parent / name, tools / name)
        (self.root / "WORKSPACE_POLICY.md").write_text("Fixture worktree policy\n")
        args = argparse.Namespace(task="one-task", owner="test", base="HEAD", peak_gib=1)
        result = workspace.add_worktree(self.policy, args)
        target = Path(result["path"])
        self.assertEqual(target, self.root.parent / "repo-worktrees/one-task")
        self.assertEqual(storage.git(target, "branch", "--show-current"), "jeremybanka/one-task")
        self.assertTrue((target / "AGENTS.md").exists())
        self.assertTrue((target / "WORKSPACE_POLICY.md").exists())
        result = subprocess.run([sys.executable, str(target / "tools/workspace.py"), "--help"], cwd=target, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("worktree-add", result.stdout)
        args.task = "../build/bad"
        with self.assertRaisesRegex(storage.StorageError, "Task names"):
            workspace.add_worktree(self.policy, args)

    def test_installer_preserves_custom_code_and_is_idempotent(self):
        source = '''"""fixture"""
import argparse, subprocess
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    custom_branch_change = "preserve me"
    def run(command):
        subprocess.run(
            command, check=True)
if __name__ == "__main__":
    main()
'''
        path = self.root / "port/n64/build.py"
        path.parent.mkdir(parents=True)
        path.write_text(source)
        self.assertTrue(workspace.install_guard(self.root))
        self.assertFalse(workspace.install_guard(self.root))
        self.assertIn('custom_branch_change = "preserve me"', path.read_text())
        self.assertEqual(next((self.policy.state_dir / "guard-backups").glob("*.py")).read_text(), source)


if __name__ == "__main__":
    unittest.main()
