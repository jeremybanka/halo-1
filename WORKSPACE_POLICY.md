# Worktree and storage policy

Source checkouts, temporary build products and retained artifacts have different
lifetimes. Keep them separate. This policy applies to people, agents and local
automation. Preserve source assets, useful editable asset-development stages and
source worktrees. ROMs are build output: retain them while actively shipping or
testing them, rather than making every tested build a permanent archive.
Retire older outputs after verifying the versioned source, asset inputs and
build recipe needed to rebuild them. Existing pins still require explicit
review; this policy does not silently authorize blanket deletion.

## Locations and ownership

The main checkout remains at its current location. Create additional checkouts
in its external sibling `<repository>-worktrees/<task>` directory. For this Mac,
that is `/Users/jem/dojo/halo-1-worktrees/<task>`. Use one task branch and one
writer per worktree. The creation command records the owner, purpose and base:

```sh
python3 tools/workspace.py worktree-add texture-budget --owner jem --base HEAD
```

New branches use `jeremybanka/<task>`. The command refuses nested destinations
and existing directories; it does not force branch checkout. Tool-managed
external worktrees may remain in their designated external locations. Never
place source checkouts in build, cache, temporary, asset or artifact directories.

Every checkout owns its ignored `build/` directory. Build without `--output-dir`
to use a fresh `build/runs/<run-id>` directory, or specify a fresh isolated path.
The shared asset bank remains a build input; the default no longer writes ROMs
into the legacy `build/n64` archive. Explicit outputs with existing ROMs or
manifests are refused. Do not overwrite active shipping/testing builds. Review
older build products separately from the editable assets and useful development
stages that may share their directories.

## Enforced storage limits

`workspace-policy.json` sets a **2 GiB free-space floor**, a **30 GiB warning**,
a **1 GiB default N64 build growth budget**, and **48 hours** before managed
intermediates become eligible for retention cleanup. These are local project
defaults. The default build budget includes the ROM, DFS, object and link files.

Jobs reserve their full peak growth estimate under a shared filesystem lock.
Admission requires free space for the safety floor, the new estimate and other
live reservations on the same filesystem. Concurrent worktrees cannot each
claim the same remaining space. Dead local reservations are ignored; foreign
host reservations are retained conservatively. The state lives in the main
checkout's ignored `.workspace/` directory, outside all cleanup roots.

All installed N64 build entry points use this guard. Other disk-heavy commands,
including downloads and archive extraction, must use the batch runner:

```sh
python3 tools/workspace.py status
python3 tools/workspace.py run --output build/import-new --peak-gib 10 -- \
  python3 path/to/import_script.py --output build/import-new
```

Estimate simultaneous download, expansion, staging, scratch and variant sizes,
not just the compressed download. Declare the directory the command writes.
Nested guarded builds within that directory share the parent batch reservation.
Their individual estimates must fit the parent budget.

The guard polls managed child processes at half-second intervals; filesystem
accounting can take additional time.
If free space crosses the floor or declared output growth exceeds the budget,
the guard stops **only its own newly launched process group** and records a
failed run. Partial outputs remain for diagnosis. Existing applications and
jobs are never signaled. Use this runner for noninteractive batch commands.
Batch commands must wait for their children and must not daemonize.

This is cooperative admission and monitoring, not an operating-system quota.
Unwrapped programs, other projects, another filesystem, or a single large write
between checks can consume space outside its control. Do not bypass a refusal;
reduce the estimate only when the actual workload has been reduced. POSIX file
locking is required by these local N64 tools; desktop platform CI is unchanged.

## Retention and accepted artifacts

After a successful N64 build, the guard verifies the ROM against its manifest,
records the packaged filesystem's checksum, then removes that newly generated
`frontend.dfs`. The ROM already contains that filesystem. `--keep-dfs` explicitly
retains it and holds the run's intermediates for repacking/debugging.

