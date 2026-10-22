"""Local Android UI inspection; no cloud upload or message-sending actions."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

adb = [str(Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk/platform-tools/adb.exe'), '-s', '192.168.1.36:43847']
folder = Path(os.environ['TEMP']) / 'kanglish-private-audit-20261020'
folder.mkdir(exist_ok=True)

def run(*args):
    return subprocess.check_output(adb + list(args))

def dump():
    run('shell', 'uiautomator', 'dump', '/sdcard/kanglish-audit-ui.xml')
    return ET.fromstring(run('exec-out', 'cat', '/sdcard/kanglish-audit-ui.xml'))

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['dump', 'tap-id', 'tap-text', 'tap-desc', 'hold-id', 'capture', 'collect'])
parser.add_argument('value', nargs='?', default='screen')
args = parser.parse_args()
tree = dump()
if args.action == 'collect':
    pages = []
    for i in range(5):
        if i: tree = dump()
        assert any(n.get('text') == 'Nukur gudde boys' for n in tree.iter('node')), 'Not in requested group'
        page = {'bodies': [n.get('text') for n in tree.iter('node') if n.get('resource-id') == 'com.whatsapp:id/message_text'],
                'voice_notes': sum(n.get('resource-id') == 'com.whatsapp:id/conversation_row_voice_note' for n in tree.iter('node')),
                'stickers': sum(n.get('resource-id') == 'com.whatsapp:id/conversation_row_sticker' for n in tree.iter('node'))}
        pages.append(page)
        run('shell', 'input', 'swipe', '540', '600', '540', '1850', '450')
    (folder / (args.value + '.json')).write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(pages, ensure_ascii=True))
elif args.action in ['tap-id', 'tap-text', 'tap-desc', 'hold-id']:
    field = 'resource-id' if args.action.endswith('id') else 'text' if args.action == 'tap-text' else 'content-desc'
    node = next(n for n in tree.iter('node') if n.get(field) == args.value)
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
    x, y = str((x1+x2)//2), str((y1+y2)//2)
    if args.action == 'hold-id': run('shell', 'input', 'swipe', x, y, x, y, '700')
    else: run('shell', 'input', 'tap', x, y)
elif args.action == 'capture':
    (folder / (args.value + '.png')).write_bytes(run('exec-out', 'screencap', '-p'))
    ET.ElementTree(tree).write(folder / (args.value + '.xml'), encoding='utf-8')
    print(folder / (args.value + '.png'))
else:
    print(json.dumps([{'id': n.get('resource-id'), 'text': '[hidden]' if n.get('password') == 'true' else n.get('text'),
                      'desc': n.get('content-desc'), 'bounds': n.get('bounds'), 'hold': n.get('long-clickable')}
                     for n in tree.iter('node') if n.get('text') or n.get('content-desc') or n.get('long-clickable') == 'true'], ensure_ascii=True))
