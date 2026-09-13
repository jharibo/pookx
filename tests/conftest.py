from wsgiref.simple_server import make_server

import falcon

import threading

import pytest

import pook


def pytest_configure(config: pytest.Config):
    config.addinivalue_line(
        "markers",
        "pook(allow_pending_mocks, start_active): run the test inside a pook engine "
        "and verify that every registered mock was used",
    )


@pytest.fixture(autouse=True)
def _pook_marker(request: pytest.FixtureRequest):
    """
    Implements ``@pytest.mark.pook`` for this test suite.

    Marked tests run inside ``pook.use()``. After the test, the engine must
    have at least one registered mock, and every mock must have been matched
    unless ``allow_pending_mocks=True``. ``start_active=False`` leaves the
    engine disabled so the test can enable it itself.
    """
    marker = request.node.get_closest_marker("pook")
    if marker is None:
        yield
        return

    allow_pending_mocks = marker.kwargs.get("allow_pending_mocks", False)
    start_active = marker.kwargs.get("start_active", True)

    with pook.use() as engine:
        if not start_active:
            engine.disable()

        yield

        assert (
            engine.mocks
        ), "The test is marked with @pytest.mark.pook but registered no mocks."
        if not allow_pending_mocks:
            assert engine.isdone(), (
                "Mocks left unused after the test. Pass allow_pending_mocks=True "
                f"to the marker if that is intentional. Pending: {engine.pending_mocks()}"
            )

    assert not engine.isactive()


class HttpbinLikeResource:
    def on_get_status(self, req: falcon.Request, resp: falcon.Response, status: int):
        resp.set_header("x-pook-httpbinlike", "")
        resp.status = status

    on_post_status = on_get_status


class HttpbinLike:
    def __init__(self, schema: str, host: str):
        self.schema = schema
        self.host = host
        self.url = schema + host

    def __add__(self, value):
        return self.url + value


@pytest.fixture(scope="session")
def local_responder():
    app = falcon.App()
    resource = HttpbinLikeResource()
    app.add_route("/status/{status:int}", resource, suffix="status")

    with make_server("127.0.0.1", 8080, app) as httpd:

        def run():
            httpd.serve_forever()

        thread = threading.Thread(target=run)
        thread.start()
        yield HttpbinLike("http://", "127.0.0.1:8080")
        httpd.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def url_404(local_responder):
    """404 httpbin URL.

    Useful in tests if pook is configured to reply 200, and the status is checked.
    If pook does not match the request (and if that was the intended behaviour)
    then the 404 status code makes that obvious!"""
    return local_responder + "/status/404"


@pytest.fixture
def url_401(local_responder):
    return local_responder + "/status/401"


@pytest.fixture
def url_500(local_responder):
    return local_responder + "/status/500"
