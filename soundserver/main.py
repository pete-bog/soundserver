import functools
import os
import os.path
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple
import bottle
import requests

from . import cli, utils

LOG = logging.getLogger(__name__)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
THIRD_PARTY_DIR = os.path.join(os.path.dirname(__file__), "thirdparty")
PERMITTED_TYPES = ('.wav', '.mp3')
PERMITTED_URL_CHARS = re.compile(r'[A-Za-z0-9\-_~]')


def check_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if ext not in PERMITTED_TYPES:
        raise bottle.HTTPError(
            status=400,
            body='File extension not allowed. Must be one of: {}.'.format(
                ', '.join(PERMITTED_TYPES)))
    return ext


def make_sound_name(url, name=None) -> Tuple[str, str]:
    if name is None:
        name = utils.extract_filename_from_url(url)
    url_safe_name = utils.make_url_safe_str(name)
    ext = utils.get_file_ext(url)
    # Return the extensionless name & the name with extension
    # eg. my-sound, my-sound.mp3
    short_name = url_safe_name
    if short_name.endswith(ext):
        short_name = short_name[:-len(ext)]
    return short_name, short_name + ext


def download_remote_file(url, save_as):
    LOG.info("Downloading '%s' to '%s'", url, save_as)
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_as, "wb") as fp:
            fp.write(response.content)
    else:
        raise bottle.HTTPError(
            500, f"There was an error getting the url {url}: {response.text}")


class SoundServer:
    MAP_INTERVAL = timedelta(minutes=5)

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

        self.all_file_names = set()
        self.all_files = []
        self.last_map_time = None

    def build_file_maps(self):
        self.all_files = []
        self.all_file_names = set()
        # Local files
        for filename in os.listdir(self.file_store):
            name, full_name = make_sound_name(filename)
            LOG.debug("Adding local file '%s' to map", name)
            self.all_files.append({'name': name, 'full_name': full_name})
            self.all_file_names.add(full_name)

        # Third party
        for third_party_file in os.listdir(THIRD_PARTY_DIR):
            with open(os.path.join(THIRD_PARTY_DIR, third_party_file)) as fp:
                sounds = json.load(fp)
            for entry in sounds:
                name, full_name = make_sound_name(entry['url'],
                                                  name=entry['name'])
                if name in self.all_file_names:
                    LOG.debug(
                        "File named '%s' already exists in map, not adding "
                        "to map", name)
                else:
                    self.all_files.append({
                        'name': name,
                        'full_name': full_name,
                        'remote_url': entry['url'],
                    })
                    self.all_file_names.add(full_name)
        LOG.debug("Added %d sounds to map", len(self.all_files))

        # Record when we build this map
        self.last_map_time = datetime.utcnow()
        LOG.debug('Successfully built map at %s', self.last_map_time)
        return self.all_files

    @property
    def enriched_file_map(self) -> Dict:
        """
        Create a JSON-compatible list of files, with the urls patched to
        the requester's hostname. Eg. if the client requested localhost, patch
        all urls to localhost/files/file.wav
        This fn also overrides any 'remote' urls with local ones that are
        handled by get_file.
        """
        fmap = {'files': self.all_files[:]}
        for i in range(len(fmap['files'])):
            fmap['files'][i]['url'] = utils.replace_url_path(
                str(bottle.request.url),
                '/files/{}'.format(fmap['files'][i]['full_name']))
        return fmap

    def get_file_list(self):
        # Return the cached map, if we built it recently
        if self.last_map_time and \
                datetime.utcnow() - self.last_map_time < self.MAP_INTERVAL:
            return self.enriched_file_map

        # Otherwise build the map now
        self.build_file_maps()
        # Return the enriched copy
        return self.enriched_file_map

    def get_data_for_filename(self, filename):
        if filename in self.all_file_names:
            for x in self.all_files:
                if x['full_name'] == filename:
                    return x
        raise FileNotFoundError

    def get_file(self, filename):
        try:
            data = self.get_data_for_filename(filename)
        except FileNotFoundError:
            raise bottle.HTTPError(404, "File not found") from None

        if 'remote_url' in data:
            # This is a remote file, so download & save it now
            LOG.info("'%s' is a non-local file, getting it from remote",
                     filename)
            download_remote_file(
                data['remote_url'],
                os.path.join(self.file_store, data['full_name']))
            # Rebuild the filemap
            self.build_file_maps()

        # Return the file that is guaranteed to exist in the file store
        LOG.info("Serving local file '%s'", filename)
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
        # Build initial map on start-up
        self.build_file_maps()
        self.app.run(*args, **kwargs)


def main():
    args = cli.parse_args()
    LOG.setLevel(logging.DEBUG if args.dev_mode else logging.INFO)
    sound_server = SoundServer(args.store)
    sound_server.run(server='wsgiref' if args.dev_mode else 'tornado',
                     host=args.host,
                     port=args.port,
                     reloader=args.dev_mode)
