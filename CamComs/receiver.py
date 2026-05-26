from __future__ import annotations

import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from CamComs.audit import AuditLog
from CamComs.codec import decode_envelope, encode_envelope
from CamComs.encryption import CamComsCryptoError, CamComsIdentity, PublicKeyBundle, decrypt_text, encrypt_message
from CamComs.instructions import instruction_from_text, instruction_to_text, press_instruction
from CamComs.paths import private_key_path, public_key_path
from CamComs.replay import ReplayGuard
from CamComs.transport import CamComsHttpClient
from CamComs.trust import DEFAULT_TRUSTED_DIR, find_trusted_sender
from QuikTieper.remote import RemoteActionRunner


class CamComsReceiverError(ValueError):
    """Raised when the host receiver cannot accept a message."""


class HostMessageProcessor:
    def __init__(
        self,
        *,
        host_identity: CamComsIdentity,
        trusted_dir: Path = DEFAULT_TRUSTED_DIR,
        replay_guard: ReplayGuard | None = None,
        action_runner: RemoteActionRunner | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.host_identity = host_identity
        self.trusted_dir = trusted_dir
        self.replay_guard = replay_guard or ReplayGuard()
        self.action_runner = action_runner or RemoteActionRunner(dry_run=True)
        self.audit_log = audit_log

    def process_encoded(self, encoded_message: str) -> dict[str, Any]:
        envelope: dict[str, Any] = {}
        try:
            envelope = decode_envelope(encoded_message.strip())
            trusted_sender = find_trusted_sender(str(envelope.get("sender", "")), self.trusted_dir)
            if trusted_sender is None:
                raise CamComsReceiverError("sender is not trusted")
            self.replay_guard.check_and_record(envelope)
            plaintext = decrypt_text(envelope, recipient=self.host_identity, expected_sender=trusted_sender)
            instruction = instruction_from_text(plaintext)
            result = self.action_runner.run(instruction)
            response = {
                "ok": True,
                "sender": envelope["sender"],
                "message_id": envelope["message_id"],
                "action": result.action,
                "detail": result.detail,
                "executed": result.executed,
            }
            self._record({**response, "instruction": instruction})
            return response
        except (CamComsCryptoError, CamComsReceiverError, ValueError) as exc:
            self._record(
                {
                    "ok": False,
                    "sender": envelope.get("sender"),
                    "message_id": envelope.get("message_id"),
                    "error": str(exc),
                }
            )
            raise

    def _record(self, event: dict[str, Any]) -> None:
        if self.audit_log is not None:
            self.audit_log.record(event)


def run_host_receiver(
    *,
    host: str,
    port: int,
    host_identity: CamComsIdentity,
    trusted_dir: Path = DEFAULT_TRUSTED_DIR,
    replay_guard: ReplayGuard | None = None,
    action_runner: RemoteActionRunner | None = None,
    audit_log: AuditLog | None = None,
) -> None:
    processor = HostMessageProcessor(
        host_identity=host_identity,
        trusted_dir=trusted_dir,
        replay_guard=replay_guard,
        action_runner=action_runner,
        audit_log=audit_log,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in {"/", "/receiver"}:
                self._send_html(_chat_page("Receiver", "receiver", processor.audit_log))
                return
            if self.path == "/sender":
                self._send_html(_chat_page("Sender", "sender", processor.audit_log, include_sender_form=True))
                return
            if self.path == "/messages":
                self._send_json(_recent_chat(processor.audit_log), status=200)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            if self.path == "/send":
                self._handle_send_form(payload.decode("utf-8"))
                return
            try:
                response = processor.process_encoded(payload.decode("ascii"))
                self.send_response(200)
            except (CamComsCryptoError, CamComsReceiverError, ValueError) as exc:
                response = {"ok": False, "error": str(exc)}
                self.send_response(400)
            self._send_json(response)

        def _handle_send_form(self, raw_form: str) -> None:
            form = parse_qs(raw_form)
            target_host = _form_value(form, "host", "127.0.0.1")
            target_port = int(_form_value(form, "port", "8080"))
            keys = [key.strip() for key in _form_value(form, "keys", "alt s").replace("+", " ").split() if key.strip()]
            sender_private = Path(_form_value(form, "sender_private", str(private_key_path("host")))).expanduser()
            recipient_public = Path(_form_value(form, "recipient_public", str(public_key_path("esp32")))).expanduser()
            event: dict[str, Any] = {
                "direction": "outbound",
                "sender": str(sender_private),
                "recipient": str(recipient_public),
                "action": "press",
                "detail": "+".join(keys),
            }
            try:
                sender = CamComsIdentity.from_private_dict(json.loads(sender_private.read_text(encoding="utf-8")))
                recipient = PublicKeyBundle.from_dict(json.loads(recipient_public.read_text(encoding="utf-8")))
                envelope = encrypt_message(
                    instruction_to_text(press_instruction(keys)),
                    sender=sender,
                    recipient=recipient,
                )
                encoded = encode_envelope(envelope)
                response = CamComsHttpClient(host=target_host, port=target_port).send_encoded(encoded)
                event.update(
                    {
                        "ok": True,
                        "sender": sender.device_id,
                        "recipient": recipient.device_id,
                        "message_id": envelope["message_id"],
                        "response": response,
                    }
                )
                processor._record(event)
                self.send_response(303)
                self.send_header("Location", "/sender")
                self.end_headers()
            except Exception as exc:
                event.update({"ok": False, "error": str(exc)})
                processor._record(event)
                self._send_html(_chat_page("Sender", "sender", processor.audit_log, include_sender_form=True, error=str(exc)), status=400)

        def _send_json(self, payload: dict[str, Any], *, status: int | None = None) -> None:
            if status is not None:
                self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload, sort_keys=True).encode("utf-8"))

        def _send_html(self, body: str, *, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, _format: str, *_args: object) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()


