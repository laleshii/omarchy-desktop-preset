"""Stateful v2 orchestration tests. No host session or application is accessed."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('v2', str(ROOT / 'bin/desktop-preset-v2'))
spec = importlib.util.spec_from_loader('v2', loader)
v2 = importlib.util.module_from_spec(spec)
loader.exec_module(v2)
N, G = v2.NAUTILUS, 'com.mitchellh.ghostty'


def window(ident, cls=G, uri=None, floating=False):
    w = dict(id=ident, **{'class': cls}, title_hint='identical', argv=['ghostty'],
             cwd=None, floating=floating, rect=[0, 0, 10, 10])
    if cls == N:
        w.update(uri=uri, argv=['nautilus', '--new-window'])
    return w


def node(axis, ratio, a, b):
    return dict(axis=axis, ratio=ratio,
                first={'id': a} if isinstance(a, str) else a,
                second={'id': b} if isinstance(b, str) else b)


def rectangles(tree, box=(0, 0, 2560, 1050)):
    if tree is None:
        return {}
    if 'id' in tree:
        x, y, w, h = box
        # Window border + inner gap on cuts; outer gap + border at the workarea.
        l = 6 if x == 0 else 4
        t = 6 if y == 0 else 4
        r = 6 if abs(x + w - 2560) < .01 else 4
        b = 6 if abs(y + h - 1050) < .01 else 4
        return {tree['id']: [round(x + l), round(y + t), round(w - l - r), round(h - t - b)]}
    axis = 0 if tree['axis'] == 'x' else 1
    a, b = list(box), list(box)
    a[axis + 2] *= tree['ratio']
    b[axis] += a[axis + 2]
    b[axis + 2] -= a[axis + 2]
    return rectangles(tree['first'], a) | rectangles(tree['second'], b)


def preset(windows, tree):
    rects = rectangles(tree)
    for w in windows:
        if w['floating']:
            w['rect'] = [30, 40, 300, 250]
        else:
            w['rect'] = rects[w['id']]
    return dict(version=2, workarea=[0, 0, 2560, 1050], windows=windows, tree=tree)


class FakeNautilus:
    bus = True
    correlated = staticmethod(v2.Nautilus.correlated)
    location = staticmethod(v2.Nautilus.location)

    def __init__(self):
        self.windows = {}
        self.owner = ':1.1'

    def snapshot(self):
        return copy.deepcopy(dict(owner=self.owner, windows=self.windows))


class FakeHypr:
    """Binary compositor with real insert/remove/ratio and rendered gap behavior."""
    def __init__(self, nautilus):
        self.windows = []
        self.trees = {}
        self.active = 1
        self.focused = None
        self.direction = 'r'
        self.dispatches = []
        self.launches = []
        self.next_id = 256
        self.n = nautilus
        self.pending = []
        self.slow = 2
        self.no_window = False
        self.title_change = None
        self.vanish = False
        self.policy = True

    def context(self, ws):
        return [0, 0, 2560, 1050]

    def check_policy(self):
        if not self.policy:
            raise v2.PresetError('unsupported policy')

    def clients(self):
        for pending in self.pending[:]:
            pending[0] -= 1
            if pending[0] <= 0:
                self.windows.append(pending[1])
                self.pending.remove(pending)
        return copy.deepcopy(self.windows)

    def focus(self, addr):
        self.focused = addr
        self.active = self.get(addr)['workspace']['id']
        self.dispatches.append(('focus', addr))

    def get(self, addr):
        return next(c for c in self.windows if c['address'] == addr)

    def remove(self, tree, addr):
        if not tree or tree.get('id') == addr:
            return None
        if 'id' in tree:
            return tree
        a, b = self.remove(tree['first'], addr), self.remove(tree['second'], addr)
        if not a or not b:
            return a or b
        return dict(tree, first=a, second=b)

    def insert(self, tree, focus, addr):
        if not tree:
            return {'id': addr}
        if tree.get('id') == focus:
            return node('x' if self.direction == 'r' else 'y', .5, focus, addr)
        if 'id' in tree:
            return tree
        return dict(tree, first=self.insert(tree['first'], focus, addr),
                    second=self.insert(tree['second'], focus, addr))

    def render(self, ws):
        rects = rectangles(self.trees.get(ws))
        for c in self.windows:
            if c['address'] in rects:
                c['at'], c['size'] = rects[c['address']][:2], rects[c['address']][2:]

    def move(self, addr, ws, follow=False):
        self.dispatches.append(('move', addr, ws))
        c = self.get(addr)
        old = c['workspace']['id']
        self.trees[old] = self.remove(self.trees.get(old), addr)
        self.render(old)
        c['workspace'] = dict(id=ws if isinstance(ws, int) else -99, name=str(ws))
        if not c['floating'] and isinstance(ws, int):
            tree = self.trees.get(ws)
            focus = self.focused if self.focused in rectangles(tree) else next(iter(rectangles(tree)), None)
            self.trees[ws] = self.insert(tree, focus, addr)
            self.render(ws)
        if follow:
            self.focused = addr
            self.active = ws

    def dispatch(self, code):
        self.dispatches.append(code)
        if code.startswith('hl.dsp.focus'):
            self.active = int(re.search(r'workspace = "(\d+)"', code)[1])
        elif 'preselect' in code:
            self.direction = re.search(r'preselect (\w+)', code)[1]
        elif 'splitratio' in code:
            ratio = float(re.search(r'splitratio ([\d.]+)', code)[1]) / 2
            def update(tree):
                if 'id' not in tree:
                    if any(tree[k].get('id') == self.focused for k in ('first', 'second')):
                        tree['ratio'] = ratio
                    else:
                        update(tree['first']); update(tree['second'])
            update(self.trees[self.active])
            self.render(self.active)
        elif 'window.float' in code:
            addr = re.search(r'address:(0x[0-9a-f]+)', code)[1]
            c = self.get(addr)
            c['floating'] = True
            ws = c['workspace']['id']
            self.trees[ws] = self.remove(self.trees.get(ws), addr)
            self.render(ws)
        elif 'window.resize' in code or 'window.move' in code:
            c = self.get(re.search(r'address:(0x[0-9a-f]+)', code)[1])
            xy = [int(re.search(rf'{key} = (\d+)', code)[1]) for key in ('x', 'y')]
            c['size' if 'resize' in code else 'at'] = xy
        else:
            raise AssertionError(code)

    def popen(self, argv, **kwargs):
        self.launches.append((list(argv), kwargs.get('cwd')))
        if self.title_change:
            self.get(self.title_change)['title'] = 'identical'
        if self.no_window:
            return unittest.mock.Mock()
        addr = hex(self.next_id)
        self.next_id += 1
        cls = N if argv[0] == 'nautilus' else G
        c = dict(address=addr, workspace=dict(id=self.active, name=str(self.active)),
                 **{'class': cls}, title='identical', pid=0, at=[0, 0], size=[100, 100], floating=False)
        self.pending.append([self.slow, c])
        if cls == N:
            self.n.windows[f'/window/{addr}'] = [argv[-1]]
        return unittest.mock.Mock()


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rt = v2.Runtime(self.root / 'runtime')
        self.n = FakeNautilus()
        self.h = FakeHypr(self.n)
        self.engine = v2.Loader(self.h, self.rt, self.n, timeout=.1)
        self.engine.wait = .001
        self.engine.settle = lambda: None
        self.path = self.root / 'test.preset'
        self.patch = patch.object(v2.subprocess, 'Popen', self.h.popen)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.uri = self.root.as_uri()

    def write(self, data):
        v2.atomic_json(self.path, data)
        return data

    def multi(self):
        windows = [window('g1'), window('g2'), window('n1', N, self.uri),
                   window('n2', N, self.uri), window('n3', N, self.uri)]
        tree = node('x', .38, node('y', .61, 'n1', 'g1'),
                    node('y', .43, 'n2', node('x', .64, 'g2', 'n3')))
        return self.write(preset(windows, tree))

    def test_two_ghostty_three_nautilus_nested_ratios_and_three_workspaces(self):
        data = self.multi()
        for ws in (1, 2, 3):
            self.engine.load(self.path, ws)
        clients = self.h.clients()
        self.assertEqual(len({c['address'] for c in clients}), 15)
        for ws in (1, 2, 3):
            local = [c for c in clients if c['workspace']['id'] == ws]
            self.assertEqual(len(local), 5)
            self.assertEqual(sum(c['class'] == N for c in local), 3)
        before = copy.deepcopy(clients)
        launches = len(self.h.launches)
        for ws in (1, 2, 3):
            self.engine.load(self.path, ws)
        self.assertEqual(self.h.clients(), before)
        self.assertEqual(len(self.h.launches), launches)
        self.assertEqual(len(data['windows']), 5)

    def test_two_same_directory_windows_keep_distinct_geometry(self):
        self.write(preset([window('a', N, self.uri), window('b', N, self.uri)],
                          node('x', .31, 'a', 'b')))
        self.engine.load(self.path, 1)
        cs = self.h.clients()
        self.assertNotEqual(cs[0]['address'], cs[1]['address'])
        self.assertNotEqual(cs[0]['size'], cs[1]['size'])
        self.assertEqual([self.engine.uri(c, self.n.snapshot()) for c in cs], [self.uri] * 2)

    def test_distinct_uri_association_and_shell_characters(self):
        uris = []
        for name in ('folder space 日本', "quote'|;$(touch hacked)`x`", 'third'):
            folder = self.root / name
            folder.mkdir()
            uris.append(folder.as_uri())
        windows = [window(str(i), N, uri) for i, uri in enumerate(uris)]
        self.write(preset(windows, node('x', .4, '0', node('y', .7, '1', '2'))))
        self.engine.load(self.path, 1)
        journal = self.rt.data['loads'][self.rt.key(self.path, 1)]['instances']
        for w in windows:
            c = self.h.get(journal[w['id']]['address'])
            self.assertEqual(self.engine.uri(c, self.n.snapshot()), w['uri'])
        self.assertFalse((self.root / 'hacked').exists())
        self.assertEqual([argv[-1] for argv, _ in self.h.launches], uris)

    def test_inference_ids_and_ratios_roundtrip_for_five_and_ten(self):
        for count in (3, 5, 10):
            tree = {'id': 'w0'}
            for i in range(1, count):
                tree = node('x' if i % 2 else 'y', .6, tree, f'w{i}')
            rects = rectangles(tree)
            inferred = v2.layout.infer_v2([dict(zip(('id', 'x', 'y', 'w', 'h'), [i, *r]))
                                          for i, r in rects.items()], [0, 0, 2560, 1050])
            rebuilt = rectangles(inferred)
            self.assertEqual(set(rebuilt), set(rects))
            self.assertLessEqual(max(abs(a-b) for i in rects for a,b in zip(rects[i],rebuilt[i])), 3)

    def test_no_duplicate_pattern_fallback(self):
        data = self.multi()
        ids = [w['id'] for w in data['windows']]
        self.assertEqual(len(ids), len(set(ids)))
        anchor, steps = v2.layout.steps_v2(data['tree'])
        self.assertEqual(len(steps), 4)
        self.assertCountEqual([anchor] + [s['new'] for s in steps], ids)
        self.assertEqual(len({s['ratio'] for s in steps}), 4)

    def test_timeout_retains_pending_and_requires_explicit_retry(self):
        self.write(preset([window('a')], {'id': 'a'}))
        self.h.no_window = True
        with self.assertRaisesRegex(v2.PresetError, 'timed out'):
            self.engine.load(self.path, 1)
        with self.assertRaisesRegex(v2.PresetError, 'previous launch'):
            self.engine.load(self.path, 1)
        self.assertEqual(len(self.h.launches), 1)
        self.h.no_window = False
        self.engine.load(self.path, 1, retry=True)
        self.assertEqual(len(self.h.launches), 2)

    def test_slow_new_address_ignores_old_title_change(self):
        self.write(preset([window('a')], {'id': 'a'}))
        self.h.popen(['ghostty'])
        self.h.clients(); self.h.clients()
        old = self.h.windows[0]
        old['workspace'] = dict(id=9, name='9')
        old['title'] = 'Starting'
        self.h.title_change = old['address']
        self.h.slow = 8
        self.engine.load(self.path, 1)
        self.assertEqual(old['workspace']['id'], 9)
        self.assertEqual(len(self.h.clients()), 2)

    def test_missing_uri_is_visible_and_preflight_has_no_mutations(self):
        self.write(preset([window('a'), window('b', N)], node('x', .5, 'a', 'b')))
        with self.assertRaisesRegex(v2.PresetError, 'URI unavailable'):
            self.engine.load(self.path, 1)
        self.assertEqual(self.h.launches, [])
        self.assertEqual(self.h.dispatches, [])

    def test_unavailable_folder_does_not_fallback_home(self):
        self.write(preset([window('a', N, (self.root/'missing').as_uri())], {'id':'a'}))
        with self.assertRaisesRegex(v2.PresetError, 'missing or inaccessible'):
            self.engine.load(self.path, 1)
        self.assertEqual(self.h.launches, [])

    def test_dry_run_has_no_launch_move_or_journal_write(self):
        self.multi()
        before = copy.deepcopy(self.rt.data)
        self.engine.load(self.path, 1, dry=True, clear=True)
        self.assertEqual(self.h.dispatches, [])
        self.assertEqual(self.h.launches, [])
        self.assertEqual(self.rt.data, before)
        self.assertFalse(self.rt.path.exists())

    def test_ambiguous_existing_windows_fail_without_launching(self):
        self.multi()
        self.h.popen(['ghostty']); self.h.popen(['ghostty'])
        self.h.clients(); self.h.clients()
        with self.assertRaisesRegex(v2.PresetError, 'ambiguous'):
            self.engine.load(self.path, 1)
        self.assertEqual(len(self.h.launches), 2)
        self.assertEqual(self.h.dispatches, [])

    def test_unrelated_local_window_is_not_staged(self):
        self.write(preset([window('a', N, self.uri)], {'id':'a'}))
        self.h.popen(['ghostty']); self.h.clients(); self.h.clients()
        with self.assertRaisesRegex(v2.PresetError, 'unassigned'):
            self.engine.load(self.path, 1)
        self.assertEqual(self.h.dispatches, [])

    def test_float_geometry_uses_its_own_id(self):
        self.write(preset([window('a'), window('b', G, floating=True)], {'id':'a'}))
        self.engine.load(self.path, 1)
        clients = self.h.clients()
        self.assertFalse(clients[0]['floating'])
        self.assertTrue(clients[1]['floating'])
        self.assertEqual(clients[1]['at'] + clients[1]['size'], [30,40,300,250])

    def test_wrong_uri_does_not_get_reported_as_restored(self):
        self.write(preset([window('a', N, self.uri)], {'id':'a'}))
        original = self.h.popen
        def wrong(argv, **kwargs):
            result = original(argv, **kwargs)
            for k in self.n.windows:
                self.n.windows[k] = ['file:///wrong']
            return result
        with patch.object(v2.subprocess, 'Popen', wrong):
            with self.assertRaisesRegex(v2.PresetError, 'verified Nautilus URI'):
                self.engine.load(self.path, 1)

    def test_journal_does_not_reclaim_window_moved_to_other_workspace(self):
        self.write(preset([window('a')], {'id':'a'}))
        self.engine.load(self.path, 1)
        old = self.h.windows[0]
        self.h.move(old['address'], 9)
        self.engine.load(self.path, 1)
        self.assertEqual(old['workspace']['id'], 9)
        self.assertEqual(len(self.h.clients()), 2)

    def test_save_force_backup_and_explicit_nautilus_override(self):
        self.multi()
        self.engine.load(self.path, 1)
        old = self.path.read_bytes()
        cs = self.h.clients()
        overrides = {c['address']: self.uri for c in cs if c['class'] == N}
        data = v2.save(self.path,1,True,overrides,self.h,self.rt,self.n)
        self.assertEqual(len(list(self.root.glob('*.bak.*'))),1)
        self.assertEqual(next(self.root.glob('*.bak.*')).read_bytes(),old)
        self.assertEqual(sum(w.get('uri')==self.uri for w in data['windows']),3)
        with self.assertRaisesRegex(v2.PresetError,'preset exists'):
            v2.save(self.path,1,False,overrides,self.h,self.rt,self.n)

    def test_untracked_save_warns_instead_of_guessing_uri(self):
        self.h.popen(['nautilus','--new-window',self.uri])
        self.h.clients(); self.h.clients()
        self.h.move(self.h.windows[0]['address'],1)
        with patch.object(v2,'warn') as warning:
            data=v2.save(self.path,1,False,{},self.h,self.rt,self.n)
        self.assertIsNone(data['windows'][0]['uri'])
        self.assertTrue(warning.called)

    def test_correlated_save_captures_single_tab_and_refuses_multi_tab(self):
        self.write(preset([window('a',N,self.uri)],{'id':'a'}))
        self.engine.load(self.path,1)
        data=v2.save(self.root/'copy.preset',1,False,{},self.h,self.rt,self.n)
        self.assertEqual(data['windows'][0]['uri'],self.uri)
        for k in self.n.windows:
            self.n.windows[k].append('sftp://host/elsewhere')
        data=v2.save(self.root/'tabs.preset',1,False,{},self.h,self.rt,self.n)
        self.assertIsNone(data['windows'][0]['uri'])

    def test_dbus_owner_change_and_multiple_new_objects_are_not_guessed(self):
        before=dict(owner='one',windows={'/old':['file:///one']})
        after=dict(owner='two',windows={'/old':['file:///new']})
        self.assertEqual(self.n.correlated(before,after),'/old')
        self.assertIsNone(self.n.location(after,dict(owner='one',object='/old')))
        after['windows']['/another']=['file:///two']
        self.assertIsNone(self.n.correlated(before,after))

    def test_validation_rejects_duplicate_ids_invalid_refs_and_injection(self):
        data=self.multi()
        for changed in ('id','ref','ratio','axis','argv'):
            bad=copy.deepcopy(data)
            if changed=='id':bad['windows'][0]['id']=bad['windows'][1]['id']
            if changed=='ref':bad['tree']['first']={'id':'missing'}
            if changed=='ratio':bad['tree']['ratio']=float('nan')
            if changed=='axis':bad['tree']['axis']='x; execute'
            if changed=='argv':bad['windows'][0]['argv']='touch hacked'
            with self.assertRaises(v2.PresetError):v2.validate(bad)
        with self.assertRaises(v2.PresetError):v2.safe_address('0x1"}); execute()')

    def test_uri_normalization_local_unicode_and_remote(self):
        for name in ('space a','Юникод','percent%20literal',"quote'"):
            p=self.root/name
            self.assertEqual(v2.normalize_uri(str(p)),p.as_uri())
        for uri in ('sftp://server/dir%20space','smb://server/share/a','file:///tmp/a%23b'):
            self.assertEqual(v2.normalize_uri(uri),uri)
        for bad in ('','relative/path','file://server/foo','file:relative'):
            with self.assertRaises(v2.PresetError):v2.normalize_uri(bad)
        self.assertTrue(v2.uri_equal('file:///tmp/a%20%24%28x%29','file:///tmp/a%20$(x)'))
        self.assertFalse(v2.uri_equal('file:///tmp/a%20b','file:///tmp/a%2520b'))

    def test_constraint_mismatch_reports_failure(self):
        data=self.multi()
        self.engine.load(self.path,1)
        journal=self.rt.data['loads'][self.rt.key(self.path,1)]['instances']
        addresses={i:r['address'] for i,r in journal.items()}
        self.h.windows[0]['size'][0]+=30
        with self.assertRaisesRegex(v2.PresetError,'rendered geometry'):
            self.engine.verify(data,addresses,1,data['workarea'])


if __name__=='__main__':
    unittest.main()
