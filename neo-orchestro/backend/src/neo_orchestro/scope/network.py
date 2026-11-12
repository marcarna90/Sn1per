"""IP address normalisation and classification."""

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)

from neo_orchestro.scope.types import IpClass

type IPAddress = IPv4Address | IPv6Address
type IPNetwork = IPv4Network | IPv6Network

_NAT64 = IPv6Network("64:ff9b::/96")

# Instance-metadata endpoints that are NOT link-local (169.254.169.254 already is).
_METADATA_ADDRESSES = frozenset(
    ip_address(a)
    for a in ("169.254.169.254", "169.254.170.2", "fd00:ec2::254", "100.100.100.200", "192.0.0.192")
)

# Networks no scope entry may overlap.
HARD_DENIED_NETWORKS: tuple[IPNetwork, ...] = tuple(
    ip_network(n)
    for n in (
        "0.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "fe80::/10",
        "ff00::/8",
    )
)


def normalise_ip(ip: IPAddress) -> IPAddress:
    """Canonical form used for rule matching and pinning: IPv4-mapped IPv6 → IPv4."""
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _embedded_ipv4(ip: IPv6Address) -> IPv4Address | None:
    """IPv4 embedded in transition formats (6to4, NAT64) that could smuggle a denied address."""
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in _NAT64:
        return IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def classify_ip(ip: IPAddress) -> IpClass:
    """Classify an address. Looks *through* mapped/6to4/NAT64 so a denied IPv4 cannot hide."""
    ip = normalise_ip(ip)
    if isinstance(ip, IPv6Address):
        embedded = _embedded_ipv4(ip)
        if embedded is not None:
            inner = classify_ip(embedded)
            if inner is not IpClass.public:
                return inner
    if ip.is_loopback:
        return IpClass.loopback
    if ip.is_link_local:
        return IpClass.link_local
    if ip.is_unspecified:
        return IpClass.unspecified
    if ip.is_multicast:
        return IpClass.multicast
    if ip.is_reserved:
        return IpClass.reserved
    if ip in _METADATA_ADDRESSES:
        return IpClass.metadata
    if ip.is_global:
        return IpClass.public
    return IpClass.private


def overlaps_hard_denied(network: IPNetwork) -> bool:
    """True if the network touches a never-scannable range or a metadata address."""
    for denied in HARD_DENIED_NETWORKS:
        if denied.version == network.version and network.overlaps(denied):
            return True
    return any(addr.version == network.version and addr in network for addr in _METADATA_ADDRESSES)