def _form_value(form: dict[str, list[str]], key: str, default: str) -> str:
    values = form.get(key)
    if not values:
        return default
    return values[0].strip() or default


def _recent_chat(audit_log: AuditLog | None, *, seconds: int = 180) -> dict[str, Any]:
    events = audit_log.read_since(seconds=seconds) if audit_log is not None else []
    return {"window_seconds": seconds, "events": events}


def _chat_page(
    title: str,
    active: str,
    audit_log: AuditLog | None,
    *,
    include_sender_form: bool = False,
    error: str | None = None,
) -> str:
    events = _recent_chat(audit_log)["events"]
    rows = "\n".join(_event_row(event) for event in events) or "<p class='empty'>No messages in the last 3 minutes.</p>"
    form = _sender_form() if include_sender_form else ""
    error_html = f"<p class='error'>{escape(error)}</p>" if error else ""
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="5">
  <title>Fiona CamComs {escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }}
    header {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: #1d1d1d; }}
    a {{ color: #8ab4ff; text-decoration: none; margin-left: 14px; }}
    main {{ padding: 20px; max-width: 980px; margin: 0 auto; }}
    .chat {{ display: grid; gap: 10px; }}
    .msg {{ border: 1px solid #333; background: #1b1b1b; border-radius: 8px; padding: 12px; }}
    .inbound {{ border-left: 4px solid #56d364; }}
    .outbound {{ border-left: 4px solid #58a6ff; }}
    .failed {{ border-left-color: #ff7b72; }}
    .meta {{ color: #aaa; font-size: 13px; margin-bottom: 6px; }}
    .detail {{ font-family: ui-monospace, monospace; }}
    form {{ display: grid; gap: 10px; margin-bottom: 18px; background: #1b1b1b; padding: 14px; border: 1px solid #333; border-radius: 8px; }}
    label {{ display: grid; gap: 4px; }}
    input {{ padding: 8px; background: #0d0d0d; color: #eee; border: 1px solid #444; border-radius: 6px; }}
    button {{ width: fit-content; padding: 8px 14px; border: 0; border-radius: 6px; background: #238636; color: white; }}
    .error {{ color: #ff7b72; }}
    .empty {{ color: #aaa; }}
  </style>
</head>
<body>
  <header>
    <strong>Fiona CamComs {escape(title)}</strong>
    <nav>
      <a href="/receiver">Receiver</a>
      <a href="/sender">Sender</a>
      <a href="/messages">JSON</a>
    </nav>
  </header>
  <main data-active="{escape(active)}">
    <p>Showing CamComs chat events from the last 3 minutes to now. This page refreshes every 5 seconds.</p>
    {error_html}
    {form}
    <section class="chat">{rows}</section>
  </main>
</body>
</html>"""


def _sender_form() -> str:
    return f"""<form method="post" action="/send">
  <label>Target host/IP <input name="host" value="127.0.0.1"></label>
  <label>Target port <input name="port" value="8080"></label>
  <label>Press keys <input name="keys" value="alt s"></label>
  <label>Sender private key <input name="sender_private" value="{escape(str(private_key_path('host')))}"></label>
  <label>Recipient public key <input name="recipient_public" value="{escape(str(public_key_path('esp32')))}"></label>
  <button type="submit">Encrypt and Send</button>
</form>"""


def _event_row(event: dict[str, Any]) -> str:
    ok = bool(event.get("ok"))
    direction = str(event.get("direction") or ("inbound" if event.get("sender") else "event"))
    status = "ok" if ok else "failed"
    classes = f"msg {escape(direction)} {'failed' if not ok else ''}"
    title = f"{direction} {status}"
    detail = event.get("detail") or event.get("error") or event.get("message_id") or ""
    meta = f"{event.get('timestamp', '')} sender={event.get('sender', '')} recipient={event.get('recipient', '')}"
    return f"<article class='{classes}'><div class='meta'>{escape(title)} · {escape(meta)}</div><div class='detail'>{escape(str(detail))}</div></article>"
