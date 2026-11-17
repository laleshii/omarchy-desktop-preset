# Validation evidence

Status: **PARTIAL** for automatic Nautilus capture. Explicit per-instance URI
round-trip and duplicate-window Dwindle restoration were validated separately
from automatic capture of arbitrary already-open windows, which is unavailable.
No cold logout/reboot or production-workspace restore was performed.

## Deterministic suite

`python3 -m unittest discover -s tests -v`: **36 tests pass** (12 retained PR #1
regressions, 22 v2 tests, 2 installation/helper tests). These use fake apps,
stateful compositors, typed D-Bus snapshots and a disposable HOME. They are not
live-session evidence. The v2 fake compositor models insertion, removal,
per-node ratios and gap/border rendering rather than returning requested sizes.

Coverage includes five mixed duplicate windows on three workspaces, equal titles,
three distinct URIs, repeated identical URIs, nested non-equal ratios, inference
up to 10 leaves, exact ID allocation, new-address exclusion, old-title changes,
slow launch, timeout/retry fencing, foreign-workspace protection, float geometry,
geometry failure, missing URI/directory, dry-run, idempotence, correlated versus
untracked capture, multi-tab refusal, URI escaping, schema validation, backups,
location overrides and preservation of unrelated installation customizations.

Bash syntax, Python AST/compilation and `git diff --check` pass. ShellCheck and
Pyflakes are unavailable; no global dependencies were installed to run checks.

## Live host

Omarchy 4.5.0-3 / Hyprland 0.56.2 / Nautilus 51.1, Wayland, Dwindle, one monitor,
2560×1080 at scale 1, workarea reduced by a 30 px top reservation. Only confirmed
empty disposable workspaces 91–94 and private temporary test directories were
used. All original window addresses and workspace assignments were checked after
cleanup; application/VPN settings were not changed.

The initial six-window workspace contained three Nautilus and three Ghostty
windows. Two Nautilus directories had identical basenames/titles; a third used
Unicode, spaces and shell punctuation. Sequential new-address/new-GTK-object
correlation verified each actual folder before save. Explicit save overrides
attached those known URIs to their corresponding window geometry. The legacy
installed save reproduced the missing-tree fallback for duplicate classes.

A nested layout with both split directions and ratios 0.39, 0.58, 0.55, 0.43 and
0.63 was arranged, saved, and only its test windows closed. The checkout CLI then
restored the preset on each of 91–93:

| Workspace | Windows | Nautilus URIs verified | Max rectangle deviation |
|---|---:|---:|---:|
| 91 | 6 | 3/3 | 3 logical px |
| 92 | 6 | 3/3 | 3 logical px |
| 93 | 6 | 3/3 | 3 logical px |

All 18 addresses were distinct. A second load per workspace reused the exact
addresses without adding windows. A real failure during initial testing exposed
GLib/pathlib differences in escaping `$()`; semantic local-URI comparison fixed
that case, which then passed the full three-workspace run.

Installed-copy validation is recorded below after deployment.

## Capture boundary and untested conditions

Nautilus `OpenWindowsWithLocations` is indexed by GTK object path, not compositor
address. GTK4 AT-SPI reported `(0,0)` window origins; duplicate sizes/titles do not
prove correlation. Arbitrary existing windows therefore need explicit overrides.
No claim of universal automatic capture, active-tab detection, or private-tree
introspection is made. Exact hidden topology is indeterminate when several trees
produce identical rectangles. Remote/GVfs locations, changed monitor settings,
first-ever Nautilus bootstrap, ten-window live layouts, and min/max-constrained
apps were not live tested. Min/max geometry failures are covered by mocks.
