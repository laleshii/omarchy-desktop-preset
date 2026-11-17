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
Hyprland does not expose those paths, and GTK4 AT-SPI reports (0,0) origins on
this Wayland host. Neither titles, process argv nor list order proves a mapping.
For existing untracked windows, save a null URI plus a visible warning; support
explicit address-to-URI overrides at save and ID-to-URI editing afterward.
For our own sequential launches, one new Hyprland address plus one new GTK
object establishes a runtime correlation. Read the URI only for single-tab
windows; multiple tabs require an explicit active-location override. Verify
launch locations through that mapping when the optional PyGObject API exists.
This is partial automatic capture, not universal Nautilus session restoration.
