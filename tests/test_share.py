"""Exercise the actual TLS LocalSend sender against a consenting local peer."""

import hashlib
import json
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from mandarin.share import inspect_peer, lan_address, send


class LocalSendTests(unittest.TestCase):
    def test_tls_consent_payload_and_certificate_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key, cert = root / "key.pem", root / "cert.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=Mandarin test",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            source = root / "message.txt"
            source.write_bytes(b"Mandarin private LAN transfer\n" * 100)
            observations = {}

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def reply(self, value, status=200):
                    body = json.dumps(value).encode()
                    self.send_response(status)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self):
                    self.reply({"alias": "Test recipient", "version": "2.0"})

                def do_POST(self):
                    body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    route = urlsplit(self.path).path
                    if route.endswith("prepare-upload"):
                        observations["prepare"] = json.loads(body)
                        self.reply(
                            {
                                "sessionId": "consented",
                                "files": {
                                    identifier: "accepted-token"
                                    for identifier in observations["prepare"]["files"]
                                },
                            }
                        )
                    elif route.endswith("upload"):
                        observations["payload"] = body
                        self.reply({})
                    else:
                        self.reply({}, 404)

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                peer = inspect_peer("127.0.0.1", server.server_port)
                progress = []
                send([source], peer, progress=lambda done, total: progress.append((done, total)))
                self.assertEqual(observations["payload"], source.read_bytes())
                file = next(iter(observations["prepare"]["files"].values()))
                self.assertEqual(file["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(progress[-1], (source.stat().st_size,) * 2)
                observations.clear()
                with self.assertRaisesRegex(ValueError, "certificate changed"):
                    send([source], {**peer, "fingerprint": "0" * 64})
                self.assertFalse(observations, "Unverified recipient received file metadata")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_reject_non_lan_destinations(self):
        for address in ["8.8.8.8", "0.0.0.0", "224.0.0.167", "example.com"]:
            with self.subTest(address=address), self.assertRaises(ValueError):
                lan_address(address)
