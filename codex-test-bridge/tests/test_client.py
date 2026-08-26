import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import client


class Response:
    def __init__(self, body, status=200):
        self.body = body.encode("utf-8")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.timeout = None

    def open(self, _request, timeout):
        self.timeout = timeout
        if self.error:
            raise self.error
        return self.response


class ClientTests(unittest.TestCase):
    def test_request_uses_configured_timeout(self):
        opener = Opener(Response('{"ok": true}'))
        old_timeout = client.REQUEST_TIMEOUT
        client.REQUEST_TIMEOUT = 12.5
        try:
            with patch("client.urllib.request.build_opener", return_value=opener):
                result = client.request_json("http://localhost/health")
        finally:
            client.REQUEST_TIMEOUT = old_timeout
        self.assertTrue(result["ok"])
        self.assertEqual(opener.timeout, 12.5)

    def test_http_json_error_is_returned_to_runner(self):
        error = urllib.error.HTTPError(
            "http://localhost/command",
            500,
            "Internal Server Error",
            {},
            io.BytesIO('{"ok": false, "error": "BSL failed"}'.encode("utf-8")),
        )
        opener = Opener(error=error)
        with patch("client.urllib.request.build_opener", return_value=opener):
            result = client.request_json("http://localhost/command", {"command": "Query"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["httpStatus"], 500)
        self.assertEqual(result["error"], "BSL failed")

    def test_non_object_response_is_protocol_error(self):
        opener = Opener(Response("[]"))
        with patch("client.urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "JSON object"):
                client.request_json("http://localhost/health")


if __name__ == "__main__":
    unittest.main()
