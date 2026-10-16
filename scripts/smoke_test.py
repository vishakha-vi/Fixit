#!/usr/bin/env python3
"""FixIt smoke test script.

Uses standard library only.
Validates live/local deployment endpoints, latency, security headers, and status codes.
"""

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class SmokeTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.failures = []
        self.cj = http.cookiejar.CookieJar()
        # Custom opener with cookie support and redirect tracking
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def _request(self, path: str, expected_status: int = 200, follow_redirects: bool = True):
        url = f"{self.base_url}{path}"
        start = time.perf_counter()
        headers = {"User-Agent": "FixIt-SmokeTest/1.0"}
        req = urllib.request.Request(url, headers=headers)

        status_code = None
        content = b""
        response_headers = {}

        try:
            with self.opener.open(req, timeout=10) as resp:
                status_code = resp.status
                content = resp.read()
                response_headers = dict(resp.headers)
        except urllib.error.HTTPError as err:
            status_code = err.code
            content = err.read()
            response_headers = dict(err.headers)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"[-] GET {path} FAILED TO CONNECT ({elapsed:.3f}s): {exc}")
            self.failures.append(f"GET {path} connection error: {exc}")
            return None, b"", {}, elapsed

        elapsed = time.perf_counter() - start
        warn_str = " [SLOW > 2s!]" if elapsed > 2.0 else ""
        print(f"[*] GET {path} -> {status_code} ({elapsed:.3f}s){warn_str}")

        if status_code != expected_status:
            self.failures.append(
                f"GET {path} returned status {status_code}, expected {expected_status}"
            )

        return status_code, content, response_headers, elapsed

    def test_healthz(self):
        print("\n--- Testing /healthz ---")
        status, content, _, _ = self._request("/healthz", expected_status=200)
        if status != 200:
            return

        try:
            data = json.loads(content.decode("utf-8"))
        except Exception as exc:
            self.failures.append(f"/healthz response is not valid JSON: {exc}")
            return

        print(f"    Payload: {data}")
        if data.get("db") is not True:
            self.failures.append(f"/healthz db field is not true: {data.get('db')}")
        if "version" not in data:
            self.failures.append("/healthz missing 'version' key")
        if "time" not in data:
            self.failures.append("/healthz missing 'time' key")
        if "demo_mode" not in data:
            self.failures.append("/healthz missing 'demo_mode' key")

    def test_home(self):
        print("\n--- Testing / ---")
        status, content, _, _ = self._request("/", expected_status=200)
        if status == 200:
            text = content.decode("utf-8", errors="replace")
            if "FixIt" not in text:
                self.failures.append("Home page content missing 'FixIt'")

    def test_vendor_asset(self):
        print("\n--- Testing /static/vendor/htmx.min.js ---")
        self._request("/static/vendor/htmx.min.js", expected_status=200)

    def test_login_page(self):
        print("\n--- Testing /accounts/login/ ---")
        self._request("/accounts/login/", expected_status=200)

    def test_missing_page(self):
        print("\n--- Testing /definitely-missing (404 check) ---")
        status, content, headers, _ = self._request("/definitely-missing", expected_status=404)
        if status == 404:
            text = content.decode("utf-8", errors="replace")
            if "Traceback" in text:
                self.failures.append("404 page leaked 'Traceback' text!")
            content_type = headers.get("Content-Type", "")
            if "text/html" not in content_type:
                self.failures.append(f"404 page is not HTML (Content-Type: {content_type})")

    def test_https_security(self):
        if not self.base_url.startswith("https://"):
            print("\n--- Skipping HTTPS redirect/cookie test (base URL is not https) ---")
            return

        print("\n--- Testing HTTPS Redirect and Secure Cookie Flags ---")
        # 1. Check HTTP redirects to HTTPS
        http_url = "http://" + self.base_url[len("https://"):] + "/"
        start = time.perf_counter()
        try:
            # Custom handler without automatic redirect following
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            req = urllib.request.Request(http_url, headers={"User-Agent": "FixIt-SmokeTest/1.0"})
            with opener.open(req, timeout=10) as resp:
                code = resp.status
                loc = resp.headers.get("Location", "")
                elapsed = time.perf_counter() - start
                print(f"[*] GET {http_url} -> {code} (Location: {loc}) ({elapsed:.3f}s)")
                if code not in (301, 302, 307, 308) or not loc.startswith("https://"):
                    self.failures.append(f"HTTP did not redirect to HTTPS (status: {code}, loc: {loc})")
        except urllib.error.HTTPError as err:
            elapsed = time.perf_counter() - start
            loc = err.headers.get("Location", "")
            print(f"[*] GET {http_url} -> {err.code} (Location: {loc}) ({elapsed:.3f}s)")
            if err.code not in (301, 302, 307, 308) or not loc.startswith("https://"):
                self.failures.append(f"HTTP did not redirect to HTTPS (status: {err.code}, loc: {loc})")
        except Exception as exc:
            self.failures.append(f"Failed to check HTTP -> HTTPS redirect: {exc}")

        # 2. Check csrftoken cookie has Secure flag
        _, _, headers, _ = self._request("/accounts/login/", expected_status=200)
        set_cookie = headers.get("Set-Cookie", "")
        if "csrftoken" in set_cookie and "secure" not in set_cookie.lower():
            self.failures.append("csrftoken cookie missing Secure attribute on HTTPS")

    def run(self) -> bool:
        print(f"Starting FixIt smoke test against {self.base_url}...")
        self.test_healthz()
        self.test_home()
        self.test_vendor_asset()
        self.test_login_page()
        self.test_missing_page()
        self.test_https_security()

        print("\n================== SMOKE TEST SUMMARY ==================")
        if self.failures:
            print(f"FAILED ({len(self.failures)} errors detected):")
            for f in self.failures:
                print(f"  [X] {f}")
            return False
        else:
            print("ALL SMOKE CHECKS PASSED.")
            return True


def main():
    parser = argparse.ArgumentParser(description="FixIt Phase 0 Smoke Test")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of FixIt instance (e.g., http://127.0.0.1:8000 or https://fixit.onrender.com)",
    )
    args = parser.parse_args()

    tester = SmokeTester(base_url=args.base_url)
    success = tester.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
