import functools
import os
import os.path
from typing import Tuple
import urllib
import bottle

from . import cli

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PERMITTED_TYPES = ('.wav', '.mp3')


def split_filename(filename: str) -> Tuple[str, str]:
    if '.' not in filename:
        return filename
    rev_filename = list(reversed(filename))
    final_dot_index = len(filename) - 1 - rev_filename.index('.')
    return filename[:final_dot_index], filename[:final_dot_index]


def replace_url_path(url: str, new_path: str) -> str:
    parsed = urllib.parse.urlparse(url)._asdict()
    parsed['path'] = new_path
    new_url = urllib.parse.ParseResult(**parsed)
    return urllib.parse.urlunparse(new_url)


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
        _, ext = os.path.splitext(upload.filename)
        if ext not in PERMITTED_TYPES:
            return 'File extension not allowed. Must be one of: {}.'\
                .format(', '.join(PERMITTED_TYPES))

        upload.save(self.file_store)  # appends upload.filename automatically
        return 'OK'

    def run(self, *args, **kwargs):
        self.app.run(*args, **kwargs)


def main():
    args = cli.parse_args()
    sound_server = SoundServer(args.store)
    sound_server.run(server='wsgiref' if args.dev_mode else 'tornado',
                     host=args.host,
                     port=args.port,
                     reloader=args.dev_mode)
