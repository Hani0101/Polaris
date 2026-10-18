"""Fetching a public web page for a resource (RS-22), and the address check web mode shares (CH-26).

Polaris runs on the learner's machine, next to its own API and their local
network. A page is fetched only from a public address: every address the host
name resolves to must be global, and the connection goes to the address that
was checked, so a second lookup cannot point it somewhere else. Each redirect
is checked the same way.
"""

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import truststore

MAX_URL_LENGTH = 2048
FETCH_TIMEOUT_SECONDS = 15
MAX_REDIRECTS = 5
USER_AGENT = "Polaris/0.1 (a local study app fetching a page its learner added)"


class FetchRefused(Exception):
    """A page was not fetched. code is one of bad_url, not_public, fetch_failed, too_big."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchedPage:
    url: str
    media_type: str
    charset: str | None
    data: bytes


def bad_url() -> FetchRefused:
    return FetchRefused("bad_url", "That is not a web address. Paste a link that starts with https://.")


def not_public() -> FetchRefused:
    return FetchRefused(
        "not_public",
        "Polaris only fetches public web pages, not addresses on this computer or its network.",
    )


def _parts(url: str) -> tuple[str, str, int]:
    """(scheme, host, port) of an http or https address, or bad_url."""

    if len(url) > MAX_URL_LENGTH:
        raise bad_url()
    try:
        split = urlsplit(url.strip())
        port = split.port
    except ValueError:
        raise bad_url() from None
    scheme = split.scheme.lower()
    host = split.hostname
    if scheme not in ("http", "https") or not host or split.username or split.password:
        raise bad_url()
    return scheme, host, port or (443 if scheme == "https" else 80)


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def public_address(url: str) -> str:
    """The checked address to connect to for a URL. Every address of its host must be public."""

    _scheme, host, port = _parts(url)
    try:
        found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise FetchRefused("fetch_failed", f"Couldn't find {host}. Check the link.") from None
    addresses = [str(info[4][0]) for info in found]
    if not addresses or not all(_is_public(address) for address in addresses):
        raise not_public()
    return addresses[0]


def is_public_url(url: str) -> bool:
    try:
        public_address(url)
    except FetchRefused:
        return False
    return True


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connects to the checked address, and still checks the certificate for the host name.

    The operating system checks the certificate (truststore), as a browser does. Python's
    own store can hold an expired root that fails pages a browser opens.
    """

    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        super().__init__(host, port, timeout=timeout, context=context)
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_page(url: str, max_bytes: int) -> FetchedPage:
    """GET a public page, following up to MAX_REDIRECTS redirects, each one checked."""

    current = url.strip()
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port = _parts(current)
        address = public_address(current)
        split = urlsplit(current)
        path = split.path or "/"
        if split.query:
            path = f"{path}?{split.query}"
        connection_type = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
        connection = connection_type(host, port, address, FETCH_TIMEOUT_SECONDS)
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html, application/pdf, text/plain, image/png, image/jpeg;q=0.8",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise _failed(host)
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise FetchRefused(
                    "fetch_failed",
                    f"{host} answered with error {response.status}. Check the link and try again.",
                )
            declared = response.getheader("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise _too_big(max_bytes)
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise _too_big(max_bytes)
            message = response.msg
            return FetchedPage(
                url=current,
                media_type=message.get_content_type(),
                charset=message.get_content_charset(),
                data=data,
            )
        except FetchRefused:
            raise
        except (OSError, http.client.HTTPException):
            raise _failed(host) from None
        finally:
            connection.close()
    raise FetchRefused("fetch_failed", "That link redirects too many times.")


def _failed(host: str) -> FetchRefused:
    return FetchRefused("fetch_failed", f"Couldn't fetch the page from {host}. Try again later.")


def _too_big(max_bytes: int) -> FetchRefused:
    return FetchRefused("too_big", f"That page is over the {max_bytes // (1024 * 1024)} MB limit.")


_SKIPPED = {"script", "style", "noscript", "template", "svg", "iframe", "nav", "footer", "form"}
_BLOCKS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "li", "main", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
}  # fmt: skip


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skipping = 0
        self._pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag in _SKIPPED:
            self._skipping += 1
        elif tag in _BLOCKS:
            self._pieces.append("\n\n" if tag not in ("br", "li", "tr", "td", "th") else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in _SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag in _BLOCKS:
            self._pieces.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skipping:
            self._pieces.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._pieces).split("\n"))
        joined = "\n".join(lines)
        while "\n\n\n" in joined:
            joined = joined.replace("\n\n\n", "\n\n")
        return joined.strip()


def html_text(data: bytes, charset: str | None = None) -> tuple[str, str]:
    """(title, readable text) of an HTML page. Scripts, styles, and markup are dropped (RS-12)."""

    try:
        markup = data.decode(charset or "utf-8")
    except (LookupError, UnicodeDecodeError):
        markup = data.decode("utf-8", errors="replace")
    parser = _TextParser()
    parser.feed(markup)
    parser.close()
    return " ".join(parser.title.split()), parser.text()
