"""Explicit, certificate-pinned LocalSend v2 LAN sending. No background server."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import mimetypes
import socket
import ssl
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

from .files import file_identity


def lan_address(host: str) -> str:
    address = ipaddress.ip_address(host.strip().strip("[]"))
    if (
        address.is_multicast
        or address.is_unspecified
        or not (address.is_private or address.is_loopback or address.is_link_local)
    ):
        raise ValueError("Choose a device on your local network.")
    return str(address)


class Connection(http.client.HTTPSConnection):
    def __init__(self, host, port=53317, fingerprint=None, timeout=90):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        super().__init__(lan_address(host), port, context=context, timeout=timeout)
        self.expected = fingerprint

    def connect(self):
        super().connect()
        self.fingerprint = hashlib.sha256(self.sock.getpeercert(binary_form=True)).hexdigest()
        if self.expected and self.fingerprint != self.expected:
            self.close()
            raise ValueError(
                "The recipient certificate changed. Verify the device again before sending."
            )


def response_json(connection) -> dict:
    response = connection.getresponse()
    body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("The recipient response is too large.")
    if response.status not in {200, 201, 204}:
        raise ValueError(
            {
                403: "The recipient declined the transfer.",
                409: "The recipient is busy.",
                401: "The recipient requires a PIN.",
            }.get(response.status, f"The recipient returned HTTP {response.status}.")
        )
    return json.loads(body) if body else {}


def inspect_peer(host: str, port: int = 53317) -> dict:
    connection = Connection(host, port, timeout=5)
    try:
        connection.connect()
        certificate = connection.fingerprint
        connection.request("GET", "/api/localsend/v2/info")
        info = response_json(connection)
        return {
            "host": lan_address(host),
            "port": port,
            "alias": str(info.get("alias", "Local device"))[:128],
            "fingerprint": certificate,
        }
    finally:
        connection.close()


def discover(seconds=3) -> list[dict]:
    peers = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 53317))
        sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton("224.0.0.167") + socket.inet_aton("0.0.0.0"),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.settimeout(0.25)
        identifier = uuid.uuid4().hex
        announcement = {
            "alias": "Mandarin",
            "version": "2.0",
            "deviceType": "desktop",
            "fingerprint": identifier,
            "port": 53317,
            "protocol": "https",
            "announce": True,
            "download": False,
        }
        sock.sendto(json.dumps(announcement).encode(), ("224.0.0.167", 53317))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                data, (host, _) = sock.recvfrom(8192)
                value = json.loads(data)
                if (
                    not isinstance(value, dict)
                    or value.get("fingerprint") == identifier
                    or value.get("protocol") != "https"
                ):
                    continue
                port = int(value.get("port", 53317))
                if not 1 <= port <= 65535:
                    continue
                peers[(host, port)] = {
                    "host": lan_address(host),
                    "port": port,
                    "alias": str(value.get("alias", "Local device"))[:128],
                }
            except (socket.timeout, ValueError, TypeError):
                continue
        return list(peers.values())
    finally:
        sock.close()


def send(
    paths: list[Path],
    peer: dict,
    cancel: threading.Event | None = None,
    progress=None,
    pin: str = "",
):
    cancel = cancel or threading.Event()
    progress = progress or (lambda done, total: None)
    if not paths or len(paths) > 1000:
        raise ValueError("Choose between one and 1,000 files.")
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError("Share regular files. Archive folders first.")
    identities = [file_identity(path) for path in paths]
    files = {}
    sources = {}
    for path, identity in zip(paths, identities):
        identifier = uuid.uuid4().hex
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if file_identity(path) != identity:
            raise ValueError("A file changed before sharing.")
        files[identifier] = {
            "id": identifier,
            "fileName": path.name,
            "size": identity[2],
            "fileType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "sha256": digest,
        }
        sources[identifier] = (path, identity)
    connection = Connection(peer["host"], peer["port"], peer["fingerprint"])
    session_id = None
    completed = False
    try:
        query = "?" + urlencode({"pin": pin}) if pin else ""
        body = json.dumps(
            {
                "info": {
                    "alias": "Mandarin",
                    "version": "2.0",
                    "deviceType": "desktop",
                    "fingerprint": uuid.uuid4().hex,
                    "port": 53317,
                    "protocol": "https",
                    "download": False,
                },
                "files": files,
            }
        ).encode()
        connection.request(
            "POST",
            "/api/localsend/v2/prepare-upload" + query,
            body,
            {"Content-Type": "application/json"},
        )
        accepted = response_json(connection)
        session_id = accepted.get("sessionId")
        tokens = accepted.get("files", {})
        if not isinstance(session_id, str) or not isinstance(tokens, dict):
            raise ValueError("The recipient did not accept a valid session.")
        if set(tokens) != set(files):
            raise ValueError(
                "The recipient did not accept every selected file. No file data was sent."
            )
        total = sum(value[1][2] for value in sources.values())
        done = 0
        for identifier, token in tokens.items():
            path, identity = sources[identifier]
            if cancel.is_set():
                raise ValueError("Sharing canceled.")
            if file_identity(path) != identity:
                raise ValueError("A source file changed before transfer.")
            connection.close()
            connection = Connection(peer["host"], peer["port"], peer["fingerprint"])
            connection.putrequest(
                "POST",
                "/api/localsend/v2/upload?"
                + urlencode({"sessionId": session_id, "fileId": identifier, "token": token}),
            )
            connection.putheader("Content-Type", "application/octet-stream")
            connection.putheader("Content-Length", str(identity[2]))
            connection.endheaders()
            with path.open("rb") as handle:
                remaining = identity[2]
                while remaining:
                    block = handle.read(min(65536, remaining))
                    if not block:
                        raise ValueError("The file changed during transfer.")
                    if cancel.is_set():
                        raise ValueError("Sharing canceled.")
                    connection.send(block)
                    remaining -= len(block)
                    done += len(block)
                    progress(done, total)
            response_json(connection)
            if file_identity(path) != identity:
                raise ValueError("The file changed during transfer. Check the received copy.")
        completed = True
    finally:
        if not completed and session_id:
            try:
                connection.close()
                connection = Connection(peer["host"], peer["port"], peer["fingerprint"], timeout=3)
                connection.request(
                    "POST",
                    "/api/localsend/v2/cancel?" + urlencode({"sessionId": session_id}),
                )
                response_json(connection)
            except Exception:
                pass
        connection.close()
