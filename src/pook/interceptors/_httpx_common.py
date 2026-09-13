import asyncio
from collections.abc import Callable
from http.client import responses as http_reasons
from typing import Any, ClassVar
from unittest import mock

from pook.interceptors.base import BaseInterceptor
from pook.request import Request
from pook.response import Response

HttpxClient = Any
TransportForUrl = Callable[[Any, Any], Any]


class HttpxInterceptorBase(BaseInterceptor):
    """
    Base class for httpx and httpx2 interceptors.

    Intercepts synchronous and asynchronous httpx and httpx2 traffic.
    """

    patch_paths: ClassVar[tuple[str, ...]]
    sync_transport_cls: ClassVar[type]
    async_transport_cls: ClassVar[type]

    def _patch(self, path, transport_cls):
        def handler(client, *_):
            return transport_cls(self, client, _original_transport_for_url)

        try:
            patcher = mock.patch(path, handler)
            _original_transport_for_url = patcher.get_original()[0]  # type: ignore[var-annotated]
            patcher.start()
        except Exception:
            pass
        else:
            self.patchers.append(patcher)

    def activate(self):
        sync_path, async_path = self.patch_paths
        self._patch(sync_path, self.sync_transport_cls)
        self._patch(async_path, self.async_transport_cls)

    def disable(self):
        [patch.stop() for patch in self.patchers]


class MockedTransportMixin:
    response_cls: ClassVar[type]
    _original_transport_for_url: TransportForUrl

    def __init__(
        self,
        interceptor: HttpxInterceptorBase,
        client: HttpxClient,
        _original_transport_for_url: TransportForUrl,
    ):
        self._interceptor = interceptor
        self._client = client
        self._original_transport_for_url = _original_transport_for_url

    @staticmethod
    def _build_pook_request(httpx_request) -> Request:
        req = Request(httpx_request.method)
        req.url = str(httpx_request.url)
        req.headers = httpx_request.headers

        return req

    def _build_response(self, httpx_request, mock_response: Response):
        res = self.response_cls(
            status_code=mock_response._status,
            headers=mock_response._headers,
            content=mock_response._body,
            extensions={
                # TODO: Add HTTP2 response support
                "http_version": b"HTTP/1.1",
                "reason_phrase": http_reasons.get(mock_response._status, "").encode(
                    "ascii"
                ),
                "network_stream": None,
            },
            request=httpx_request,
        )

        # Allow to read the response on client side
        res.is_stream_consumed = False
        res.is_closed = False
        if hasattr(res, "_content"):
            del res._content

        return res


class AsyncTransportMixin(MockedTransportMixin):
    async def _get_pook_request(self, httpx_request) -> Request:
        req = self._build_pook_request(httpx_request)
        req.body = await httpx_request.aread()
        return req

    async def handle_async_request(self, request):
        pook_request = await self._get_pook_request(request)

        mock = self._interceptor.engine.match(pook_request)

        if not mock:
            transport = self._original_transport_for_url(self._client, request.url)
            return await transport.handle_async_request(request)

        if mock._delay:
            await asyncio.sleep(mock._delay / 1000)

        return self._build_response(request, mock._response)


class SyncTransportMixin(MockedTransportMixin):
    def _get_pook_request(self, httpx_request):
        req = self._build_pook_request(httpx_request)
        req.body = httpx_request.read()
        return req

    def handle_request(self, request):
        pook_request = self._get_pook_request(request)

        mock = self._interceptor.engine.match(pook_request)

        if not mock:
            transport = self._original_transport_for_url(self._client, request.url)
            return transport.handle_request(request)

        return self._build_response(request, mock._response)
