"""Minimal DNS server for the end-to-end smoke test (UDP, authoritative, no recursion).

Usage: ``python fake_dns.py RECORDS.json [ADDRESS] [PORT]``

``RECORDS.json`` maps lower-case names to ``{"A": [...], "AAAA": [...], "TXT": [...],
"MX": [...], "NS": [...]}``. The file is re-read on *every* query, so a test can change an
answer while the stack runs (DNS-rebinding simulation). Unknown names answer NXDOMAIN.
Every query is logged to stdout as ``query <name> <type>`` so a test can prove which names
were (and were not) looked up.
"""

import json
import socket
import sys
from pathlib import Path

import dns.flags
import dns.message
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.rrset

TTL = 0  # never cached: rebinding must be visible immediately


def build_answer(query: dns.message.Message, records: dict[str, dict[str, list[str]]]):
    response = dns.message.make_response(query)
    response.flags |= dns.flags.AA
    if not query.question:
        response.set_rcode(dns.rcode.FORMERR)
        return response
    question = query.question[0]
    name = question.name.to_text(omit_final_dot=True).lower()
    rtype = dns.rdatatype.to_text(question.rdtype)
    zone = records.get(name)
    if zone is None:
        response.set_rcode(dns.rcode.NXDOMAIN)
        return response
    values = list(zone.get(rtype, []))
    if rtype == "TXT":
        values = [f'"{value}"' for value in values]
    if values:
        response.answer.append(
            dns.rrset.from_text_list(question.name, TTL, dns.rdataclass.IN, question.rdtype, values)
        )
    return response


def main() -> int:
    records_path = Path(sys.argv[1])
    address = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.77"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 53
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((address, port))
    print(f"fake-dns listening on {address}:{port}", flush=True)
    while True:
        data, peer = sock.recvfrom(4096)
        try:
            query = dns.message.from_wire(data)
        except Exception:  # malformed packet: ignore
            continue
        try:
            records = json.loads(records_path.read_text())
            response = build_answer(query, records)
        except Exception:  # unreadable records file: SERVFAIL, like a broken upstream
            response = dns.message.make_response(query)
            response.set_rcode(dns.rcode.SERVFAIL)
        if query.question:
            q = query.question[0]
            print(
                f"query {q.name.to_text(omit_final_dot=True).lower()} "
                f"{dns.rdatatype.to_text(q.rdtype)}",
                flush=True,
            )
        sock.sendto(response.to_wire(), peer)


if __name__ == "__main__":
    raise SystemExit(main())
