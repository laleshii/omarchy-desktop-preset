"""Run install/uninstall in a disposable HOME with fake host commands."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_validate_missing_uri_is_successful_and_legacy_stays_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env = dict(os.environ, DESKTOP_PRESET_DIR=tmp,
                       DESKTOP_PRESET_RUNTIME_DIR=str(directory/'runtime'))
            path = directory/'example.preset'
            for text in ('example | example\n', json.dumps(dict(version=2, workarea=[0,0,1000,800],
                    windows=[dict(id='a', **{'class': 'org.gnome.Nautilus'}, floating=False,
                                  rect=[6,6,988,788], uri=None)], tree={'id':'a'}))):
                path.write_text(text)
                result = subprocess.run([str(ROOT/'bin/desktop_preset'), 'validate', 'example'],
                                        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(path.read_text(), text)
                self.assertIn('Legacy' if text.startswith('example') else 'Home fallback: 1/1', result.stdout)

    def test_autostart_wrapper_propagates_exit_and_warn_only_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            cli = directory/'desktop_preset'
            notify = directory/'omarchy'
            marker = directory/'notified'
            notify.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\n')
            notify.chmod(0o755)
            env = dict(os.environ, PATH=f'{directory}:{os.environ["PATH"]}')
            for rc in (0, 1):
                cli.write_text('#!/bin/sh\necho "warning: synthetic Home fallback"\nexit '+str(rc)+'\n')
                cli.chmod(0o755)
                result = subprocess.run([str(ROOT/'bin/desktop-preset-autostart')], env=env,
                                        stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, rc)
                self.assertEqual(marker.exists(), rc != 0)

    def test_reinstall_and_uninstall_preserve_data_and_unrelated_customization(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / 'fakebin'
            bin_dir.mkdir()
            for name in ('hyprctl', 'omarchy'):
                script = bin_dir / name
                script.write_text('#!/bin/sh\nprintf "test-host\\n"\n')
                script.chmod(0o755)
            preset_dir = home / '.config/desktop_preset'
            preset_dir.mkdir(parents=True)
            legacy = b'example | example\n@anchor example\n'
            (preset_dir/'old.preset').write_bytes(legacy)
            (preset_dir/'autostart.conf').write_bytes(b'3=old\n')
            hook = home / '.config/hypr/autostart.lua'
            hook.parent.mkdir(parents=True)
            hook.write_text('-- desktop-preset-autostart is optional\no.launch_on_start("unrelated")\n')
            menu = home / '.config/omarchy/extensions/omarchy-menu.jsonc'
            menu.parent.mkdir(parents=True)
            unrelated = '  "personal.tools": {"action":"omarchy-menu-select unrelated"},\n'
            menu.write_text('{\n'+unrelated+'}\n')
            env = dict(os.environ, HOME=tmp, PATH=f'{bin_dir}:{os.environ["PATH"]}')
            for _ in range(2):
                result = subprocess.run(['bash',str(ROOT/'install.sh')],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(hook.read_text().count('o.launch_on_start("desktop-preset-autostart")'),1)
            self.assertEqual(menu.read_text().count('"trigger.preset"'),1)
            self.assertIn(unrelated,menu.read_text())
            for src in (ROOT/'bin').iterdir():
                if src.is_file() and src.name.startswith(('desktop-preset','desktop_preset')):
                    self.assertEqual((home/'.local/bin'/src.name).read_bytes(),src.read_bytes())
            result = subprocess.run(['bash',str(ROOT/'uninstall.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((preset_dir/'old.preset').read_bytes(),legacy)
            self.assertEqual((preset_dir/'autostart.conf').read_bytes(),b'3=old\n')
            self.assertEqual(menu.read_text(),'{\n'+unrelated+'}\n')
            self.assertIn('-- desktop-preset-autostart is optional',hook.read_text())
            self.assertIn('o.launch_on_start("unrelated")',hook.read_text())
            self.assertFalse((home/'.local/bin/desktop-preset-v2').exists())

    def test_location_helper_preserves_ids_tree_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            directory=home/'presets'
            directory.mkdir()
            data=dict(version=2,workarea=[0,0,1000,800],tree={'id':'a'},windows=[
                dict(id='a',**{'class':'org.gnome.Nautilus'},argv=['nautilus','--new-window'],
                     floating=False,rect=[6,6,988,788],uri=None)])
            path=directory/'test.preset'
            path.write_text('\n  '+json.dumps(data))
            before=path.read_bytes()
            folder=home/"spaces 日本 ;$(touch never)"
            env=dict(os.environ,DESKTOP_PRESET_DIR=str(directory),DESKTOP_PRESET_RUNTIME_DIR=str(home/'runtime'))
            result=subprocess.run([str(ROOT/'bin/desktop_preset'),'location','set','test','a',str(folder)],
                                  env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            updated=json.loads(path.read_text())
            self.assertEqual(updated['tree'],data['tree'])
            self.assertEqual(updated['windows'][0]['id'],'a')
            self.assertEqual(updated['windows'][0]['uri'],folder.as_uri())
            self.assertEqual(next(directory.glob('*.bak.*')).read_bytes(),before)
            self.assertFalse((home/'never').exists())
            result=subprocess.run([str(ROOT/'bin/desktop_preset'),'list'],
                                  env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('a  org.gnome.Nautilus',result.stdout)


if __name__=='__main__':
    unittest.main()
