import httpx2

from pook.interceptors._httpx_common import (
    SyncTransportMixin,
    AsyncTransportMixin,
    HttpxInterceptorBase,
)


class SyncTransport(SyncTransportMixin, httpx2.BaseTransport):
    response_cls = httpx2.Response


class AsyncTransport(AsyncTransportMixin, httpx2.AsyncBaseTransport):
    response_cls = httpx2.Response


class Httpx2Interceptor(HttpxInterceptorBase):
    """
    Interceptor for httpx2.

    Intercepts synchronous and asynchronous httpx2 traffic.
    """

    patch_paths = (
        "httpx2.Client._transport_for_url",
        "httpx2.AsyncClient._transport_for_url",
    )
    sync_transport_cls = SyncTransport
    async_transport_cls = AsyncTransport
