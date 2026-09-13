import httpx

from pook.interceptors._httpx_common import (
    SyncTransportMixin,
    AsyncTransportMixin,
    HttpxInterceptorBase,
)


class SyncTransport(SyncTransportMixin, httpx.BaseTransport):
    response_cls = httpx.Response


class AsyncTransport(AsyncTransportMixin, httpx.AsyncBaseTransport):
    response_cls = httpx.Response


class HttpxInterceptor(HttpxInterceptorBase):
    """
    Interceptor for httpx.

    Intercepts synchronous and asynchronous httpx traffic.
    """

    patch_paths = (
        "httpx.Client._transport_for_url",
        "httpx.AsyncClient._transport_for_url",
    )
    sync_transport_cls = SyncTransport
    async_transport_cls = AsyncTransport
