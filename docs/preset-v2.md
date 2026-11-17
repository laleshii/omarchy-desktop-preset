# Version 2 file format

A `.preset` is a UTF-8 JSON object. JSON comments and executable shell syntax are
not supported. This minimal example records two tiled Nautilus instances with
independent locations and one floating terminal:

```json
{
  "version": 2,
  "workarea": [0, 30, 2560, 1050],
  "windows": [
    {
      "id": "w1",
      "class": "org.gnome.Nautilus",
      "title_hint": "Example one",
      "argv": ["nautilus", "--new-window"],
      "cwd": null,
      "floating": false,
      "rect": [6, 36, 1014, 1038],
      "uri": "file:///example/one",
      "location_source": "explicit"
    },
    {
      "id": "w2",
      "class": "org.gnome.Nautilus",
      "title_hint": "Example two",
      "argv": ["nautilus", "--new-window"],
      "cwd": null,
      "floating": false,
      "rect": [1028, 36, 1526, 1038],
      "uri": "file:///example/two",
      "location_source": "explicit"
    },
    {
      "id": "w3",
      "class": "com.mitchellh.ghostty",
      "title_hint": "Terminal",
      "argv": ["ghostty"],
      "cwd": null,
      "floating": true,
      "rect": [200, 150, 640, 400]
    }
  ],
  "tree": {
    "axis": "x",
    "ratio": 0.4,
    "first": {"id": "w1"},
    "second": {"id": "w2"}
  }
}
```

The example paths are synthetic; inaccessible locations will use Home on load.
`workarea` and `rect` are `[x, y, width, height]` in logical pixels. Workarea
excludes monitor reservations, while each rectangle is the rendered client
rectangle reported by Hyprland. `floating` is explicit, not inferred from class.

`id` is unique within the file and consists of letters, digits, `_` or `-`.
It must stay unchanged when editing location or launch metadata. Every tiled ID
must appear in the tree exactly once; floating IDs must not appear there.
`tree` is null for a floating-only preset, a single `{"id":"w1"}` for one tiled
window, or a recursive split. `axis: "x"` means left/right; `"y"` means top/bottom.
`first` precedes `second` on that axis. `ratio` is the first child's fraction of
the parent's cell, between 0.05 and 0.95, including gap/border midpoints.

`class` is an exact current/initial class match. `title_hint` is optional and may
help disambiguate workspace-local candidates; it never serves as a persistent
window identity. `argv` is an array passed directly to the process launcher;
null means capture could not determine a command. `cwd` is an absolute path or
null. A cold load requires usable argv for every non-Nautilus instance.

For Nautilus, `uri` supplies the launch location and `argv` is replaced with
`["nautilus", "--new-window", uri]`. `uri: null` means no folder was recorded;
load opens a separate window in the current user's Home without changing the
file. Invalid/unavailable locations use the same nonfatal fallback.
`location_source` is explanatory: `explicit`, `singleton-dbus`, `correlated-dbus`,
or `unavailable`. Optional `location_confidence` is `user-confirmed`, `proven`, or
`unknown`. Old v2 files need neither field and are not automatically migrated.
Unknown/unavailable data is never inferred from another window of the same class.
The `location set` helper changes one URI while preserving IDs, geometry, launch
metadata and unrelated autostart assignments.

The session journal is stored separately under the user's private runtime
directory. It contains temporary addresses, process-lifetime fingerprints,
allocation/pending records, explicit live-window overrides, effective Home
fallbacks and optional D-Bus window correlations. Fingerprints include the
compositor stable ID when available, preventing same-process address reuse.
The journal is not part of the saved format, is not portable to another compositor
session, and
should not be published with presets.
