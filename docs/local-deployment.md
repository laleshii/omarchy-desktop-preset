# Local fork deployment and rollback

The working fork checkout is the sole installation source. Before deployment,
back up `~/.config/desktop_preset/`, `~/.config/hypr/autostart.lua`,
`~/.config/omarchy/extensions/omarchy-menu.jsonc` and the installed project scripts
in `~/.local/bin/` to a private timestamped directory outside the repository.
Keep a hash inventory. Never commit these files: presets contain private paths.

Run `./install.sh` in the fork checkout, then compare each installed project
script with its `bin/` source. Check `desktop_preset --help`, `desktop_preset list`
and `desktop_preset autostart list`. Reinstallation is preferable to uninstalling
first: it replaces project scripts while preserving the existing menu, login
hook, presets and unrelated customizations. The installer adds missing entries
without duplicating the existing integration. No compositor rules are edited.

Keep development and updates on the patched branch in this same checkout:

```sh
git status --short --branch
git remote -v
git pull --ff-only origin <patched-branch>
./install.sh
```

Old presets remain legacy captures until explicitly resaved. After arranging an
actual workspace, use `desktop_preset save NAME --force --interactive` for
per-window selection, or supply `--location ADDRESS URI` for scripted overrides.
`desktop_preset validate NAME` reports missing locations and expected fallback.
Explicit recapture creates a backup and v2 snapshot without changing existing
`autostart.conf` mappings.

To remove the tool while preserving presets, run `./uninstall.sh` **without
`--purge`**. To restore a prior installation from a backup, copy its project
scripts back to `~/.local/bin/`, then restore its menu and autostart Lua files.
Do not overwrite later unrelated edits blindly: compare those files first.
Restore `~/.config/desktop_preset/` only if it actually changed and recovery is
needed; an ordinary install does not change it. Remove the new
`desktop-preset-v2` executable when rolling back to a version without that helper.
After restoring a changed Hyprland Lua file, run `hyprctl reload` and
`hyprctl configerrors`. No logout or reboot is necessary.
