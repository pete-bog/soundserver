import json
import os
import os.path
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import aiofiles
import sanic
import fuzzywuzzy.process
import httpx

from sanic.log import logger

from . import cli, utils

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
THIRD_PARTY_DIR = os.path.join(os.path.dirname(__file__), "thirdparty")
PERMITTED_TYPES = ('.wav', '.mp3')
PERMITTED_URL_CHARS = re.compile(r'[A-Za-z0-9\-_~]')
DEFAULT_SEARCH_LIMIT = 5


def check_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if ext not in PERMITTED_TYPES:
        raise sanic.exceptions.InvalidUsage(
            'File extension not allowed. Must be one of: {}.'.format(
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


async def download_remote_file(url, save_as):
    logger.info("Downloading '%s' to '%s'", url, save_as)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code == 200:
        async with aiofiles.open(save_as, "wb") as fp:
            await fp.write(response.content)
    else:
        raise sanic.exceptions.ServerError(
            f"There was an error getting the url {url}: {response.text}")


def find_closest_matches(search_term,
                         choices,
                         limit=5) -> List[Tuple[str, int]]:
    logger.info("Searching for %d similar matches to '%s'", limit, search_term)
    matches = fuzzywuzzy.process.extract(search_term, choices, limit=limit)
    logger.info("Found matches: %s", matches)
    return matches


async def redirect_home(_):
    return sanic.response.redirect("/static/index.html")


class SoundServer:
    MAP_INTERVAL = timedelta(minutes=5)

    def __init__(self, file_store_dir: str):
        self.file_store = file_store_dir
        self.app = sanic.Sanic(__package__)
        # Static files
        self.app.static("/static", STATIC_DIR)
        # Routes
        self.app.add_route(redirect_home, "/")
        self.app.add_route(self.get_file_list, "/files")
        self.app.add_route(self.get_file, "/files/get/<filename:path>")
        self.app.add_route(self.search, "/files/search")
        self.app.add_route(self.lucky, "/files/lucky")
        self.app.add_route(self.upload_file, "/files/upload", methods=["POST"])
        self.app.add_route(self.add_from_url,
                           "/files/add-from-url",
                           methods=["POST"])
        # Start up task
        self.app.add_task(self.on_start_up)

        self.all_file_names = set()
        self.all_files = []
        self.last_map_time = None

    async def on_start_up(self, _) -> None:
        # Build initial map on start-up
        self.build_file_maps()

    def build_file_maps(self) -> Dict:
        self.all_files = []
        self.all_file_names = set()
        # Local files
        for filename in os.listdir(self.file_store):
            name, full_name = make_sound_name(filename)
            logger.debug("Adding local file '%s' to map", name)
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
                    logger.debug(
                        "File named '%s' already exists in map, not adding "
                        "to map", name)
                else:
                    self.all_files.append({
                        'name': name,
                        'full_name': full_name,
                        'remote_url': entry['url'],
                    })
                    self.all_file_names.add(full_name)
        logger.debug("Added %d sounds to map", len(self.all_files))

        # Record when we build this map
        self.last_map_time = datetime.utcnow()
        logger.debug('Successfully built map at %s', self.last_map_time)
        return self.all_files

    def enriched_file_map(self, request_url: str) -> Dict:
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
                str(request_url),
                '/files/get/{}'.format(fmap['files'][i]['full_name']))
        return fmap

    async def search(self, request: sanic.Request) -> sanic.HTTPResponse:
        search_term = request.args.get('search')
        if 'limit' in request.args:
            limit = int(request.args.get('limit'))
        else:
            limit = DEFAULT_SEARCH_LIMIT

        matches = find_closest_matches(search_term,
                                       self.all_file_names,
                                       limit=limit)
        results = {'files': []}
        for x in self.all_files:
            if x['full_name'] in (m[0] for m in matches):
                results['files'].append(x)
        return sanic.response.json(results)

    async def lucky(self, request: sanic.Request) -> sanic.HTTPResponse:
        search_term = request.args.get("search")
        matches = find_closest_matches(search_term,
                                       self.all_file_names,
                                       limit=1)
        if matches:
            for x in self.all_files:
                if x['full_name'] == matches[0][0]:
                    logger.info("Redirecting client to file '%s'",
                                x['full_name'])
                    return sanic.response.redirect("/files/get/{}".format(
                        x['full_name']))
        raise sanic.exceptions.NotFound("u r unlucki")

    async def get_file_list(self, request: sanic.Request) -> sanic.HTTPResponse:
        # Build a fresh map, if we haven't built it recently
        if self.last_map_time and \
                datetime.utcnow() - self.last_map_time >= self.MAP_INTERVAL:
            self.build_file_maps()

        # Return the enriched copy
        enriched = self.enriched_file_map(request.url)
        return sanic.response.json(enriched)

    def get_data_for_filename(self, filename: str) -> Dict:
        if filename in self.all_file_names:
            for x in self.all_files:
                if x['full_name'] == filename:
                    return x
        raise FileNotFoundError

    async def get_file(self, request: sanic.Request,
                       filename: str) -> sanic.HTTPResponse:
        try:
            data = self.get_data_for_filename(filename)
        except FileNotFoundError:
            raise sanic.exceptions.FileNotFound(
                "File not found", filename,
                "/files/get/{}".format(filename)) from None

        if 'remote_url' in data:
            # This is a remote file, so download & save it now
            logger.info("'%s' is a non-local file, getting it from remote",
                        filename)
            await download_remote_file(
                data['remote_url'],
                os.path.join(self.file_store, data['full_name']))
            # Rebuild the filemap
            self.build_file_maps()

        # Return the file that is now guaranteed to exist in the file store
        logger.info("Serving local file '%s'", filename)
        abs_path = os.path.join(self.file_store, filename)
        return await sanic.response.file(abs_path)

    async def upload_file(self, request: sanic.Request) -> sanic.HTTPResponse:
        upload = request.files['upload']
        check_file_extension(upload)
        save_as = os.path.join(self.file_store, upload.name)
        async with aiofiles.open(save_as, 'wb') as fp:
            await fp.write(upload.body)
        return sanic.response.text('ok')

    async def add_from_url(self, request: sanic.Request) -> sanic.HTTPResponse:
        ext = check_file_extension(request.form["url"])
        save_as = os.path.join(self.file_store, request.form["name"] + ext)
        await download_remote_file(request.form["url"], save_as)

        return sanic.response.empty()

    def run(self, *args, **kwargs):
        self.app.run(*args, **kwargs)


def main():
    args = cli.parse_args()
    sound_server = SoundServer(args.store)
    sound_server.run(host=args.host,
                     port=args.port,
                     debug=args.dev_mode,
                     access_log=args.dev_mode)
