#!/usr/bin/env python3
"""Exercise the real CLI with a stateful fake compositor; no desktop needed.

Run: python3 -m unittest discover -s tests -v
Set DESKTOP_PRESET_TEST_BIN to test another revision of the CLI.
"""

import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


NAUTILUS = "org.gnome.Nautilus"
GHOSTTY = "com.mitchellh.ghostty"
ROOT = Path(__file__).resolve().parents[1]
CLI = Path(os.environ.get("DESKTOP_PRESET_TEST_BIN", ROOT / "bin/desktop_preset"))


def client(address, workspace, cls, title="Window"):
    return dict(address=address, workspace={"id": workspace}, **{
        "class": cls, "title": title, "at": [0, 0], "size": [800, 600],
        "floating": False, "pid": 0,
    })


def fake_command(name, args):
    """Serialize the CLI's background launches and compositor queries."""
    path = Path(os.environ["FAKE_STATE"])
    with path.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text())
        output = ""
        if name == "hyprctl":
            if args == ["clients", "-j"]:
                for pending in state["pending"][:]:
                    pending["polls"] -= 1
                    if pending["polls"] == 0:
                        state["clients"].append(pending["client"])
                        state["pending"].remove(pending)
                output = json.dumps(state["clients"])
            elif args == ["activeworkspace", "-j"]:
                output = json.dumps({"id": state["active"]})
            elif len(args) == 2 and args[0] == "dispatch":
                dispatch = args[1]
                state["dispatches"].append(dispatch)
                ws = re.search(r'workspace = "([^"]+)"', dispatch)
                addr = re.search(r'window = "address:([^"]+)"', dispatch)
                window = next((c for c in state["clients"]
                               if addr and c["address"] == addr[1]), None)
                if dispatch.startswith("hl.dsp.focus"):
                    if ws:
                        state["active"] = int(ws[1])
                    elif window:
                        state["active"] = window["workspace"]["id"]
                elif dispatch.startswith("hl.dsp.window.move") and ws:
                    assert window, dispatch
                    window["workspace"]["id"] = (
                        -99 if ws[1].startswith("special:") else int(ws[1]))
                    if "follow = false" not in dispatch:
                        state["active"] = window["workspace"]["id"]
                elif dispatch.startswith("hl.dsp.window.close"):
                    state["clients"].remove(window)
                elif dispatch.startswith("hl.dsp.window.float"):
                    window["floating"] = True
                output = "ok"
            else:
                raise AssertionError(args)
        else:
            if name == "uwsm-app":
                assert args[0] == "--", args
                name, *args = args[1:]
                name = Path(name).name
            state["launches"].append([name, *args])
            if name != "no-window":
                cls = NAUTILUS if name == "nautilus" else GHOSTTY
                existing = next((c for c in state["clients"]
                                 if c["class"] == cls), None)
                if name == "nautilus" and existing and not (
                        "--new-window" in args or "-w" in args):
                    state["active"] = existing["workspace"]["id"]
                else:
                    if name == "late-title":
                        existing["title"] = "Ready"
                    address = f"0x{state['next_id']:x}"
                    state["next_id"] += 1
                    window = client(address, state.get("launch_workspace") or
                                    state["active"], cls,
                                    "Ready" if name == "late-title" else "Window")
                    state["pending"].append({"polls": 2, "client": window})
        path.write_text(json.dumps(state))
        print(output)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.presets = self.home / "presets"
        self.presets.mkdir()
        for name in ("hyprctl", "nautilus", "ghostty", "no-window",
                     "late-title", "uwsm-app"):
            (self.bin / name).symlink_to(Path(__file__).resolve())
        self.state_path = self.home / "state.json"
        self.state_path.write_text(json.dumps(dict(
            clients=[], pending=[], launches=[], dispatches=[], active=1,
            next_id=256)))
        self.env = dict(os.environ, HOME=str(self.home),
                        DESKTOP_PRESET_DIR=str(self.presets),
                        DESKTOP_PRESET_TIMEOUT="1", FAKE_STATE=str(self.state_path),
                        PATH=f"{self.bin}:{os.environ['PATH']}")

    def state(self):
        return json.loads(self.state_path.read_text())

    def update(self, **changes):
        state = self.state()
        state.update(changes)
        self.state_path.write_text(json.dumps(state))

    def preset(self, text, name="test"):
        (self.presets / f"{name}.preset").write_text(text)

    def cli(self, *args, success=True):
        result = subprocess.run(["bash", str(CLI), *args], env=self.env,
                                text=True, capture_output=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_autostart_three_workspaces_and_repeat(self):
        self.preset(f"{NAUTILUS} | uwsm-app -- nautilus\n"
                    f"{GHOSTTY} | ghostty\n"
                    f"@anchor {NAUTILUS}\n@split {NAUTILUS} r {GHOSTTY}\n"
                    f"@size {NAUTILUS} 500 600\n")
        (self.presets / "autostart.conf").write_text("1=test\n2=test\n3=test\n")
        self.cli("autostart", "run")
        state = self.state()
        self.assertEqual(len({c["address"] for c in state["clients"]}), 6)
        for ws in (1, 2, 3):
            self.assertCountEqual([c["class"] for c in state["clients"]
                                   if c["workspace"]["id"] == ws], [NAUTILUS, GHOSTTY])
        self.cli("autostart", "run")
        self.assertEqual(self.state(), state, "occupied workspaces must be skipped")

    def test_reuse_target_before_other_workspace(self):
        self.update(clients=[client("0x1", 9, GHOSTTY), client("0x2", 2, GHOSTTY)])
        self.preset(f"{GHOSTTY} | ghostty\n")
        self.cli("load", "test", "-w", "2")
        state = self.state()
        self.assertEqual(state["launches"], [])
        self.assertEqual([c["workspace"]["id"] for c in state["clients"]], [9, 2])
        self.assertFalse(any('address:0x1"' in d for d in state["dispatches"]))

    def test_autostart_two_workspaces_in_fallback_order(self):
        self.preset(f"{NAUTILUS} | uwsm-app -- /usr/bin/nautilus\n"
                    f"{GHOSTTY} | ghostty\n")
        (self.presets / "autostart.conf").write_text("1=test\n2=test\n")
        self.cli("autostart", "run")
        clients = self.state()["clients"]
        self.assertEqual(len({c["address"] for c in clients}), 4)
        self.assertEqual([c["workspace"]["id"] for c in clients], [1, 1, 2, 2])

    def test_launch_when_only_other_workspace_matches(self):
        self.update(clients=[client("0x1", 9, GHOSTTY)], launch_workspace=8)
        self.preset(f"{GHOSTTY} | ghostty\n")
        self.cli("load", "test", "-w", "2")
        state = self.state()
        self.assertEqual(len(state["launches"]), 1)
        self.assertEqual([c["workspace"]["id"] for c in state["clients"]], [9, 2])
        self.assertEqual(state["pending"], [])

    def test_wait_excludes_addresses_before_launch(self):
        self.update(clients=[client("0x1", 9, GHOSTTY, "Starting")])
        self.preset("Ready | late-title\n")
        self.cli("load", "test", "-w", "2")
        state = self.state()
        self.assertEqual(len(state["clients"]), 2)
        self.assertEqual(state["clients"][0]["workspace"]["id"], 9)
        self.assertEqual(state["clients"][1]["workspace"]["id"], 2)

    def test_timeout_does_not_move_foreign_window(self):
        self.update(clients=[client("0x1", 9, GHOSTTY)])
        self.preset(f"{GHOSTTY} | no-window\n")
        result = self.cli("load", "test", "-w", "2", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stdout + result.stderr)
        self.assertEqual(self.state()["clients"][0]["workspace"]["id"], 9)
        self.assertEqual(self.state()["launches"], [["no-window"]])

    def test_failed_duplicate_is_not_launched_again(self):
        self.preset(f"{GHOSTTY} | no-window\n{GHOSTTY} | no-window\n")
        result = self.cli("load", "test", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["launches"], [["no-window"]])

    def test_autostart_keeps_failure_from_earlier_workspace(self):
        self.preset(f"{GHOSTTY} | no-window\n", "fail")
        self.preset(f"{GHOSTTY} | ghostty\n")
        (self.presets / "autostart.conf").write_text("1=fail\n2=test\n")
        result = self.cli("autostart", "run", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stdout + result.stderr)
        self.assertEqual(len(self.state()["clients"]), 1)
        self.assertEqual(self.state()["clients"][0]["workspace"]["id"], 2)

    def test_tree_size_and_float_use_selected_addresses(self):
        self.update(clients=[client("0x1", 9, GHOSTTY), client("0x2", 2, GHOSTTY),
                             client("0x3", 9, "float-app"),
                             client("0x4", 2, "float-app")])
        self.preset(f"{GHOSTTY} | ghostty\n{NAUTILUS} | nautilus --new-window\n"
                    "float-app | no-window\n"
                    f"@anchor {GHOSTTY}\n@split {GHOSTTY} r {NAUTILUS}\n"
                    f"@size {GHOSTTY} 500 600\n@float float-app 20 30 400 300\n")
        self.cli("load", "test", "-w", "2")
        dispatches = self.state()["dispatches"]
        self.assertFalse(any('address:0x1"' in d or 'address:0x3"' in d
                             for d in dispatches))
        self.assertEqual(sum("window.resize" in d and "address:0x2" in d
                             for d in dispatches), 2)
        self.assertTrue(any("window.float" in d and "address:0x4" in d
                            for d in dispatches))
        self.assertTrue(any('preselect r' in d for d in dispatches))

    def test_clear_is_limited_to_target_workspace(self):
        self.update(clients=[client("0x1", 9, GHOSTTY), client("0x2", 2, GHOSTTY)])
        self.preset(f"{GHOSTTY} | ghostty\n")
        self.cli("load", "test", "-w", "2", "--clear", "-y")
        state = self.state()
        self.assertEqual([c["workspace"]["id"] for c in state["clients"]], [9, 2])
        self.assertFalse(any('address:0x1"' in d for d in state["dispatches"]))

    def test_dry_run_has_no_launches_or_dispatches(self):
        self.update(clients=[client("0x1", 9, GHOSTTY), client("0x2", 2, GHOSTTY)])
        self.preset(f"{GHOSTTY} | ghostty\n{NAUTILUS} | nautilus\n"
                    f"@anchor {GHOSTTY}\n@split {GHOSTTY} r {NAUTILUS}\n"
                    f"@size {GHOSTTY} 500 600\n@close-terminal\n")
        state = self.state()
        self.cli("load", "test", "-w", "2", "--clear", "-y", "--dry-run")
        (self.presets / "autostart.conf").write_text("3=test\n")
        self.cli("autostart", "run", "--dry-run", success=False)
        self.assertEqual(self.state(), state)

    def test_nautilus_simple_and_custom_commands(self):
        commands = [("nautilus", ["nautilus", "--new-window"]),
                    ("uwsm-app -- /usr/bin/nautilus", ["nautilus", "--new-window"]),
                    ('nautilus --new-window "file:///tmp/a b"',
                     ["nautilus", "--new-window", "file:///tmp/a b"]),
                    ("nautilus -w", ["nautilus", "-w"])]
        for cmd, expected in commands:
            with self.subTest(cmd=cmd):
                self.update(clients=[client("0x1", 9, NAUTILUS)], launches=[],
                            pending=[], dispatches=[])
                self.preset(f"{NAUTILUS} | {cmd}\n")
                self.cli("load", "test", "-w", "2")
                self.assertEqual(self.state()["launches"], [expected])
        # A shell command with arguments is left intact: the user must opt
        # into new-window behavior themselves, rather than risk a rewrite.
        self.update(clients=[client("0x1", 9, NAUTILUS)], launches=[], pending=[])
        self.preset(f"{NAUTILUS} | nautilus 'file:///tmp/a b'\n")
        result = self.cli("load", "test", "-w", "2", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stdout + result.stderr)
        self.assertEqual(self.state()["launches"], [["nautilus", "file:///tmp/a b"]])
        self.assertEqual(self.state()["clients"][0]["workspace"]["id"], 9)


if __name__ == "__main__":
    name = Path(sys.argv[0]).name
    if name in ("hyprctl", "nautilus", "ghostty", "no-window", "late-title", "uwsm-app"):
        fake_command(name, sys.argv[1:])
    else:
        unittest.main()