The latest successful managed build in each checkout is current. Pin any other
build, accepted baseline, reference result or asset directory that must remain:

```sh
python3 tools/workspace.py pin build/runs/EXAMPLE --reason 'Accepted hardware baseline'
python3 tools/workspace.py cleanup
python3 tools/workspace.py cleanup --apply
```

Cleanup defaults to a dry run. Only a successful managed N64 run older than
48 hours can contribute candidates. It must be inactive, noncurrent and unpinned,
and its ROM must still match its recorded checksum. The explicit allowlist is
the run's DFS, `objects/*.o`, and its ROM's `.elf`, `.stripped`, `.sym` and linker
`.map` siblings. Each candidate must still match its recorded identity and hash.
Baseline/release/reference-named output directories are also protected.

Eligible managed intermediates are cleaned automatically before admitting a new
job. Cleanup never adopts existing legacy outputs, deletes ROMs or reports,
removes directories or arbitrary state dumps, traverses symlinks, or treats an
asset extension as disposable. Every removal gets a receipt in `.workspace/`.
Pins require an existing path and a reason; no automatic expiration or unpinning
is provided. Failed/interrupted runs are retained for explicit review.

Keep original asset inputs and useful editable intermediate work in versioned
private asset history. This includes graphics, meshes, textures, rigs and
meaningful reduction/editing stages, with their recipes and provenance. It does
not mean object files, generated C, packaged filesystems, caches or old ROMs.
Check JSON and binary files by their role; an extension alone cannot distinguish
an editable asset from a generated artifact.

Retain ROM bytes only for active shipping/testing or an explicit current need.
Keep lightweight source/asset refs, toolchain details, commands, checksums and
useful findings as needed to explain past work. A historical ROM checksum that
differs because of embedded build paths does not itself justify retaining that
ROM indefinitely. Verify the underlying inputs and recipe, and distinguish
repeatable builds from exact reproduction of historical packaging.

The managed cleanup command currently excludes ROMs and legacy outputs; that is
a limitation of its conservative allowlist, not a requirement to hoard them.
Review and retire those outputs explicitly after preserving the asset work.

Before retiring a dirty
checkout, save its patch, required untracked files and private submodule changes.
Keep source/asset revisions reachable through durable Git references. Pinning
protects an artifact locally; it does not publish or back it up.

## Existing worktrees and migration

The currently registered nested worktrees are grandfathered and receive the
shared guard without moving their source or outputs. `status` reports their
locations. `install-guards` is idempotent and saves each predecessor build script
under `.workspace/guard-backups/` before making a small entry-point change.
Other branch-specific source edits remain intact. Fresh worktrees made from
older commits receive the same guard, policy document, agent guidance and policy
tools when these files are absent. Existing agent guidance is retained. Legacy
checkouts without the CLI use the main checkout's `tools/workspace.py --root
<owning-checkout>`; storage state and limits remain shared.
The small entry shim remains compatible with historical branches used on machines
where this policy was never installed. Once the shared policy file exists,
a missing guard module is an error, not permission to build unguarded.

`protect-existing` adds local pins for existing asset/archive paths, named
baselines/releases/references and each checkout's latest ROM output. It records
the current worktree inventory without modifying any artifact. Existing legacy
outputs remain excluded from managed retention whether or not they have a pin.

Migrate existing worktrees as a separate operation: pause writers, inventory
dirty/untracked/ignored files and submodule state, preserve assets and retained
artifacts, then verify Git metadata, links and hardcoded paths afterward. Migrate
the innermost reference checkout first. No automatic migration, removal, reset,
branch switch, force checkout or Git configuration change is part of this policy.

Use `git worktree remove` only after the owner has retired the work and all data
is saved; never force removal automatically. `git worktree prune` only removes
stale administrative records. Git does not support `worktree move` for worktrees
containing submodules, so these checkouts require a submodule-aware migration.
See the [Git worktree manual](https://git-scm.com/docs/git-worktree).
