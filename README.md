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
geometry; argv arrays and optional Nautilus locations. Existing text presets
still load through the legacy reader, including the cross-workspace fix in
[PR #1](https://github.com/laleshii/omarchy-desktop-preset/pull/1).

**Nautilus automatic capture is partial.** Arbitrary already-open Wayland windows
cannot currently be correlated reliably with Nautilus's GTK D-Bus window IDs.
Use explicit per-window locations when saving those windows. Missing locations
are saved as `null`, warned about (including from the Save menu), and refused on
cold load. The tool never guesses a folder from a title, process cwd, or argv.
See [Nautilus locations](#nautilus-locations).

## Install and update

Requirements: Omarchy 4+, Hyprland 0.56+ with Lua dispatches, Bash, jq, Python 3.
Optional **PyGObject** (`python-gobject` on Arch) enables typed Nautilus D-Bus
correlation and displayed-location verification. No Python packages are installed
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
desktop_preset save work --force           # backup, then explicit recapture
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

First inspect the workspace's individual addresses, then supply the actual
active folder for each window explicitly:

```sh
desktop_preset inspect -w 3
desktop_preset save files -w 3 \
  --location 0x123 '/absolute/path/with spaces' \
  --location 0x456 'file:///absolute/path/Unicode%20folder' \
  --location 0x789 '/another/folder'
```

The addresses above are examples: use current addresses from `inspect`. Each
saved row has an independent `w1`, `w2`, … ID, even for the same directory twice.
Addresses are never stored as reboot-persistent identities in the preset.
Alternatively, set a location **by saved ID** after inspecting `show`:

```sh
desktop_preset location set files w1 '/absolute/path/with spaces'
desktop_preset location set files w3 'sftp://server.example/share/folder'
```

This helper backs up the preset, updates only that instance's location, and
preserves the tree and IDs. Paths are normalized to URIs; URIs and argv are JSON
data, passed directly to `subprocess.Popen`, without shell interpolation. Quote
arguments in your shell. Whitespace, Unicode, percent encoding and punctuation
are supported. Each launch uses `nautilus --new-window URI`, including repeated
identical URIs. Home is represented by an explicit home URI, never by `null`.

With PyGObject and `OpenWindowsWithLocations`, a sequential launch correlates
**one new Hyprland address** with **one new Nautilus GTK object**. It waits for
that object's displayed URI to match the requested URI before assigning the
window to its slot. This correlation is session-local and invalidated by a D-Bus
owner or process change. Subsequent saves of these tracked **single-tab** windows
can capture their current URI automatically. Closing the tool does not require
a watcher; a private runtime journal records the correlation.

This does **not** provide automatic capture of arbitrary pre-existing windows.
The installed [Nautilus API](https://github.com/GNOME/nautilus/blob/51.1/src/nautilus-application.c)
exports GTK object paths and tab locations, without a Hyprland address. GTK4
AT-SPI on the tested Wayland host reports window origins `(0,0)`; equal sizes or
titles do not establish identity. The tool deliberately avoids such guesses.
Multi-tab windows require an explicit active-location override: the API's tab
list does not establish the active URI. Tab history and inactive tabs are not
restored.

Local folders must exist and be accessible before loading; missing disks or
folders cause a visible failure, without a home-directory fallback. Remote/GVfs
URIs may be specified explicitly and are passed unchanged as data. Credentials,
mounts and network access must already work; a slow/inaccessible location times
out instead of being marked restored. Remote capture/restore has **not** been
live validated. Without PyGObject, launches can pass a supplied URI but report
that the displayed location is unverified. With a working D-Bus API, missing or
mismatched location verification fails the load.

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
It does not relax application constraints (including AmneziaVPN constraints).

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
ShellCheck was unavailable on the validation host. Design decisions are in
[design-v2.md](docs/design-v2.md). MIT license: [LICENSE](LICENSE).
