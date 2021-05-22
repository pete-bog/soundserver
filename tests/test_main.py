from unittest import mock
import pytest
import sanic
import os.path
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


@pytest.mark.asyncio
@mock.patch('soundserver.main.aiofiles.open')
@mock.patch('soundserver.main.httpx.AsyncClient.get',
            new_callable=mock.AsyncMock)
async def test_download_remote_file_200(get_mock, open_mock):
    # Arrange
    get_mock.return_value = mock.Mock(status_code=200, content=b'123')
    file_handle_mock = mock.AsyncMock()
    open_mock.return_value.__aenter__.return_value = file_handle_mock
    # Act
    await main.download_remote_file('url', '/path/to/file')
    # Assert
    get_mock.assert_awaited_once_with('url')
    open_mock.assert_called_once_with('/path/to/file', 'wb')
    file_handle_mock.write.assert_awaited_once_with(b'123')


@pytest.mark.asyncio
@mock.patch('soundserver.main.httpx.AsyncClient.get',
            new_callable=mock.AsyncMock)
async def test_download_remote_file_error(get_mock):
    # Arrange
    get_mock.return_value = mock.Mock(status_code=404, text='not found')
    # Act
    with pytest.raises(sanic.exceptions.ServerError):
        await main.download_remote_file('url', '/path/to/file')
    # Assert
    get_mock.assert_awaited_once_with('url')


class TestSoundServer:
    FILE_STORE = '/path/to/store'

    @pytest.fixture
    def soundserver(self) -> main.SoundServer:
        return main.SoundServer(self.FILE_STORE)

    def make_request(self):
        with mock.patch("sanic.Request.receive_body") as receive_body_mock:
            request = sanic.Request(
                b'/test',
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
                transport=mock.Mock(),
                app=mock.Mock(),
                version="1.1")
            body = "url=value1&field2=value2"
            receive_body_mock.return_value = body
        return request

    @pytest.mark.asyncio
    @mock.patch('soundserver.main.download_remote_file')
    @mock.patch('soundserver.main.check_file_extension')
    async def test_add_from_url(self, check_mock, download_mock, soundserver):
        # Arrange
        check_mock.return_value = '.wav'
        # request = self.make_request()
        request = mock.MagicMock(spec=sanic.Request)
        request.form = {"url": "url_val", "name": "name_val"}
        # Act
        result = await soundserver.add_from_url(request)
        # Assert
        check_mock.assert_called_once_with("url_val")
        download_mock.assert_awaited_once_with(
            "url_val", os.path.join(self.FILE_STORE, "name_val.wav"))
        assert isinstance(result, sanic.HTTPResponse)
        assert result.status == 204
