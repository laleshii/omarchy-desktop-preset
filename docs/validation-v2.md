# Validation evidence

Automatic Nautilus capture is **partial**: exact runtime bindings and complete
stable singletons can supply URIs. Arbitrary indistinguishable pre-existing
windows require independent explicit selection. No title/PID/list-order matching
is claimed. The user confirmed cold-login failures before this fix. A real
post-fix reboot/logout has **not** been performed.

## Deterministic suite

`python3 -m unittest discover -s tests -v`: **78 tests pass**. All 37 earlier
scenarios are retained; the old fatal-null/missing-directory expectations now
explicitly require successful Home fallback. The suite uses stateful fake
compositors/apps and disposable HOME/runtime directories, not a live compositor.

Coverage includes nested ratios up to ten leaves, 10 mixed windows on each of
three workspaces, identical titles and folders, per-ID URI association, exact
address exclusion/reuse, foreign-workspace protection, floating geometry,
geometry failures, pending timeout/retry fences, idempotence, URI null/invalid/
inaccessible fallback, preserved preset bytes, dynamic Home, remote probe
statuses/timeouts and argv escaping. Discovery tests exercise typed property
shape/signature, owner/PID changes, initial bootstrap, stable inventories,
singleton versus ambiguous multi-window capture, duplicate runtime bindings,
multiple tabs, explicit precedence, stable-ID address reuse and unavailable
PyGObject. GUI/CLI adapters cover local/remote choice, cancellation, invalid
input, no TTY/display and timeouts. Installation/helper tests cover atomic
failure cleanup, backups, legacy/v2 validation, autostart exit propagation and
preservation of unrelated customization.

Bash syntax, Python compilation, `git diff --check`, ShellCheck at error severity,
and Ruff `F,E9` pass. ShellCheck at warning severity reports the pre-existing
SC2206 in the legacy desktop-entry token parser; it is outside the new URI path. Lint tools ran through isolated `uvx` environments; no
runtime dependency was installed. A compositor-free GitHub Actions workflow runs
the unit, syntax and compile checks. Hosted CI status is separate from local PASS.

## Current live verification

Omarchy 4.5.0-3 / Hyprland 0.56.2 / Nautilus 51.1, GTK 4.24.1, Wayland/Dwindle.
Tests use two verified unused temporary workspaces and private synthetic folders.
Only test-created addresses are closed. Existing window/workspace assignments
are compared after cleanup. Private inventories, preset JSON and logs stay
outside the repository; only aggregate measurements are recorded here.

The checkout smoke test passed these cases:

| Case | Windows | URI result | Geometry / repeat |
|---|---:|---|---|
| Existing windows opened outside the loader | 4 Nautilus + 2 Ghostty | Four independent scripted CLI prompts; no ambiguous automatic assignment | One floating terminal retained |
| Save, close test windows, load | 6 | 4/4 Nautilus URIs verified, including two equal folders and two equal basenames with distinct URIs | Maximum rectangle delta 3 logical px; repeated load retains all addresses |
| Automatic recapture after proven loader correlation | 6 | 4/4 single-tab Nautilus URIs captured without overrides/input | IDs and per-window geometry retained |
| Synthetic historical v2 with all Nautilus URIs null, two workspaces | 12 total | 8/8 separate Nautilus windows verified at dynamic Home; exit 0, warning | Maximum delta 3 px; idempotent; preset bytes unchanged |
| Missing local directory | 6 | Missing instance verified at Home, other three Nautilus URIs retained; exit 0 | Maximum delta 3 px; floating state retained |

Maximum inferred per-node split-fraction drift was 0.003096. Geometry uses the
same monitor/workarea/settings; this is not a changed-monitor guarantee.
The interactive test drives the actual CLI adapter through a pseudo-TTY with
synthetic answers. It is not a claim that a person tested the graphical dialogs.
The chooser implementation is separately unit tested. Original user windows were
preserved and no test windows remained after cleanup.

Repeated installed-copy runs passed the same cases with 2–3 px maximum delta
(final run: 2 px and split-fraction drift 0.001562), then exercised **unattended `autostart run` with stdin=DEVNULL**: twelve windows
on two temporary workspaces, including eight distinct Nautilus Home instances,
exit 0, and repeated autostart skipping the occupied workspaces. Only a private
synthetic preset/autostart directory was used. The actual login-hook wrapper
also restored all twelve windows with stdin=DEVNULL, exit 0 and a nonblocking
diagnostic. No production mappings were run.

`./install.sh` ran from the existing fork checkout. All ten installed executables
matched source SHA-256. Existing preset, autostart, menu and Hyprland configuration
hashes were unchanged; exactly one login hook remained. The ordinary installed
CLI was checked without rewriting any user preset. Backup and rollback scripts
are private, outside tracked Git.

## Earlier branch evidence

Before the safe-fallback change, the branch had 37 passing mock/disposable-HOME
tests and an installed live run with three Nautilus plus three Ghostty on each
of three temporary workspaces: 18 distinct addresses, nine displayed URIs,
maximum rectangle deviation 3 px, ratio drift 0.00153, and idempotent reload.
Initial saves used explicit URI overrides. Another six-window case included
two equal directories and a floating terminal. That evidence verified the
Dwindle/per-instance algorithm, **not** successful restoration of null URI at
cold login. Its fatal missing-directory policy is superseded by this change.

## Limits / not run

A real post-fix reboot/logout, singleton capture isolated from existing user
windows, actual GUI clicks, remote/GVfs restoration, first-ever Nautilus process
bootstrap, changed monitor settings, ten-window live layouts and constrained
apps were not live tested. Their automated coverage, where present, is not live
evidence. Multi-tab active URI is not inferred. Rectangles can describe more
than one geometrically equivalent hidden tree; the inferred tree is compatible,
not Hyprland private-tree introspection. Application constraints may prevent the
8 px geometry tolerance and remain visible failures.
