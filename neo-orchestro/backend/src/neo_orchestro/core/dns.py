"""DNS resolver factory shared by the scope engine and the DNS engine."""

from collections.abc import Sequence

import dns.resolver


def build_resolver(nameservers: Sequence[str] = ()) -> dns.resolver.Resolver:
    """A dnspython resolver.

    With explicit ``nameservers`` it uses *only* those (nothing is read from the host's
    ``resolv.conf``): point workers at a trusted resolver you control (ADR 0004). Without,
    it follows the system configuration.
    """
    if not nameservers:
        return dns.resolver.Resolver()
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = list(nameservers)
    return resolver
