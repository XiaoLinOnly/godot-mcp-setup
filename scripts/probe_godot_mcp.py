#!/usr/bin/env python3
"""Probe the Godot MCP server over streamable HTTP.

Sends initialize -> tools/list (-> optional tools/call) to the editor plugin at
http://127.0.0.1:3000/mcp. Only the Python standard library is required.

Examples:
    python scripts/probe_godot_mcp.py
    python scripts/probe_godot_mcp.py --call project_info --args '{"action": "get_info"}'
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PROTOCOL_VERSION = "2024-11-05"


class RpcError(Exception):
    pass


def parse_json_or_sse(raw, content_type):
    text = raw.strip()
    if not text:
        return None
    if "text/event-stream" in (content_type or "").lower():
        messages = []
        data_lines = []
        for line in text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif not line.strip() and data_lines:
                blob = "\n".join(data_lines)
                data_lines = []
                try:
                    messages.append(json.loads(blob))
                except json.JSONDecodeError:
                    pass
        if data_lines:
            try:
                messages.append(json.loads("\n".join(data_lines)))
            except json.JSONDecodeError:
                pass
        return messages[-1] if messages else None
    return json.loads(text)


def post(url, payload, session_id=None, timeout=20.0):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("Content-Type", "")
            new_session = response.headers.get("Mcp-Session-Id") or session_id
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:1000]
        raise RpcError("HTTP %s from %s: %s" % (exc.code, url, body))
    except urllib.error.URLError as exc:
        raise ConnectionError(
            "cannot reach %s (%s). Is the Godot editor open with the MCP plugin enabled?"
            % (url, exc.reason)
        )
    return parse_json_or_sse(raw, content_type), new_session


def rpc(url, method, params, request_id, session_id=None, timeout=20.0):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    reply, new_session = post(url, payload, session_id, timeout)
    if reply is None:
        raise RpcError("empty response for %s" % method)
    if reply.get("id") != request_id:
        raise RpcError("unexpected response id for %s: %s" % (method, reply.get("id")))
    if "error" in reply:
        raise RpcError("JSON-RPC error: " + json.dumps(reply["error"], ensure_ascii=False))
    return reply.get("result", {}), new_session


def summarize_result(result, full):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if result.get("isError"):
        text = "[isError] " + text
    if not full and len(text) > 4000:
        text = text[:4000] + "\n... (truncated; use --full)"
    return text


def main():
    parser = argparse.ArgumentParser(description="Probe the Godot MCP HTTP server")
    parser.add_argument("--url", default="http://127.0.0.1:3000/mcp", help="MCP endpoint")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds")
    parser.add_argument("--call", help="Tool name to call after tools/list")
    parser.add_argument("--args", default="{}", help="JSON object passed to --call")
    parser.add_argument("--full", action="store_true", help="Do not truncate tool output")
    args = parser.parse_args()

    print("ENDPOINT: " + args.url)
    try:
        init, session_id = rpc(
            args.url,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "godot-mcp-probe", "version": "1.0"},
            },
            1,
            timeout=args.timeout,
        )
        info = init.get("serverInfo", {})
        print("INIT: %s %s (protocol %s)" % (
            info.get("name", "?"), info.get("version", "?"), init.get("protocolVersion", "?")))

        # The plugin acknowledges "initialized" with a JSON-RPC response; it is safe to ignore.
        try:
            post(
                args.url,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                session_id,
                args.timeout,
            )
        except (RpcError, ConnectionError):
            pass

        listing, session_id = rpc(args.url, "tools/list", {}, 2, session_id, args.timeout)
        tools = listing.get("tools", [])
        print("TOOL COUNT: %d" % len(tools))
        print("TOOLS: " + ", ".join(tool.get("name", "?") for tool in tools))

        ok = len(tools) > 0
        if args.call:
            try:
                call_args = json.loads(args.args)
            except json.JSONDecodeError as exc:
                raise SystemExit("--args is not valid JSON: %s" % exc)
            if not isinstance(call_args, dict):
                raise SystemExit("--args must be a JSON object")
            result, _ = rpc(
                args.url,
                "tools/call",
                {"name": args.call, "arguments": call_args},
                3,
                session_id,
                max(args.timeout, 60.0),
            )
            print("CALL %s: %s" % (args.call, summarize_result(result, args.full)))
            ok = not result.get("isError", False)
    except (RpcError, ConnectionError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
