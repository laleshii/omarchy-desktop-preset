# Nautilus location capture and safe load

The user reproduced a cold-login failure before this fix: v2 Nautilus instances
with `uri: null` stopped workspace restoration. Post-fix verification used empty
disposable workspaces and synthetic null presets, without a reboot or logout.

## Interfaces investigated

| Interface | What it proves | Boundary / decision |
|---|---|---|
| Nautilus `OpenWindowsWithLocations` | A GTK D-Bus window object owns these tab URIs | Typed `a{sas}` extension, not the standard FileManager1 methods. Does not identify a Hyprland address or active tab. Use as the URI source. |
| `OpenLocations` | The aggregate set of open folders | Cannot associate instances; never used for assignment. |
| Hyprland `clients -j` | Exact address, PID, workspace, rectangle and optional stable ID | No GTK application-window ID. PID filters a process but does not distinguish its windows. |
| Complete singleton | One stable GTK object and one mapped native Nautilus client, matching the D-Bus owner PID across the whole session | Two equal snapshots and equal full client inventories required. Works for a user-created window; disabled for multiple windows, owner changes or churn. Unit tested, not isolated live. |
| Sequential new-window journal | Exactly one new compositor address and one new GTK object after a serialized launch, with matching displayed URI | Reject multiple new candidates/objects and existing-owner changes. Bootstrap requires a positive NameHasNoOwner result; a failed snapshot is insufficient. Session/process/stable-ID checks fence reuse. Subsequent arbitrary navigation is recaptured for a single tab. |
| GTK4 AT-SPI | Accessible windows, state, buildable IDs and extents | Live origins were `(0,0)`; IDs are widget buildable IDs, not `gtk_application_window_get_id()`. Size/title coincidence is not identity. No automatic matching. |
| Wayland foreign-toplevel and Hyprland toplevel mapping | A foreign toplevel can be associated with a compositor address | Advertised live, but no Nautilus GTK D-Bus path. XDG export handles require cooperation from the surface owner; there is no read-only arbitrary GTK-ID lookup. No new dependency. |
| Portal / GTK window actions | Portal parent handles and window-specific actions | No common GTK-object/Hyprland identity or read-only active URI. `go-to-tab` has an index state, but the URI export has no active-tab or stable order contract. Never select the first tab implicitly. |
| Per-window interactive choice | The user explicitly assigns the target for the focused exact address | Primary override, accepts folder paths or remote URIs, cancellation allowed. Existing zenity/yad, Omarchy menu, or a TTY; no new GUI framework. |

On the validation host, the initial read-only D-Bus inventory contained four
single-tab Nautilus windows, and Hyprland contained four clients with one shared
PID. The property signature and exported action names were inspected without
publishing any window titles, paths, IDs or dumps. The accessibility bus and
Wayland registry were queried without changing desktop settings.

The [Nautilus interface declaration](https://sources.debian.org/src/nautilus/51.0.1-3/data/freedesktop-dbus-interfaces.xml)
and [export implementation](https://sources.debian.org/src/nautilus/51.0.1-3/src/nautilus-application.c)
show that keys derive from `gtk_application_window_get_id()` and values from
`nautilus_window_get_locations()`. The latter enumerates all slots; it does not
export active-tab identity. This is an extension beyond the
[standard FileManager1 methods](https://wiki.freedesktop.org/www/Specifications/file-manager-interface/).
The host's [Nautilus 51.1 source](https://github.com/GNOME/nautilus/blob/51.1/src/nautilus-window.c)
was also checked for window actions and tab enumeration. GTK's
[AT-SPI context](https://github.com/GNOME/gtk/blob/4.24.1/gtk/a11y/gtkatspicontext.c)
and [widget accessible IDs](https://github.com/GNOME/gtk/blob/4.24.1/gtk/gtkwidget.c)
explain the separate identifier namespace. The
[Hyprland mapping protocol](https://github.com/hyprwm/hyprland-protocols/blob/main/protocols/hyprland-toplevel-mapping-v1.xml)
only maps foreign toplevel handles to compositor addresses.

## Provenance and interaction

Priority: explicit override → proven auto-capture → independent interactive
selection → unknown `null` at save / dynamic Home at load.

`location_source` is `explicit`, `singleton-dbus`, `correlated-dbus` or
`unavailable`; `location_confidence` is `user-confirmed`, `proven` or `unknown`.
Metadata describes the capture method, not a statistical likelihood. Raw GTK
objects, owner names, addresses and process fingerprints stay in the private
runtime journal. Duplicate object bindings, process/stable-ID changes, changed
owners, malformed/empty/unavailable snapshots and unstable inventories disable
auto-assignment. There is no title/basename or list-order fallback.

Multi-tab windows require one explicit target URI. A proven binding permits
offering that window's tab URIs as numbered CLI choices. An ambiguous window is
offered no inferred candidates. Tab history and other tabs are outside scope.
Interactive invalid input reprompts that same window; cancel keeps null. Menu
save passes `--interactive`; a terminal defaults to interaction only with a TTY.
`--non-interactive` prevents prompts even with a graphical environment. Neither
load nor autostart invokes selection. An explicit live override remains primary
until replaced or its session/window fingerprint expires.

## Recovery policy

Nautilus null/invalid URI, a missing/inaccessible/non-directory local path, or an
unavailable remote path selects `Path.home().as_uri()` in memory, independently
for each saved ID. Remote checks never mount or authenticate, run in a child with
a 2.5 second hard limit, and use Home on timeout or missing optional PyGObject.
An accessible already-mounted remote directory retains its URI. No credentials,
GUI or TTY are requested by this policy. Actual remote/GVfs restoration is not
claimed as live verified.

Every new instance launches with direct argv `nautilus --new-window URI`. If a
proven newly created GTK object shows a different URI, `go-home` targets only
that object. A D-Bus outage means displayed URI verification is unavailable:
report that boundary and continue the geometry/tree restoration. Do not guess a
binding to hide the outage. Failures to create a window, other application
errors, ambiguous occupied workspaces and geometry errors still return nonzero.

Successful fallback loads print an ID-based summary and send a detached desktop
notification if available. A Home fallback is remembered for idempotent repeated
load during that session; a known already-associated live window can be reused
without replacing its current folder. `validate NAME` reports current coverage
and fallback targets without modifying a preset. Historical v1 files retain the
legacy reader. Historical v2 files, names and autostart assignments are preserved.
Only explicit backed-up atomic `save --force` or `location set` changes a preset.

To restore the desired folders rather than Home, reopen/arrange them and run
`desktop_preset save NAME --force --interactive`, or use `--location ADDRESS URI`
and `location set NAME ID URI`. A historical null cannot reveal a URI that was
never recorded; it cannot recover an old folder after that original window and
session data are gone.
