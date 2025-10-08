import json

import httpx
from django.test import SimpleTestCase

from slm.client import SLMClient, SLMError

SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}}


def client_with(replies):
    """Serve canned /api/chat messages in order, recording the request bodies."""
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": replies[len(requests) - 1]})

    return SLMClient("http://slm", "m", 5, httpx.MockTransport(handler)), requests


class CallToolTests(SimpleTestCase):
    def call(self, client):
        return client.call_tool("sys", "usr", "t", "desc", SCHEMA)

    def test_uses_native_tool_call(self):
        client, requests = client_with([{"tool_calls": [{"function": {"name": "t", "arguments": {"a": 1}}}]}])
        self.assertEqual(self.call(client), {"a": 1})
        self.assertEqual(requests[0]["tools"][0]["function"]["name"], "t")

    def test_requests_a_context_large_enough_for_the_prompts(self):
        client, requests = client_with([{"content": '{"a": 1}'}])
        self.call(client)
        self.assertEqual(requests[0]["options"]["num_ctx"], 8192)

    def test_limits_output_length(self):
        client, requests = client_with([{"content": '{"a": 1}'}])
        self.call(client)
        self.assertEqual(requests[0]["options"]["num_predict"], 1500)

    def test_reply_cut_off_at_the_limit_is_an_error(self):
        reply = {"message": {"content": "partial resume"}, "done_reason": "length"}
        client = SLMClient("http://slm", "m", 5, httpx.MockTransport(lambda _r: httpx.Response(200, json=reply)))
        with self.assertRaises(SLMError):
            client.complete("s", "u")

    def test_accepts_string_arguments(self):
        client, _ = client_with([{"tool_calls": [{"function": {"name": "t", "arguments": '{"a": 2}'}}]}])
        self.assertEqual(self.call(client), {"a": 2})

    def test_falls_back_to_json_in_text(self):
        client, requests = client_with([{"content": 'Sure! {broken} then {"a": 3} done'}])
        self.assertEqual(self.call(client), {"a": 3})
        self.assertEqual(len(requests), 1)

    def test_falls_back_to_schema_constrained_retry(self):
        client, requests = client_with([{"content": "no json"}, {"content": '{"a": 4}'}])
        self.assertEqual(self.call(client), {"a": 4})
        self.assertEqual(requests[1]["format"], SCHEMA)

    def test_ignores_call_to_unknown_tool(self):
        client, _ = client_with([{"tool_calls": [{"function": {"name": "other", "arguments": {"a": 9}}}]},
                                 {"content": '{"a": 5}'}])
        self.assertEqual(self.call(client), {"a": 5})

    def test_raises_when_every_step_fails(self):
        client, _ = client_with([{"content": "no"}, {"content": "still no"}])
        with self.assertRaises(SLMError):
            self.call(client)


class TransportTests(SimpleTestCase):
    def test_server_error_becomes_slm_error(self):
        client = SLMClient("http://slm", "m", 5, httpx.MockTransport(lambda _r: httpx.Response(500)))
        with self.assertRaises(SLMError):
            client.complete("s", "u")

    def test_connection_error_becomes_slm_error(self):
        def refuse(_request):
            raise httpx.ConnectError("refused")

        client = SLMClient("http://slm", "m", 5, httpx.MockTransport(refuse))
        with self.assertRaises(SLMError):
            client.complete("s", "u")

    def test_empty_reply_is_an_error(self):
        client, _ = client_with([{"content": "  "}])
        with self.assertRaises(SLMError):
            client.complete("s", "u")
