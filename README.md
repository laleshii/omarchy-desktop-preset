# desktop_preset

Save a manually chosen startup workspace arrangement and restore its individual
windows at login, or with `desktop_preset load`. Built for Omarchy and Hyprland
Dwindle. No permanent window rules, class routing, daemon, or automatic resaving.
Later application launches behave normally on any workspace.

```sh
desktop_preset save work
desktop_preset load work -w 3
desktop_preset autostart set work -w 3
```

New snapshots use **version 2**: separate IDs for every window, including identical
classes and titles; a split tree with a ratio at each node; per-window floating
geometry; argv arrays and optional Nautilus locations. See the [v2 format reference](docs/preset-v2.md) for an editable example.
Existing text presets still load through the legacy reader, including the cross-workspace fix in
[PR #1](https://github.com/laleshii/omarchy-desktop-preset/pull/1).

**Nautilus capture is conservative.** Save prefers explicit locations, proven
D-Bus capture, then a separate interactive choice for each unresolved window.
Unknown locations remain `null` with a warning. Load opens an independent Home
window for every missing/invalid/unavailable Nautilus location and continues the
whole layout, including at login. No folder is guessed from a title or process
cwd. See [Nautilus locations](#nautilus-locations).

## Install and update

Requirements: Omarchy 4+, Hyprland 0.56+ with Lua dispatches, Bash, jq, Python 3.
Optional **PyGObject** (`python-gobject` on Arch) enables typed Nautilus D-Bus
correlation, displayed-location verification and bounded remote availability checks.
Optional zenity/yad provide folder dialogs; the existing Omarchy input menu or a
TTY supplies a path/URI prompt. No GUI packages are required or installed. No Python packages are installed
by this project. Tested on Omarchy 4.5.0-3, Hyprland 0.56.2 and Nautilus 51.1.

Run the installer **from your chosen checkout**:

```sh
cd /path/to/your/omarchy-desktop-preset
./install.sh
```

It copies `bin/*` scripts to `~/.local/bin`, adds **Trigger → Preset** in the
Omarchy menu, and adds one `o.launch_on_start("desktop-preset-autostart")` hook to
`~/.config/hypr/autostart.lua`. Reinstallation overwrites only project scripts;
it preserves presets, autostart assignments and unrelated menu/config entries.
An overwrite install avoids an unnecessary uninstall/reinstall gap.

Develop and update in the same fork checkout. Check the current branch and its
tracking remote before pulling; keep your patched feature branch selected until
it has been merged:

```sh
git status --short --branch
git remote -v
git pull --ff-only origin <your-patched-branch>
./install.sh
```

Do not switch to an unpatched upstream branch to perform a local update. See
[local deployment and rollback](docs/local-deployment.md).

## Commands and menus

```sh
desktop_preset list [--names]
desktop_preset show work
desktop_preset edit work                   # $EDITOR, default nano
desktop_preset inspect [-w 3]              # live addresses and verified known URIs
desktop_preset save work [-w 3]
desktop_preset save work --force --interactive # backup, then per-window recapture
desktop_preset save work --non-interactive  # never prompt; unknown URI stays null
desktop_preset validate work               # URI coverage and current fallback policy
desktop_preset load work [-w 3]
desktop_preset load work --dry-run
desktop_preset clear [-w 3]                # asks before closing windows
desktop_preset load work --clear          # asks before closing target windows
```

Preset names use letters, digits, `_` and `-`. Files stay in
`${XDG_CONFIG_HOME:-$HOME/.config}/desktop_preset/<name>.preset` (or
`DESKTOP_PRESET_DIR`). The menu keeps Load, Save, Clear and Autostart actions.
V2 leaves the invoking terminal open; use the menu or a different workspace if
that terminal should not be part of the saved arrangement.

`--dry-run` launches, closes and moves no windows, and writes no preset or
allocation journal. It describes the intended operations; it does not prove the
apps can launch or the geometry can be realized.

## Nautilus locations

Saving follows this order for **each window independently**:

1. `--location ADDRESS URI`, or a fingerprint-checked explicit session assignment.
2. Proven `OpenWindowsWithLocations` capture: an existing exact runtime binding,
   or a stable complete singleton inventory with matching D-Bus owner/PID.
3. An interactive folder/URI choice, with the exact window focused and its ID,
   workspace and address displayed. Multiple tabs require a choice; no first-tab
   assumption is made. Known tab candidates are offered only for a proven binding.
4. Cancel, no TTY, or `--non-interactive`: save `null` and warn. Load uses Home.

The Save menu explicitly enables interaction. Terminal saves prompt when stdin
is a TTY; `--interactive` also allows an available graphical dialog without one.
Without a display and TTY, even `--interactive` keeps unknown locations as null.
Zenity/yad offer a local folder picker or text URI entry. Omarchy's existing
input menu accepts either a path or remote URI. No dialog is used by load or login.

```sh
desktop_preset save files -w 3 --interactive
desktop_preset validate files
# Reopen the desired folders, then explicitly replace the capture with a backup:
desktop_preset save files -w 3 --force --interactive
```

For a scripted override, use current addresses from `inspect`:

```sh
desktop_preset inspect -w 3
desktop_preset save files -w 3 \
  --location 0x123 '/tmp/example/one' \
  --location 0x456 'file:///tmp/example/two'
desktop_preset location set files w1 '/tmp/example/one'
desktop_preset location set files w3 'sftp://server.example/share/folder'
```

Every saved instance keeps an independent ID, even for the same folder twice.
`location set` backs up and atomically replaces one URI while retaining IDs and
the tree. Explicit assignments take precedence over automatic capture and are
remembered for that live window's lifetime in the private session journal.
New overrides replace them. A later session must recapture its own locations.

The [Nautilus extension](https://sources.debian.org/src/nautilus/51.0.1-3/data/freedesktop-dbus-interfaces.xml)
exports a typed `a{sas}` mapping of GTK object paths to **all tab URIs**. Its
`OpenLocations` aggregate cannot associate windows. Hyprland addresses and GTK
IDs occupy different namespaces. AT-SPI on the tested GTK4/Wayland host reports
window origins `(0,0)` and buildable IDs, not the GTK application-window IDs.
Foreign-toplevel mappings identify the compositor side only. Title/basename,
PID alone, size, list order and tab order are never used to guess a binding.
See the [mechanism comparison and capture boundaries](docs/nautilus-locations.md).

A complete stable singleton can be captured even if opened outside the loader.
This case is unit tested; it could not be isolated live without closing existing
user windows. Several arbitrary pre-existing windows remain ambiguous on this
host and receive independent manual choices. Sequential loader launches correlate
one new address with one new GTK object, verify the URI, and journal that binding.
A D-Bus owner/process change, duplicate object assignment, incomplete inventory or
window churn disables capture. No daemon is needed. Multiple tabs are not restored;
select one target URI for that instance. `location_source` and
`location_confidence` record provenance without persisting compositor addresses.

Each new Nautilus instance uses direct argv `nautilus --new-window URI`, including
repeated identical folders. Whitespace, Unicode, percent encoding and shell
punctuation are data; no `eval` or shell launch is used. Quote shell arguments.
A historical `null` contains no recoverable folder address. The loader computes
the current user's Home dynamically; it never rewrites that historical file.

Missing/invalid local locations, non-directory paths and inaccessible directories
fall back to Home before launch. Remote/GVfs paths are queried without mounting
or authentication UI in an optional PyGObject child with a 2.5 second timeout.
Unavailable, timed-out or unverified remote resources also use Home; accessible
mounted resources retain their URI. No credentials are requested at login. A
late displayed-URI mismatch navigates only the proven newly created GTK window
Home. If D-Bus verification itself is unavailable, the argv request is reported
as unverified, and tree replay continues. A session Home fallback is remembered
for idempotent reload. Warnings and a nonblocking desktop notification identify
fallbacks; `validate NAME` reports current coverage and load targets.

Failures to start an application, an unresolved new-window timeout, ambiguous
occupied workspaces and geometry errors still return nonzero. Remote/GVfs and
real post-fix reboot were not live tested. Existing v1 files retain their legacy
reader; v2 files keep the same schema, names and autostart bindings.

## Identity, reuse and failure recovery

A v2 load maps `instance ID → exact live address` once. An address is consumed
once, and only workspace-local existing windows can be reused. Cold launches
snapshot all addresses and await a new exact-class window, excluding old windows
even if their titles change. The private journal is scoped to the compositor
session, preset contents and workspace and validates the process lifetime.
Concurrent v2 loads are serialized by a session lock.

A second manual load reuses valid journal assignments and restores their
geometry without launching duplicates. Without a journal, reuse must be
unambiguous in both directions. Indistinguishable occupied windows or unrelated
extra windows cause a preflight failure before launches or moves. Use an empty
workspace, or explicitly save the intended existing workspace to bind its
instances. The tool does not pull matching windows from another workspace.
Avoid creating unrelated windows in the target workspace while loading.

A timeout retains a pending-launch record. An automatic retry could otherwise
create a second window after a slow first launch. Inspect late windows, then
explicitly retry if appropriate:

```sh
desktop_preset load work --retry-pending
```

A window that closes or moves during replay causes failure; other workspaces'
windows are left alone. Selected staged windows are returned to the target on
failure. A failed replay can have changed the target layout; it is not an atomic
compositor transaction. The private runtime files are not presets and disappear
with the runtime session; no window addresses are reused across reboots.

## Dwindle geometry and limits

All tiled windows (up to 10) participate in tree inference by **instance ID**.
There is no duplicate-class fallback. Leaves record rendered rectangles and
internal nodes record axis, ordered children and a normalized first-child ratio.
Cuts are inferred at gap/border midpoints relative to the monitor workarea.
The loader stages the selected tiled windows, replays focus/preselect/insert,
and sets each new parent's ratio with `splitratio <value> exact` **before**
subdividing its children. Floating windows retain their own state and rectangles.
No global options or application constraints are changed.

The workspace must use Dwindle with `use_active_for_splits` enabled and either
`preserve_split` or `smart_split` enabled. Unsupported policy is reported instead
of changed. Fullscreen/grouped snapshots, Master, Scrolling and multi-monitor
workspace layouts are outside the supported scope.

On the same monitor, workarea and settings, verification requires every rendered
window position and size to differ by **at most 8 logical pixels**. The live
six-window nested test measured **3 px maximum**. Changed resolutions use the
saved normalized cuts; floating rectangles scale and stay inside the workarea.
Changed gaps, scale, borders or app min/max sizes can prevent the 8 px criterion;
the loader reports a geometry failure rather than claiming exact restoration.
It does not relax application constraints.

Rectangles cannot reveal a unique hidden compositor tree for geometrically
equivalent arrangements, such as a perfectly aligned 2×2 grid. In that case the
tool reconstructs a deterministic compatible guillotine tree with the same
rendered ordering and proportions. It does not claim to read Hyprland's private
tree. Other apps' launch argv/cwd are best-effort process or desktop-entry data;
a shared application process may not identify per-window launch arguments.
Terminal shell sessions, jobs, command history, open files, and browser tabs are
not restored. Review unusual application argv before relying on a cold login.

## Legacy files and explicit migration

Legacy pattern/command rows and `@anchor`, `@split`, `@size`, `@float`,
`@close-terminal` remain readable. Their shell launch commands remain trusted
executable configuration; only load legacy files you trust. V2 argv never uses
a shell. The previous workspace-local reuse/new-address fix remains intact.

Old duplicate-pattern files cannot recover window identities, folders or split
ratios that were never recorded. They produce an ambiguity warning; their legacy
behavior is retained, without an invented tree. Load/edit is never an implicit
migration. Arrange the actual windows, specify any missing Nautilus locations,
then explicitly `save NAME --force`. A timestamped `.preset.bak.*` retains the
old file. Preset names, menu selection and `autostart.conf` assignments stay the
same. Autostart only reads presets and skips occupied workspaces.

## Login autostart

```sh
desktop_preset autostart set work -w 3
desktop_preset autostart list
desktop_preset autostart unset -w 3
```

`autostart.conf` remains `<workspace>=<preset>`, one mapping per line. The single
login hook loads configured empty workspaces once. It neither overwrites presets
nor changes ordinary later launch behavior. Running it again skips occupied
workspaces. A failure is propagated even if later workspaces load successfully.

## Validation and removal

```sh
python3 -m unittest discover -s tests -v
for script in install.sh uninstall.sh bin/*; do
  if head -n1 "$script" | grep -q bash; then bash -n "$script"; fi
done
git diff --check
./uninstall.sh                 # keep presets and autostart assignments
```

Tests use stateful fake apps/compositors and a disposable HOME; see
[validation evidence](docs/validation-v2.md) for the separate live-host results.
ShellCheck and Ruff checks are also recorded there. Design decisions are in
[design-v2.md](docs/design-v2.md). MIT license: [LICENSE](LICENSE).
