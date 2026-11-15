"""Local-network (LAN) helpers: private-origin matching for CORS and LAN IP discovery.

Why this module exists: during the hackathon the API runs on one laptop and
teammates open the frontend from their own devices on the same Wi-Fi. Two
things are needed for that:

1. The API must listen on every network interface (``API_HOST=0.0.0.0``), and
   people need to know which address to type. :func:`get_lan_ip` finds it.
2. Browsers only let a page call the API if the page's *origin* (scheme + host
   + port, e.g. ``http://192.168.1.23:5173``) is allowed by CORS. LAN addresses
   change from network to network, so listing them by hand is fragile.
   :data:`PRIVATE_NETWORK_ORIGIN` matches any origin on a private network instead.

Example:
    >>> bool(PRIVATE_NETWORK_ORIGIN.match("http://192.168.1.23:5173"))
    True
    >>> bool(PRIVATE_NETWORK_ORIGIN.match("https://example.com"))
    False
"""

from __future__ import annotations

import re
import socket

_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"

#: Matches browser origins that point to this computer or to a private (LAN) network.
#:
#: Accepted hosts, with ``http`` or ``https`` and an optional ``:port``:
#:
#: - ``localhost`` and ``127.x.x.x`` (loopback: this same computer);
#: - ``10.x.x.x``, ``172.16.x.x`` – ``172.31.x.x`` and ``192.168.x.x``: the three
#:   private IPv4 ranges reserved by RFC 1918, which home and office routers hand out
#:   (for ``172`` the second number must be 16–31, written as ``1[6-9]|2\d|3[01]``);
#: - ``<name>.local``: mDNS names such as ``my-laptop.local`` (macOS, Linux with Avahi).
#:
#: Public addresses and domains never match, so a random website on the
#: Internet still cannot call the API from a visitor's browser.
PRIVATE_NETWORK_ORIGIN: re.Pattern[str] = re.compile(
    r"^https?://(?:"
    r"localhost"
    rf"|127\.{_OCTET}\.{_OCTET}\.{_OCTET}"
    rf"|10\.{_OCTET}\.{_OCTET}\.{_OCTET}"
    rf"|172\.(?:1[6-9]|2\d|3[01])\.{_OCTET}\.{_OCTET}"
    rf"|192\.168\.{_OCTET}\.{_OCTET}"
    r"|[A-Za-z0-9-]+\.local"
    r")(?::\d{1,5})?$",
    re.IGNORECASE,
)


def get_lan_ip() -> str | None:
    """Return this computer's IPv4 address on the local network, if it has one.

    How: open a UDP socket and ``connect`` it to a private address. For UDP,
    ``connect`` sends no packet; it only asks the operating system which local
    interface would be used to reach that address. ``getsockname()`` then
    returns that interface's IP (e.g. ``192.168.1.23``).

    Why this trick: ``socket.gethostbyname(socket.gethostname())`` often returns
    ``127.0.1.1`` on Linux, which is useless to other devices, and listing the
    interfaces portably would need an extra dependency.

    Returns:
        The LAN IPv4 address, or ``None`` when the computer is not connected to
        any network (then only ``localhost`` works).

    Example:
        >>> ip = get_lan_ip()   # e.g. '192.168.1.23', or None when offline
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            ip = probe.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith("127.") or ip == "0.0.0.0" else ip
