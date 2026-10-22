"""Exercise the Translate page with a nonprivate sample; never read or log API keys."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
ADB = str(Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/platform-tools/adb.exe')
PACKAGE = 'org.kanglish.app'
IDS = {'etPasteInput', 'tvQuickResult', 'tvQuickTeacherStatus', 'tvQuickTeacherTranslation',
       'tvQuickTeacherExplanation', 'pbQuickTeacher', 'pbQuickTranslating', 'btnCopyQuick',
       'btnCopyQuickTeacher', 'btnRetryQuickTeacher'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', default='192.168.1.36:34679')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--text', default='sakkath aagide')
    parser.add_argument('--name', default='teacher_glossary')
    args = parser.parse_args()
    adb = [ADB, '-s', args.serial]

    def run(*command):
        return subprocess.check_output(adb + list(command), timeout=30)

    def dump():
        run('shell', 'uiautomator', 'dump', '/sdcard/kanglish-teacher-ui.xml')
        return ET.fromstring(run('exec-out', 'cat', '/sdcard/kanglish-teacher-ui.xml'))

    if args.install:
        apk = ROOT / 'mobile/android/app/build/outputs/apk/debug/app-debug.apk'
        result = run('install', '-r', str(apk)).decode('utf-8', errors='replace').strip()
        print('APK update: ' + result, flush=True)
        if 'Success' not in result:
            raise RuntimeError('APK update did not succeed')

    run('shell', 'input', 'keyevent', 'KEYCODE_WAKEUP')
    launch = 'am start -W -n org.kanglish.app/.ui.MainActivity --es extra_text ' + shlex.quote(args.text)
    run('shell', launch)
    started = time.monotonic()
    observations = []
    local_result = ''
    scrolled = False
    terminal = {'Agrees with the model', 'Suggests a correction', 'Needs more context',
                'Review unavailable', 'Cloud review is off', 'API key needed'}
    while time.monotonic() - started < 90:
        tree = dump()
        app_nodes = [node for node in tree.iter('node') if node.get('package') == PACKAGE]
        if not app_nodes:
            print('Waiting for Kanglish to be visible.', flush=True)
            time.sleep(1)
            continue
        values = {node.get('resource-id', '').split('/')[-1]: node.get('text', '')
                  for node in app_nodes if node.get('resource-id', '').split('/')[-1] in IDS}
        local_result = values.get('tvQuickResult', local_result)
        if not observations or values != observations[-1]['values']:
            record = {'elapsed_seconds': round(time.monotonic() - started, 2), 'values': values}
            observations.append(record)
            print(json.dumps(record, ensure_ascii=True), flush=True)
        status = values.get('tvQuickTeacherStatus', '')
        if status in terminal:
            result = {'input': args.text, 'local_translation': local_result,
                      'teacher_status': status,
                      'teacher_translation': values.get('tvQuickTeacherTranslation', ''),
                      'explanation': values.get('tvQuickTeacherExplanation', ''),
                      'observations': observations}
            (FOLDER / (args.name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
            filtered = ET.Element('app-ui')
            for node in app_nodes:
                if node.get('resource-id', '').split('/')[-1] in IDS:
                    ET.SubElement(filtered, 'node', node.attrib)
            ET.ElementTree(filtered).write(FOLDER / (args.name + '.xml'), encoding='utf-8', xml_declaration=True)
            (FOLDER / (args.name + '.png')).write_bytes(run('exec-out', 'screencap', '-p'))
            print(json.dumps(result, indent=2), flush=True)
            return 0 if status in {'Agrees with the model', 'Suggests a correction', 'Needs more context'} else 1
        if local_result and local_result != 'Translating on your phone...' and not scrolled:
            scroll = next((node for node in app_nodes if node.get('resource-id') == PACKAGE + ':id/viewImportTab'), None)
            if scroll is not None:
                x1, y1, x2, y2 = map(int, re.findall(r'\d+', scroll.get('bounds')))
                x = (x1 + x2) // 2
                run('shell', 'input', 'swipe', str(x), str(y1 + (y2 - y1) * 4 // 5),
                    str(x), str(y1 + (y2 - y1) // 4), '350')
                scrolled = True
        time.sleep(0.5)
    raise RuntimeError('Timed out waiting for the teacher panel')


if __name__ == '__main__':
    raise SystemExit(main())
