from itertools import zip_longest

import httpx
import httpx2
import pytest

import pook
from tests.unit.interceptors.base import StandardTests

pytestmark = [pytest.mark.pook]


@pytest.fixture(params=[httpx, httpx2], ids=["httpx", "httpx2"])
def lib(request):
    """The httpx-compatible module under test."""
    return request.param


class TestStandardAsyncHttpx(StandardTests):
    is_async = True

    @pytest.fixture(autouse=True)
    def _select_lib(self, lib):
        self.lib = lib

    async def amake_request(self, method, url, content=None, headers=None):
        async with self.lib.AsyncClient() as client:
            response = await client.request(
                method=method, url=url, content=content, headers=headers
            )
            content = await response.aread()
            return response.status_code, content, response.headers


class TestStandardSyncHttpx(StandardTests):
    @pytest.fixture(autouse=True)
    def _select_lib(self, lib):
        self.lib = lib

    def make_request(self, method, url, content=None, headers=None):
        response = self.lib.request(
            method=method, url=url, content=content, headers=headers
        )
        content = response.read()
        return response.status_code, content, response.headers


def test_sync(lib, url_404):
    pook.get(url_404).times(1).reply(200).body("123")

    response = lib.get(url_404)

    assert response.status_code == 200


async def test_async(lib, url_404):
    pook.get(url_404).times(1).reply(200).body(b"async_body").mock

    async with lib.AsyncClient() as client:
        response = await client.get(url_404)

    assert response.status_code == 200
    assert (await response.aread()) == b"async_body"


def test_json(lib, url_404):
    (
        pook.post(url_404)
        .times(1)
        .json({"id": "123abc"})
        .reply(200)
        .json({"title": "123abc title"})
    )

    response = lib.post(url_404, json={"id": "123abc"})

    assert response.status_code == 200
    assert response.json() == {"title": "123abc title"}


@pytest.mark.parametrize("response_method", ("iter_bytes", "iter_raw"))
def test_streaming(lib, url_404, response_method):
    streamed_response = b"streamed response"
    pook.get(url_404).times(1).reply(200).body(streamed_response).mock

    with lib.stream("GET", url_404) as r:
        read_bytes = list(getattr(r, response_method)(chunk_size=1))

    assert len(read_bytes) == len(streamed_response)
    assert b"".join(read_bytes) == streamed_response


def test_redirect_following(lib, url_404):
    urls = [url_404, f"{url_404}/redirected", f"{url_404}/redirected_again"]
    for req, dest in zip_longest(urls, urls[1:], fillvalue=None):
        if not dest:
            pook.get(req).times(1).reply(200).body("found at last")
        else:
            pook.get(req).times(1).reply(302).header("Location", dest)

    response = lib.get(url_404, follow_redirects=True)

    assert response.status_code == 200
    assert response.read() == b"found at last"
