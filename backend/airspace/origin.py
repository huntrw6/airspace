from urllib.parse import urlsplit


def origin_is_allowed(
    origin: str | None,
    public_url: str,
    request_host: str | None,
    forwarded_host: str | None = None,
    trust_forwarded: bool = False,
) -> bool:
    if not origin:
        return True
    origin_host = urlsplit(origin).netloc.casefold()
    allowed = {urlsplit(public_url).netloc.casefold()}
    if request_host:
        allowed.add(request_host.casefold())
    if trust_forwarded and forwarded_host:
        allowed.add(forwarded_host.split(",")[-1].strip().casefold())
    return bool(origin_host) and origin_host in allowed
