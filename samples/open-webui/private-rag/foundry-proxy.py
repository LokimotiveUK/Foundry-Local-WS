#!/usr/bin/env python3
"""
Foundry Proxy - A fixed-port proxy that forwards to Foundry Local's dynamic port.

This solves the fundamental problem: Foundry Local uses dynamic ports that change
on every restart, but Docker containers need a stable endpoint.

This proxy:
1. Runs on a FIXED port (default: 5999)
2. Auto-detects Foundry's current port on each request
3. Forwards all requests to Foundry
4. Handles port changes transparently

Run this on the HOST (not in Docker):
    python foundry-proxy.py

Then configure Docker containers to use:
    http://host.docker.internal:5999/v1
"""

import argparse
import logging
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import http.client
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Cache the Foundry port with TTL
_cached_port = None
_cache_time = 0
CACHE_TTL = 30  # Re-detect port every 30 seconds


def probe_port(port: int) -> bool:
    """Check if a port has Foundry responding."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/v1/models")
        response = conn.getresponse()
        data = response.read().decode()
        conn.close()
        return "model" in data.lower()  # Foundry returns model list
    except:
        return False


def get_foundry_port() -> int:
    """Detect the current Foundry Local port."""
    global _cached_port, _cache_time

    # Return cached port if still valid AND still responding
    if _cached_port and (time.time() - _cache_time) < CACHE_TTL:
        if probe_port(_cached_port):
            return _cached_port
        else:
            logger.info(f"Cached port {_cached_port} no longer responding, re-detecting...")

    # Method 1: Try the foundry CLI
    try:
        result = subprocess.run(
            ["foundry", "service", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout + result.stderr

        # Look for port in output like "http://127.0.0.1:50402/"
        match = re.search(r'http://[^:]+:(\d+)', output)
        if match:
            port = int(match.group(1))
            if probe_port(port):
                _cached_port = port
                _cache_time = time.time()
                logger.info(f"Detected Foundry port via CLI: {port}")
                return port

    except Exception as e:
        logger.debug(f"CLI detection failed: {e}")

    # Method 2: Probe common Foundry port ranges
    # Foundry typically uses ports in 50000-65000 range
    logger.info("CLI detection failed, probing port ranges...")

    # First, check last known port
    if _cached_port and probe_port(_cached_port):
        _cache_time = time.time()
        logger.info(f"Found Foundry on cached port: {_cached_port}")
        return _cached_port

    # Probe likely port ranges (Foundry seems to use 50000+ range)
    probe_ranges = [
        range(50400, 50500),  # Common range
        range(50000, 50100),
        range(51400, 51500),
        range(5273, 5274),    # Default port
        range(62800, 62900),  # Another observed range
    ]

    for port_range in probe_ranges:
        for port in port_range:
            if probe_port(port):
                _cached_port = port
                _cache_time = time.time()
                logger.info(f"Found Foundry by probing port: {port}")
                return port

    logger.warning("Could not find Foundry on any port")
    return _cached_port  # Return last known port as fallback


class FoundryProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that proxies requests to Foundry Local."""

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_proxy(self):
        """Proxy the request to Foundry."""
        foundry_port = get_foundry_port()

        if not foundry_port:
            self.send_error(503, "Foundry Local is not running")
            return

        try:
            # Parse the path
            path = self.path

            # Read request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # Connect to Foundry
            conn = http.client.HTTPConnection("127.0.0.1", foundry_port, timeout=120)

            # Forward headers (excluding hop-by-hop headers)
            headers = {}
            for key, value in self.headers.items():
                if key.lower() not in ('host', 'connection', 'keep-alive',
                                       'transfer-encoding', 'te', 'trailer',
                                       'upgrade', 'proxy-authorization',
                                       'proxy-authenticate'):
                    headers[key] = value

            # Make the request
            conn.request(self.command, path, body=body, headers=headers)
            response = conn.getresponse()

            # Send response back
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, value)
            self.end_headers()

            # Stream response body
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)

            conn.close()

        except ConnectionRefusedError:
            # Port might have changed, clear cache and retry once
            global _cached_port, _cache_time
            _cached_port = None
            _cache_time = 0

            new_port = get_foundry_port()
            if new_port and new_port != foundry_port:
                logger.info(f"Foundry port changed from {foundry_port} to {new_port}, retrying...")
                self.do_proxy()  # Retry with new port
            else:
                self.send_error(503, f"Cannot connect to Foundry on port {foundry_port}")

        except Exception as e:
            logger.error(f"Proxy error: {e}")
            self.send_error(502, f"Proxy error: {str(e)}")

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
    parser = argparse.ArgumentParser(
        description="Fixed-port proxy for Foundry Local's dynamic port"
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5999,
        help='Port to listen on (default: 5999)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    args = parser.parse_args()

    # Verify Foundry is available
    port = get_foundry_port()
    if port:
        logger.info(f"Foundry Local detected on port {port}")
    else:
        logger.warning("Foundry Local not detected - proxy will wait for it to start")

    # Start server
    server = HTTPServer((args.host, args.port), FoundryProxyHandler)
    logger.info(f"Foundry Proxy listening on http://{args.host}:{args.port}")
    logger.info(f"Configure Docker containers to use: http://host.docker.internal:{args.port}/v1")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
