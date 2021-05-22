"""Utility methods for soundserver"""
import os
import os.path

import re
import logging
import urllib

import httpx

LOG = logging.getLogger(__name__)

PERMITTED_URL_CHARS = re.compile(r'[A-Za-z0-9\-_~\.]')


def replace_url_path(url: str, new_path: str) -> str:
    """Swap the path section of a url (eg. localhost:8080)"""
    parsed = urllib.parse.urlparse(url)._asdict()
    parsed['path'] = new_path
    new_url = urllib.parse.ParseResult(**parsed)
    return urllib.parse.urlunparse(new_url)


def extract_filename_from_url(url: str) -> str:
    """Given a url to a static file, return just the filename
    Eg. web.site/files/123.txt -> 123.txt
    """
    parsed = urllib.parse.urlparse(url)
    return parsed.path.split("/")[-1]


def make_url_safe_str(input_str: str) -> str:
    """Make the supplied name URL safe by excluding/replacing characters"""
    safe = ""
    for char in input_str:
        if char == " ":
            # change spaces to dashes
            safe += "-"
        elif PERMITTED_URL_CHARS.match(char):
            # only add permitted chars, ignore anything else
            safe += char
    return safe


def remove_file_ext(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    return name.rstrip(".")


def get_file_ext(filename: str) -> str:
    return os.path.splitext(filename)[1]
