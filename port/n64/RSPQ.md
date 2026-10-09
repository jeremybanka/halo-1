# Local command-queue configuration

The installed libdragon uses two 2 KiB CPU-to-RSP low-priority command buffers.
When they fill, `rspq_next_buffer()` waits for the RSP to finish the preceding
buffer. This time appears inside draw/HUD submission, separately from the
explicit frame-slot fence wait. The default two 16 KiB queues permit next-frame CPU work
to overlap pending graphics; it does not make the RSP process geometry faster.

Build comparable quiet measurements with:

```sh
python3 port/n64/build.py --benchmark --rspq-buffer-kib 2
python3 port/n64/build.py --benchmark --rspq-buffer-kib 16
```

The normal build now uses 16 KiB buffers and retains its documented ROM basename.
Explicit 2/4/8/32 KiB options add `-rspqNk`; `--rspq-buffer-kib 0` uses the
installed SDK unchanged and adds `-rspq-stock`. Stock mode requires no SDK source
checkout. The normal build fails clearly if matching source is unavailable; it
does not silently fall back to a smaller queue. The benchmark's QUEUE field
measures CPU time spent waiting inside low-priority queue-buffer switches.
It overlaps WORLD/OBJ/HUD timings; those inclusive times must not be added.
Frame intervals continue to include display acquisition, rendering and fences.

`prepare_rspq.py` requires the **matching libdragon source checkout**, supplied
with `--libdragon-source` or found beside the SDK as `libdragon-src`. It checks
three installed/source public headers, exact source patch sites and the expected
2 KiB baseline. It writes a generated CPU `rspq.c` override and SHA-256 provenance
under ignored `build/n64/rspq-override/`. No shared SDK file is modified or copied
into tracked source. The generated object links before `libdragon.a`, replacing
the archive's CPU queue object. RSP microcode, 64 KiB RDP buffers, high-priority
buffers, block lifetimes and all existing wait/signal/fence logic stay intact.
The two 16 KiB buffers require 28 KiB more RAM than the baseline.

`python3 port/n64/test_rspq_override.py` verifies that the two generated variants
differ only in the allocation size and retain the original synchronization and
block-lifetime functions. Target compilation and emulator/RDP validation remain required for changes to
the override or the installed SDK.

Quiet benchmarks now collect two independent 75-second samples after a one-second
warmup. The first result page measures CPU frame acquisition intervals. Pages
alternate every eight seconds; press A to switch sooner to RDP full-sync
completion intervals, grouped by the frame completing at that
callback. This wraps the same callback used by `rdpq_detach_show()` and calls
`display_show()` without an additional pipeline wait. Neither page measures the
VI scanout time. Callback samples use a fixed 20 KiB bank and no allocation,
logging or sorting inside the interrupt; sorting starts after the callback has
published its completed bank. `test_cadence.c` checks warmup, phase transitions,
publication, quantiles and the exact 33,333-microsecond budget boundary.

Two additional result pages show the eight longest completed-frame intervals,
four per page. Their metadata belongs to the completing frame: simulation time,
submitted vertices, triangle categories, and mounted/zoom/death player masks.
The masks use bits1/2/4/8 for players1/2/3/4. These are scene identifiers, not a
claim that one category caused the whole interval; CPU supply gaps and queued
work also affect completion cadence.

Tail collection adds a fixed eight-entry bank (388 bytes on the target) and
44 bytes of metadata per display buffer. Once full, an ordinary completion
performs one threshold comparison. A new top-eight interval moves at most seven
48-byte entries and copies one44-byte frame record; it performs no heap work,
formatting, sorting of the sample bank, floating-point work or waiting in the
interrupt. This small bounded instrumentation cost is included in measured
intervals rather than subtracted or assumed to be zero. The timestamp is taken
before the bookkeeping. `test_cadence_tail.c` checks ranking, metadata ownership,
warmup exclusion and final publication.
