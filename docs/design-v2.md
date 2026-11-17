# Per-instance presets

The v1 pattern dictionary conflates equal-class windows. Its save fallback drops
the tree, and one final size per pattern also loses distinct ancestor split
ratios. PR #1 fixes foreign-workspace reuse and new-address detection; retain
that implementation and its regression tests for legacy files.

New saves use versioned JSON in the same `.preset` files. Each window has a
preset-local ID, exact class, argv, cwd, rectangle, floating flag, and optional
Nautilus URI. Tree leaves reference IDs; internal nodes record axis and ratio.
No compositor address or PID is a persistent identity in the preset. Existing
files remain readable without conversion. Explicit `save --force` backs up and
recaptures the current workspace; missing historical geometry cannot be recovered.

The v2 loader serializes compositor orchestration with a session lock. It keeps
a session-scoped, preset/workspace-specific ID-to-address journal, validates
process identity and workspace before reuse, and consumes each address once.
Without a valid journal, only uniquely identifiable workspace-local candidates
may be reused. Ambiguous occupied workspaces fail before launching or moving.
Each launch snapshots addresses and waits for one new matching address; a
timeout is journaled and blocks blind retries within that compositor session.
No rules, watchers, routing, or global layout options are installed.

All selected tiled windows are staged before replay. Each insertion uses the
exact focus address and `preselect` direction. Require active-window splitting
and preserved split directions; do not change global policy. Set the new parent
ratio immediately with `splitratio <value> exact`, before subdividing either
child. Ratios come from gap midpoints and the monitor workarea. Validate rendered
rectangles after replay; constraints and unsupported settings produce failures.
Rectangles alone cannot distinguish geometrically equivalent trees (for example
an aligned 2x2 grid); infer a deterministic guillotine tree, without claiming
access to Hyprland's private internal tree.

Nautilus 51.1 exports `OpenWindowsWithLocations`, keyed by GTK object paths.
Read its typed `a{sas}` GVariant using optional PyGObject with finite call timeouts.
Validate the FileManager1 and Nautilus owners, owner PID, property shape, and
stable owner/inventories. Auto-capture only an existing exact session binding or
a complete singleton across all workspaces with matching owner PID. Do not use
list order, title, basename, process argv/cwd, size, or AT-SPI `(0,0)` origins to
associate objects. Multiple addresses for one object invalidate those bindings.
For sequential launches, one new address and one new GTK object establish a
session correlation; an existing owner changing invalidates it. Cold bootstrap
is accepted only after a positive D-Bus NameHasNoOwner response; a failed or
delayed snapshot is not proof of an empty inventory.

Prioritize explicit live-window overrides, then proven single-tab capture,
then a save-only interactive selection adapter. Focus only the specified window,
show ID/workspace/address, support local folder and text URI selection, and
restore the original focus. Cancel/no TTY/noninteractive save may retain null.
Multiple tabs require an explicit target; exported lists and action indices do
not guarantee the active URI. Persist explanatory provenance, never runtime
identifiers in a preset. See [mechanism research](nautilus-locations.md).

Load resolves every Nautilus location independently. Missing/invalid/inaccessible
local folders use dynamic Home; remote probes run without mount/authentication
in a child bounded to 2.5 seconds, with unavailable/unverified results using
Home. Keep the original preset bytes. Launch a separate `--new-window` per ID,
then replay the unchanged tree. A displayed-location mismatch may call `go-home`
only on the proven new GTK object, never on a guessed user window. Unavailable
D-Bus verification produces a warning instead of aborting the layout. Record
runtime Home fallback for idempotent reload and emit a nonblocking notification.
Other launch/layout errors retain nonzero status. Neither load nor login creates
an interactive selection adapter. No rules, daemon or persistent policy changes.

Command semantics were checked against the installed 0.56.2 implementation:
[DwindleAlgorithm.cpp](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/layout/algorithm/tiled/dwindle/DwindleAlgorithm.cpp).
Nautilus window/tab export semantics were checked against
[nautilus-application.c](https://github.com/GNOME/nautilus/blob/51.1/src/nautilus-application.c)
and [nautilus-window.c](https://github.com/GNOME/nautilus/blob/51.1/src/nautilus-window.c).
