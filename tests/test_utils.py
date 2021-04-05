import pytest
from unittest import mock

from soundserver import utils


class TestMakeUrlSafeStr:

    def test_spaces_subsituted(self):
        result = utils.make_url_safe_str('i have spaces.txt')
        assert result == 'i-have-spaces.txt'

    @pytest.mark.parametrize('unsafe_char', '&$+,/:;=?@#<>[]{}\\|^%')
    def test_unsafe_chars_removed(self, unsafe_char):
        template = 'abc{0}def{0}.mp3'
        result = utils.make_url_safe_str(template.format(unsafe_char))
        assert result == template.format('')


@pytest.mark.parametrize(
    'url', ['http://localhost/file.txt', '/file/file.txt', 'file.txt'])
def test_extract_filename_from_url(url):
    assert utils.extract_filename_from_url(url) == 'file.txt'
