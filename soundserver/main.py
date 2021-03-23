import functools
import os
import os.path
import tempfile
import urllib
from typing import Tuple

import bottle
import requests

from . import cli

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PERMITTED_TYPES = ('.wav', '.mp3')


def replace_url_path(url: str, new_path: str) -> str:
    parsed = urllib.parse.urlparse(url)._asdict()
    parsed['path'] = new_path
    new_url = urllib.parse.ParseResult(**parsed)
    return urllib.parse.urlunparse(new_url)


def check_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if ext not in PERMITTED_TYPES:
        raise bottle.HTTPError(
            status=400,
            body='File extension not allowed. Must be one of: {}.'.format(
                ', '.join(PERMITTED_TYPES)))
    return ext


class SoundServer:

    def __init__(self, file_store_dir):
        self.file_store = file_store_dir
        self.app = bottle.Bottle()
        self.app.route('/', 'GET',
                       functools.partial(bottle.redirect, "static/index.html"))
        # Static application files (html, css, js, ...)
        self.app.route('/static/<filename:path>', 'GET',
                       functools.partial(bottle.static_file, root=STATIC_DIR))
        self.app.route('/files', 'GET', self.get_file_list)
        # Stored non-application files
        self.app.route('/files/<filename:path>', 'GET', self.get_file)
        self.app.route('/files/upload', 'POST', self.upload_file)
        self.app.route('/files/add-from-url', 'POST', self.add_from_url)

    def get_file_list(self):
        catalog = {'files': []}
        for filename in os.listdir(self.file_store):
            url = replace_url_path(str(bottle.request.url),
                                   f'/static/{filename}')
            catalog['files'].append({
                'name': os.path.splitext(filename)[0],
                'url': url
            })
        return catalog

    def get_file(self, filename):
        return bottle.static_file(filename, root=self.file_store)

    def upload_file(self):
        upload = bottle.request.files['upload']
        check_file_extension(upload)
        upload.save(self.file_store)  # appends upload.filename automatically
        return 'ok'

    def add_from_url(self):
        ext = check_file_extension(bottle.request.forms["url"])
        filename = os.path.join(self.file_store,
                                bottle.request.forms["name"] + ext)
        with open(filename, 'wb') as fp:
            response = requests.get(bottle.request.forms["url"])
            fp.write(response.content)
        return 'ok'

    def run(self, *args, **kwargs):
        self.app.run(*args, **kwargs)


def main():
    args = cli.parse_args()
    sound_server = SoundServer(args.store)
    sound_server.run(server='wsgiref' if args.dev_mode else 'tornado',
                     host=args.host,
                     port=args.port,
                     reloader=args.dev_mode)
