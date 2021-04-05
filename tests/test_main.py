from unittest import mock
import pytest
from soundserver import main


@mock.patch('soundserver.main.utils.extract_filename_from_url',
            mock.Mock(return_value='file.txt'))
@mock.patch('soundserver.main.utils.make_url_safe_str',
            mock.Mock(return_value='file.txt'))
def test_make_sound_name_url():
    url = 'http://localhost/file.txt'
    short, full = main.make_sound_name(url)
    assert short == 'file'
    assert full == 'file.txt'