"""Local ADB helpers for this device smoke test; Python standard library only."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

FOLDER = Path(__file__).resolve().parent
ADB = [os.path.join(os.environ['LOCALAPPDATA'], 'Android', 'Sdk', 'platform-tools', 'adb.exe'), '-s', '192.168.1.36:34679']

def run(*args):
    return subprocess.check_output(ADB + list(args), text=True, errors='replace')

def dump():
    run('shell', 'uiautomator', 'dump', '/sdcard/kanglish-audit-ui.xml')
    return ET.fromstring(subprocess.check_output(ADB + ['exec-out', 'cat', '/sdcard/kanglish-audit-ui.xml']))

def tap_node(node):
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
    run('shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))

def tap_id(name):
    tree = dump()
    node = next(n for n in tree.iter('node') if n.get('resource-id') == 'org.kanglish.app:id/' + name)
    tap_node(node)

def tap_text(text):
    node = next(n for n in dump().iter('node') if n.get('text') == text)
    tap_node(node)

def capture(name, tree=None):
    tree = tree if tree is not None else dump()
    ET.ElementTree(tree).write(FOLDER / (name + '.xml'), encoding='utf-8', xml_declaration=True)
    with (FOLDER / (name + '.png')).open('wb') as output:
        subprocess.run(ADB + ['exec-out', 'screencap', '-p'], stdout=output, check=True)
    return tree

def values(tree):
    return {n.get('resource-id').split('/')[-1]: n.get('text') for n in tree.iter('node') if n.get('resource-id', '').startswith('org.kanglish.app:id/')}

def translate(text, name):
    tap_text('TRANSLATE')
    tap_id('btnClearPasteText')
    tap_id('etPasteInput')
    run('shell', 'input', 'text', text.replace(' ', '%s'))
    run('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    tree = dump()
    actual_input = values(tree).get('etPasteInput')
    if actual_input != text:
        capture(name + '_input_mismatch', tree)
        raise RuntimeError('Input mismatch: ' + repr(actual_input))
    button = next(n for n in tree.iter('node') if n.get('resource-id') == 'org.kanglish.app:id/btnParsePaste')
    started = time.monotonic()
    tap_node(button)
    samples = []
    for _ in range(10):
        tree = dump()
        text_values = values(tree)
        result = text_values.get('tvQuickResult', '')
        samples.append({'elapsed_seconds': round(time.monotonic() - started, 2), 'result': result})
        if result and result != 'Translating on your phone...':
            break
        if 'viewModelTab' in text_values:
            raise RuntimeError('Screen changed to Settings during test')
    capture(name, tree)
    record = {'input': text, 'actual': result, 'observations': samples, 'timing_note': 'Includes ADB and UIAutomator polling overhead; not a throughput benchmark.'}
    (FOLDER / (name + '.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)
    return record
