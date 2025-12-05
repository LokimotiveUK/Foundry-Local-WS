#!/usr/bin/env python3
"""
Foundry Proxy - Auto-discovers Foundry Local's dynamic port and proxies requests.

This runs as a Docker service and provides a stable endpoint (port 8080) that
automatically finds and forwards to Foundry's actual dynamic port.
"""

import http.client
import http.server
import json
import logging
import os
import time
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Foundry host from Docker's perspective
FOUNDRY_HOST = os.getenv("FOUNDRY_HOST", "host.docker.internal")

# Cache for port discovery
_cached_port = None
_cache_time = 0
CACHE_TTL = 10  # Re-discover every 10 seconds


def probe_port(host: str, port: int) -> bool:
    """Check if Foundry is responding on a specific port."""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=1)
        conn.request("GET", "/v1/models")
        response = conn.getresponse()
        data = response.read().decode()
        conn.close()
        return "model" in data.lower() or "data" in data.lower()
    except Exception:
        return False


def discover_foundry_port() -> int:
    """Discover Foundry's current dynamic port."""
    global _cached_port, _cache_time

    # Return cached port if valid and still responding
    if _cached_port and (time.time() - _cache_time) < CACHE_TTL:
        if probe_port(FOUNDRY_HOST, _cached_port):
            return _cached_port

    # Check cached port first (might have just expired but still valid)
    if _cached_port and probe_port(FOUNDRY_HOST, _cached_port):
        _cache_time = time.time()
        return _cached_port

    # Probe common Foundry port ranges
    port_ranges = [
        range(50400, 50500),  # Most common range
        range(50000, 50100),
        range(51400, 51500),
        range(62800, 62900),
        range(5273, 5280),    # Default port
        range(57500, 57600),
    ]

    logger.info(f"Scanning for Foundry on {FOUNDRY_HOST}...")

    for port_range in port_ranges:
        for port in port_range:
            if probe_port(FOUNDRY_HOST, port):
                _cached_port = port
                _cache_time = time.time()
                logger.info(f"Found Foundry on port {port}")
                return port

    logger.warning("Foundry not found on any port")
    return None


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that proxies to Foundry."""

    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")

    def send_error_response(self, status: int, message: str):
        """Send a JSON error response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        error = {"error": {"message": message, "type": "proxy_error"}}
        self.wfile.write(json.dumps(error).encode())

    def do_proxy(self):
        """Proxy the request to Foundry."""
        foundry_port = discover_foundry_port()

        if not foundry_port:
            self.send_error_response(503, "Foundry Local is not running or not discoverable")
            return

        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # Connect to Foundry with longer timeout for LLM requests
            conn = http.client.HTTPConnection(FOUNDRY_HOST, foundry_port, timeout=300)

            # Forward headers
            headers = {}
            for key, value in self.headers.items():
                if key.lower() not in ('host', 'connection', 'keep-alive',
                                       'transfer-encoding', 'te', 'trailer',
                                       'upgrade', 'proxy-authorization',
                                       'proxy-authenticate'):
                    headers[key] = value

            # Make request
            conn.request(self.command, self.path, body=body, headers=headers)
            response = conn.getresponse()

            # Forward response
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, value)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Stream response body
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)

            conn.close()

        except ConnectionRefusedError:
            # Port changed, clear cache and retry
            global _cached_port, _cache_time
            old_port = _cached_port
            _cached_port = None
            _cache_time = 0

            new_port = discover_foundry_port()
            if new_port and new_port != old_port:
                logger.info(f"Foundry port changed {old_port} -> {new_port}, retrying")
                self.do_proxy()
            else:
                self.send_error_response(503, f"Cannot connect to Foundry (tried port {old_port})")

        except Exception as e:
            logger.error(f"Proxy error: {e}")
            self.send_error_response(502, f"Proxy error: {str(e)}")

    def do_GET(self):
        self.do_proxy()

    def do_POST(self):
        self.do_proxy()

    def do_PUT(self):
        self.do_proxy()

    def do_DELETE(self):
        self.do_proxy()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()


def main():
    port = int(os.getenv("PROXY_PORT", "8080"))

    # Initial discovery
    foundry_port = discover_foundry_port()
    if foundry_port:
        logger.info(f"Foundry discovered on port {foundry_port}")
    else:
        logger.warning("Foundry not found - will retry on requests")

    # Start server
    server = http.server.HTTPServer(("0.0.0.0", port), ProxyHandler)
    logger.info(f"Foundry Proxy listening on port {port}")
    logger.info(f"Proxying to {FOUNDRY_HOST}:<dynamic-port>")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
