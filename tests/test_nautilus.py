"""URI discovery/fallback regressions, entirely synthetic and compositor-free."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

import test_v2 as fixtures

v2, N = fixtures.v2, fixtures.N
node, preset, window = fixtures.node, fixtures.preset, fixtures.window


class NautilusTests(unittest.TestCase):
    setUp = fixtures.V2Tests.setUp
    write = fixtures.V2Tests.write

    def create(self, uri=None):
        self.h.popen(['nautilus', '--new-window', uri or self.uri])
        self.h.clients(); self.h.clients()
        self.h.move(self.h.windows[-1]['address'], 1)
        return self.h.windows[-1]

    def typed_snapshot(self):
        return dict(self.n.snapshot(), pid=0)

    def test_arbitrary_existing_singleton_uses_complete_owner_inventory(self):
        c = self.create()
        snapshot = self.typed_snapshot()
        with patch.object(self.n, 'snapshot', return_value=snapshot):
            data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n)
        w = data['windows'][0]
        self.assertEqual(w['uri'], self.uri)
        self.assertEqual(w['location_source'], 'singleton-dbus')
        self.assertEqual(w['location_confidence'], 'proven')
        self.assertEqual(self.rt.binding(c)['object'], next(iter(snapshot['windows'])))

    def test_singleton_requires_matching_owner_pid(self):
        self.create()
        snapshot = dict(self.n.snapshot(), pid=123)
        with patch.object(self.n, 'snapshot', return_value=snapshot):
            self.assertEqual(v2.capture_locations(self.h, self.rt, self.n)[0], {})

    def test_other_workspace_window_disables_singleton(self):
        self.create(); other = self.create()
        self.h.move(other['address'], 9)
        snapshot = self.typed_snapshot()
        with patch.object(self.n, 'snapshot', return_value=snapshot):
            data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n)
        self.assertIsNone(data['windows'][0]['uri'])
        self.assertEqual(other['workspace']['id'], 9)

    def test_same_title_different_uri_or_same_uri_never_guesses_order(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                if not self.h.windows:
                    self.create(); self.create()
                uris = [self.uri, self.uri if duplicate else 'file:///example/two']
                self.n.windows = dict(zip(reversed(list(self.n.windows)), [[u] for u in uris]))
                with patch.object(self.n, 'snapshot', return_value=self.typed_snapshot()):
                    bindings, _ = v2.capture_locations(self.h, self.rt, self.n)
                self.assertEqual(bindings, {})

    def test_snapshot_navigation_or_owner_churn_disables_capture(self):
        self.create()
        first = self.typed_snapshot()
        for second in (dict(first, owner=':1.2'), dict(first, windows={}),
                       dict(first, windows={'/window/changed': ['file:///example/two']})):
            with patch.object(self.n, 'snapshot', side_effect=[first, second]):
                self.assertEqual(v2.capture_locations(self.h, self.rt, self.n)[0], {})

    def test_client_churn_disables_capture(self):
        c = self.create()
        with patch.object(self.n, 'snapshot', return_value=self.typed_snapshot()), \
                patch.object(self.h, 'clients', side_effect=[[c], []]):
            self.assertEqual(v2.capture_locations(self.h, self.rt, self.n)[0], {})

    def test_duplicate_runtime_object_bindings_fail_closed(self):
        a, b = self.create(), self.create()
        for c in (a, b):
            self.rt.data['nautilus'][c['address']] = dict(owner=self.n.owner,
                object=next(iter(self.n.windows)), fingerprint=v2.fingerprint(c))
        self.assertEqual(v2.capture_locations(self.h, self.rt, self.n)[0], {})

    def test_singleton_multitab_requires_explicit_selection(self):
        c = self.create()
        self.n.windows[next(iter(self.n.windows))] = [self.uri, 'file:///example/two']
        picker = Mock()
        picker.choose.return_value = 'file:///example/two'
        with patch.object(self.n, 'snapshot', return_value=self.typed_snapshot()):
            data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n, picker)
        self.assertEqual(data['windows'][0]['uri'], 'file:///example/two')
        self.assertEqual(picker.choose.call_args.args[0]['address'], c['address'])
        self.assertEqual(picker.choose.call_args.args[2], [self.uri, 'file:///example/two'])
        self.assertEqual(data['windows'][0]['location_source'], 'explicit')

    def test_unknown_windows_prompt_independently_and_cancel_is_null(self):
        a, b = self.create(), self.create()
        picker = Mock()
        picker.choose.side_effect = [self.uri, None]
        data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n, picker)
        self.assertEqual(len({c.args[0]['address'] for c in picker.choose.call_args_list}), 2)
        self.assertEqual([w['uri'] for w in data['windows']], [self.uri, None])
        self.assertEqual([c.args[2] for c in picker.choose.call_args_list], [[], []])
        self.assertNotEqual(a['address'], b['address'])

    def test_explicit_override_precedes_auto_and_survives_recapture(self):
        c = self.create()
        uri = 'file:///example/manual'
        picker = Mock()
        with patch.object(self.n, 'snapshot', return_value=self.typed_snapshot()):
            data = v2.save(self.path, 1, False, {c['address']: uri}, self.h, self.rt, self.n, picker)
            again = v2.save(self.path, 1, True, {}, self.h, self.rt, self.n, picker)
        picker.choose.assert_not_called()
        self.assertEqual(data['windows'][0]['uri'], uri)
        self.assertEqual(again['windows'][0]['uri'], uri)
        self.assertEqual(len(list(self.root.glob('*.bak.*'))), 1)

    def test_stable_id_prevents_address_reuse_within_same_process(self):
        c = self.create()
        c['stableId'] = 'synthetic-first'
        self.rt.data.setdefault('explicit', {})[c['address']] = {
            'uri': self.uri, 'fingerprint': v2.fingerprint(c)}
        replacement = dict(c, stableId='synthetic-second')
        self.assertIsNone(v2.explicit_location(self.rt, replacement))

    def test_invalid_interactive_value_reprompts_only_same_window(self):
        c = self.create()
        picker = Mock()
        picker.choose.side_effect = ['relative', self.uri]
        data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n, picker)
        self.assertEqual(data['windows'][0]['uri'], self.uri)
        self.assertEqual([x.args[0]['address'] for x in picker.choose.call_args_list], [c['address']] * 2)

    def test_final_geometry_is_captured_after_picker_closes(self):
        self.create()
        picker = Mock()
        def choose(*args):
            self.h.windows[0]['floating'] = True
            self.h.windows[0]['at'] = [20, 30]
            self.h.windows[0]['size'] = [500, 400]
            return self.uri
        picker.choose.side_effect = choose
        data = v2.save(self.path, 1, False, {}, self.h, self.rt, self.n, picker)
        self.assertEqual(data['windows'][0]['rect'], [20, 30, 500, 400])
        self.assertTrue(data['windows'][0]['floating'])
        self.assertIsNone(data['tree'])

    def test_invalid_explicit_override_is_not_replaced_with_auto(self):
        c = self.create()
        with patch.object(self.n, 'snapshot', return_value=self.typed_snapshot()):
            with self.assertRaises(v2.PresetError):
                v2.save(self.path, 1, False, {c['address']: ''}, self.h, self.rt, self.n)
        self.assertFalse(self.path.exists())

    def test_ten_instances_null_three_workspaces_and_idempotence(self):
        tree = {'id': 'n0'}
        windows = [window('n0', N)]
        for i in range(1, 10):
            ident = f'n{i}'
            windows.append(window(ident, N) if i < 8 else window(ident))
            tree = node('x' if i % 2 else 'y', .52, tree, ident)
        self.write(preset(windows, tree))
        original = self.path.read_bytes()
        for ws in (1, 2, 3):
            self.engine.load(self.path, ws)
            before = self.h.clients()
            self.engine.load(self.path, ws)
            self.assertEqual(before, self.h.clients())
        self.assertEqual(len(self.h.launches), 30)
        self.assertEqual(sum(a[0][0] == 'nautilus' for a in self.h.launches), 24)
        self.assertTrue(all(a[0][-1] == Path.home().as_uri() for a in self.h.launches if a[0][0] == 'nautilus'))
        self.assertEqual(self.path.read_bytes(), original)

    def test_home_is_resolved_from_current_environment(self):
        home = self.root / 'new home'
        home.mkdir()
        with patch.dict(os.environ, HOME=str(home)):
            self.assertEqual(v2.effective_location(None), (home.as_uri(), 'missing URI'))

    def test_invalid_historical_uri_is_recoverable(self):
        for uri in ('relative', '', 'file://server/path', 'file:///tmp/%00', ['bad'], 'sftp://['):
            with self.subTest(uri=uri):
                data = preset([window('a', N, uri)], {'id': 'a'})
                v2.validate(data)
                self.assertEqual(v2.effective_location(uri)[0], Path.home().as_uri())

    def test_local_special_names_and_permissions(self):
        for name in ('space a', 'кириллица', 'literal%20', 'hash#', "quote';$(no)`x`"):
            directory = self.root / name
            directory.mkdir()
            self.assertEqual(v2.effective_location(str(directory)), (directory.as_uri(), None))
        with patch.object(v2.os, 'access', return_value=False):
            self.assertEqual(v2.effective_location(self.uri)[0], Path.home().as_uri())

    def test_remote_availability_policy_and_optional_gi(self):
        uri = 'sftp://server.example/share/a%20b'
        for status in ('available', 'unavailable', 'unverified', 'timeout'):
            probe = Mock(return_value=status)
            target, reason = v2.effective_location(uri, probe)
            self.assertEqual(target, uri if status == 'available' else Path.home().as_uri())
            self.assertEqual(reason is None, status == 'available')
            probe.assert_called_once_with(uri)

    def test_remote_probe_is_direct_argv_bounded_and_no_input(self):
        uri = 'smb://server.example/share/$(no);x'
        with patch.object(v2.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(v2.probe_remote(uri), 'available')
        self.assertEqual(run.call_args.args[0][-1], uri)
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertLessEqual(run.call_args.kwargs['timeout'], 3)
        with patch.object(v2.subprocess, 'run', side_effect=subprocess.TimeoutExpired('probe', 2)):
            self.assertEqual(v2.probe_remote(uri), 'timeout')

    def test_unavailable_api_does_not_abort_home_or_ghostty(self):
        self.n.bus = None
        self.write(preset([window('a', N), window('b')], node('x', .4, 'a', 'b')))
        with patch.object(self.n, 'snapshot', return_value={'owner': None, 'windows': {}}):
            self.engine.load(self.path, 1)
        self.assertEqual(len(self.h.clients()), 2)

    def test_api_delay_or_loss_does_not_abort_other_instances(self):
        self.write(preset([window('a', N), window('b')], node('x', .4, 'a', 'b')))
        with patch.object(self.n, 'snapshot', return_value={'owner': None, 'windows': {}}):
            self.engine.load(self.path, 1)
        self.assertEqual(len(self.h.clients()), 2)
        self.assertEqual(len(self.h.launches), 2)

    def test_other_application_failure_stays_fatal(self):
        self.write(preset([window('a', N), window('b')], node('x', .4, 'a', 'b')))
        original = self.h.popen
        def fail(argv, **kwargs):
            if argv[0] == 'ghostty':
                raise FileNotFoundError('synthetic missing executable')
            return original(argv, **kwargs)
        with patch.object(v2.subprocess, 'Popen', side_effect=fail):
            with self.assertRaisesRegex(v2.PresetError, 'launch failed'):
                self.engine.load(self.path, 1)

    def test_runtime_home_navigation_fallback_is_idempotent(self):
        self.write(preset([window('a', N, self.uri)], {'id': 'a'}))
        original = self.h.popen
        def wrong(argv, **kwargs):
            process = original(argv, **kwargs)
            self.n.windows[next(iter(self.n.windows))] = ['file:///example/wrong']
            return process
        with patch.object(v2.subprocess, 'Popen', side_effect=wrong):
            self.engine.load(self.path, 1)
        self.engine.load(self.path, 1)
        self.assertEqual(len(self.h.launches), 1)

    def test_atomic_failure_keeps_original_and_removes_temporary_file(self):
        self.path.write_text('original')
        with patch.object(v2.os, 'replace', side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):
                v2.atomic_json(self.path, {'example': 1})
        self.assertEqual(self.path.read_text(), 'original')
        self.assertEqual(list(self.root.glob('.test.preset*')), [])

    def test_disabled_picker_never_focuses_or_reads_input(self):
        picker = v2.LocationPicker(self.h, False)
        with patch('builtins.input', side_effect=AssertionError('unexpected input')):
            self.assertIsNone(picker.choose({}, 'w1', []))
        self.assertEqual(self.h.dispatches, [])

    def test_no_display_or_tty_never_prompts_even_if_requested(self):
        with patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
                patch.object(v2.sys.stdin, 'isatty', return_value=False), \
                patch('builtins.input', side_effect=AssertionError('unexpected input')):
            self.assertIsNone(v2.LocationPicker(self.h, True).choose({}, 'w1', []))
        self.assertEqual(self.h.dispatches, [])

    def test_cli_picker_identifies_exact_window_and_selects_tab(self):
        c = self.create()
        with patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
                patch.object(v2.sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value='2'):
            uri = v2.LocationPicker(self.h).choose(c, 'w1', [self.uri, 'file:///example/two'])
        self.assertEqual(uri, 'file:///example/two')
        self.assertEqual(self.h.focused, c['address'])

    def test_gui_local_remote_and_cancel_adapter(self):
        c = self.create()
        with patch.dict(os.environ, WAYLAND_DISPLAY='example'), patch.object(v2.shutil, 'which', return_value='/example'):
            picker = v2.LocationPicker(self.h, True)
        for results, expected in ((['Choose local folder', '/tmp/example'], '/tmp/example'),
                                  (['Enter URI or path', 'sftp://server.example/folder'], 'sftp://server.example/folder'),
                                  ([None], None)):
            with patch.object(picker, 'dialog', side_effect=results) as dialog, \
                    patch.object(v2.shutil, 'which', return_value='/example'):
                self.assertEqual(picker.choose(c, 'w1', []), expected)
            self.assertNotIn('shell', dialog.call_args.kwargs)

    def test_omarchy_input_backend_and_dialog_timeout(self):
        c = self.create()
        with patch.dict(os.environ, WAYLAND_DISPLAY='example'), \
                patch.object(v2.shutil, 'which', side_effect=lambda n: '/example' if n == 'omarchy-menu-input' else None):
            picker = v2.LocationPicker(self.h, True)
            with patch.object(picker, 'dialog', return_value='sftp://server.example/share') as dialog:
                self.assertEqual(picker.choose(c, 'w1', []), 'sftp://server.example/share')
            self.assertEqual(dialog.call_args.args[0][0], 'omarchy-menu-input')
        with patch.object(v2.subprocess, 'run', side_effect=subprocess.TimeoutExpired('dialog', 300)):
            self.assertIsNone(picker.dialog(['example']))

    def test_validate_reports_fallback_without_mutations(self):
        data = preset([window('a', N), window('b', N, self.uri)], node('x', .5, 'a', 'b'))
        before = copy.deepcopy(data)
        stream = io.StringIO()
        with patch.object(v2.sys, 'stdout', stream):
            v2.location_report(data)
        self.assertIn('coverage: 1/2; Home fallback: 1/2', stream.getvalue())
        self.assertEqual(data, before)

    def test_inspect_keeps_json_lines_stdout_for_existing_consumers(self):
        self.create()
        output, diagnostics = io.StringIO(), io.StringIO()
        with patch.object(v2, 'Hypr', return_value=self.h), \
                patch.object(v2, 'Runtime', return_value=self.rt), \
                patch.object(v2, 'Nautilus', return_value=self.n), \
                patch.object(v2.sys, 'argv', ['desktop-preset-v2', 'inspect', '-w', '1']), \
                patch.object(v2.sys, 'stdout', output), patch.object(v2.sys, 'stderr', diagnostics):
            v2.main()
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['class'], N)
        self.assertIn('coverage: 0/1', diagnostics.getvalue())


class SnapshotTests(unittest.TestCase):
    def snapshot(self, windows=None, owners=None, failure=None):
        n = object.__new__(v2.Nautilus)
        n.error = None
        owners = iter(owners or [':1.1', ':1.1', ':1.1'])
        def call(dest, path, interface, method, signature, args):
            if failure:
                raise failure
            if method == 'GetNameOwner':
                return (next(owners),)
            if method == 'GetConnectionUnixProcessID':
                return (100,)
            return (windows,)
        n.call = call
        return n.snapshot()

    def test_unavailable_empty_and_malformed_property(self):
        self.assertEqual(self.snapshot({})['windows'], {})
        self.assertIsNotNone(self.snapshot({})['owner'])
        for bad in (None, [], {'invalid': ['file:///example']},
                    {'/org/gnome/Nautilus/window/1': 'file:///example'},
                    {'/org/gnome/Nautilus/window/1': ['relative']},
                    {'/org/gnome/Nautilus/window/1': ['sftp://[']},
                    {'/org/gnome/Nautilus/window/1': [None]}):
            self.assertIsNone(self.snapshot(bad)['owner'])
        self.assertIsNone(self.snapshot(failure=TimeoutError())['owner'])

    def test_owner_change_and_foreign_filemanager_disable_snapshot(self):
        for owners in ([':1.1', ':1.2'], [':1.1', ':1.1', ':1.2']):
            self.assertIsNone(self.snapshot({}, owners=owners)['owner'])

    def test_bootstrap_is_allowed_only_when_no_previous_owner(self):
        empty = {'owner': None, 'windows': {}, 'absent': True}
        after = {'owner': ':1.1', 'windows': {'/window/1': ['file:///example']}}
        self.assertEqual(v2.Nautilus.correlated(empty, after), '/window/1')
        self.assertIsNone(v2.Nautilus.correlated(dict(empty, owner=':1.0'), after))

    def test_failed_snapshot_is_not_proof_of_empty_initial_inventory(self):
        before = {'owner': None, 'windows': {}}
        after = {'owner': ':1.1', 'windows': {'/window/existing': ['file:///example']}}
        self.assertIsNone(v2.Nautilus.correlated(before, after))
        self.assertIsNone(v2.Nautilus.correlated(dict(before, absent=False), after))

    def test_only_positive_name_absence_allows_bootstrap(self):
        n = object.__new__(v2.Nautilus)
        n.Gio = Mock()
        n.call = Mock(side_effect=Exception('synthetic'))
        n.Gio.DBusError.get_remote_error.return_value = 'org.freedesktop.DBus.Error.NameHasNoOwner'
        self.assertTrue(n.snapshot()['absent'])
        n.Gio.DBusError.get_remote_error.return_value = 'org.freedesktop.DBus.Error.NoReply'
        self.assertFalse(n.snapshot()['absent'])

    def test_missing_pygobject_is_optional(self):
        with patch.dict('sys.modules', {'gi': None, 'gi.repository': None}):
            n = v2.Nautilus()
        self.assertIsNone(n.bus)
        self.assertIsNone(n.snapshot()['owner'])

    def test_typed_variant_signature_is_checked(self):
        n = object.__new__(v2.Nautilus)
        n.bus, n.Gio, n.GLib = Mock(), Mock(), Mock()
        result = n.bus.call_sync.return_value
        result.get_type_string.return_value = '(v)'
        variant = result.get_child_value.return_value.get_variant.return_value
        variant.get_type_string.return_value = 'as'
        with self.assertRaisesRegex(v2.PresetError, 'signature'):
            n.call('example', '/example', 'org.freedesktop.DBus.Properties', 'Get', '(ss)',
                   ('org.freedesktop.FileManager1', 'OpenWindowsWithLocations'))


if __name__ == '__main__':
    unittest.main()
