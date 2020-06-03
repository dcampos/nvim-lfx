#!/usr/bin/env python3

from core.types import ClientConfig, Settings
from core.sessions import create_session
from core.protocol import WorkspaceFolder
from core.sessions import Session
from core.protocol import Request, Notification
from core.url import filename_to_uri
from core.logging import set_debug_logging, set_exception_logging, setup_log

import signal
import sys
import time
import shutil
import json
import argparse
import os

INTELEPHENSE = ['node',
                '/home/dpc/.npm-global/lib/node_modules/intelephense/lib/intelephense.js',
                '--stdio']
PYLS = [shutil.which('pyls')]
WORKING_FILE = '/home/dpc/sandbox/ulf/rplugin/python3/ulf/core/diff.py'
# WORKING_FILE='/home/dpc/Dev/eproc1g/web/modulos/sandbox/tools/TesteDatas.php'
# WORKING_FILE='/home/dpc/Dev/godot/my-circle-jump/Main.gd'

initialized = False
position = [1, 1]

configs = {
    '.php': ClientConfig(
        name='intelephense',
        binary_args=INTELEPHENSE,
        # binary_args=[shutil.which('pyls')],
        tcp_port=None,
        languageId='python',
        settings=dict(),
        init_options={
                'clearCache': False,
                'storagePath': '/tmp/foo',
            }),
    '.py': ClientConfig(
        name='pyls',
        binary_args=PYLS,
        tcp_port=None,
        languageId='python',
        settings={},
        init_options={}),
    '.gd': ClientConfig(
        name='godot',
        binary_args=[],
        tcp_port=6008,
        languageId='gdscript3',
        settings={},
        init_options={}),
}

def on_pre_initialize(session):
    print('Pre-initialize called')

def on_post_initialize(session: Session):
    global initialized
    print('Post-initialize called')
    initialized = True
    print(session.capabilities)

    session.client.send_notification(
        Notification.initialized())

    did_open(working_file)

    session.client.on_notification(
        'indexingStarted', lambda params: print(params))
    session.client.on_notification(
        'indexingEnded', lambda params: print(params))

def find_root(file):
    head, tail = os.path.split(file)
    found = head
    while tail != '':
        for lookup in ['.gitmodules', '.git']:
            lookup = os.path.join(head, lookup)
            if os.path.exists(lookup):
                found = head
                break
        head, tail = os.path.split(head)
    return found

parser = argparse.ArgumentParser()
parser.add_argument('file', nargs='?', type=argparse.FileType('r'),
                    default=WORKING_FILE)
args = parser.parse_args()

working_file = os.path.abspath(args.file.name)
file_ext = os.path.splitext(working_file)[1]
root_path = find_root(working_file)
root_name = os.path.dirname(root_path)

for key in configs.keys():
    if key == file_ext:
        config = configs[key]
        break
else:
    raise KeyError('No config found for this file')

workspace = WorkspaceFolder(root_name, root_path)
# workspace = WorkspaceFolder('eproc1g', '/home/dpc/sandbox/sublime-lsp/')
settings = Settings()
settings.log_stderr = True
settings.log_payloads = True
set_debug_logging(True)
set_exception_logging(True)
setup_log()

current_file = None

session = create_session(
    config=config,
    workspace_folders=[workspace],
    env=dict(),
    settings=settings,
    on_post_initialize=on_post_initialize,
    on_pre_initialize=on_pre_initialize,
    on_stderr_log=lambda what: print(what))

def signal_handler(sig, frame):
    session.end()

signal.signal(signal.SIGINT, signal_handler)

# Handlers

def request_handler(res):
    print(res)

def error_handler(error):
    print(error)

# Params

def text_document_position_params():
    return {
        'textDocument': {
            'uri': filename_to_uri(working_file)
        },
        'position': {
            'line': position[0] - 1,
            'character': position[1] - 1
        }
    }

# Util

def print_position():
    with open(working_file, 'r', encoding='latin1') as file:
        lines = file.readlines()
        print(lines[position[0] - 1].rstrip())
        print('{}^'.format(' ' * (position[1] - 1)))

# Requests/notifications

def did_close(path):
    session.client.send_notification(
        Notification.didClose({
            'textDocument': {
                'uri': filename_to_uri(path)
            }
        })
    )

def did_open(path):
    global current_file

    if current_file:
        did_close(current_file)

    with open(path, 'r', encoding='latin1') as file:
        text = file.read()
    session.client.send_notification(
        Notification.didOpen({
            'textDocument': {
                'uri': filename_to_uri(path),
                'languageId': 'php',
                'version': 1,
                'text': text
            }}
        ))
    current_file = path

def workspace_symbol():
    query = input('Symbol: ')
    session.client.execute_request(
        Request.workspaceSymbol({'query': query}),
        request_handler,
        error_handler,
        300)

def document_symbol():
    session.client.execute_request(
        Request.documentSymbols({
            'textDocument': {
                'uri': filename_to_uri(working_file)
            }
        }),
        request_handler,
        error_handler,
        300)

def hover():
    session.client.execute_request(
        Request.hover(text_document_position_params()),
        request_handler,
        error_handler,
        300)

def completion():
    session.client.execute_request(
        Request.complete(text_document_position_params()),
        lambda res: print(json.dumps(res, indent=4)),
        error_handler,
        300)

def references():
    params = text_document_position_params()
    params['context'] = {'includeDeclaration' : False}
    session.client.execute_request(
        Request.references(params),
        lambda res: print(json.dumps(res, indent=4)),
        error_handler,
        10)

def goto_definition():
    session.client.execute_request(
        Request.definition(text_document_position_params()),
        lambda res: print(json.dumps(res, indent=4)),
        error_handler,
        300)

def signature_help():
    session.client.execute_request(
        Request.signatureHelp(text_document_position_params()),
        lambda res: print(json.dumps(res, indent=4)),
        error_handler,
        10)

def set_position():
    line = input('Line: ')
    col = input('Col: ')
    position[0] = int(line)
    position[1] = int(col)
    print('Position set to ', position)
    print_position()

def open_file():
    file = input('File: ')
    print('Opening file {}...'.format(file))
    did_open(file)

def end():
    session.end()
    sys.exit(0)

menu_items=[
    ['c', 'Completion', completion],
    ['h', 'Hover', hover],
    ['s', 'Document symbols', document_symbol],
    ['w', 'Workspace symbols', workspace_symbol],
    ['d', 'Go to definition', goto_definition],
    ['r', 'Find referenes', references],
    ['S', 'Signature help', signature_help],
    ['p', 'Set position', set_position],
    ['o', 'Open file', open_file],
    ['q', 'Exit', end]]

def show_menu():
    print('-' * 70)
    print('Choose an option:')
    for i, item in enumerate(menu_items):
        print('({}) {}'.format(item[0], item[1]))

while True:
    if not initialized:
        time.sleep(1.0)
        continue
    show_menu()
    res = input('---> ')
    for item in menu_items:
        if item[0] == res:
            cmd = item[2]
            cmd()
            break
    else:
        print('Invalid choice!')
