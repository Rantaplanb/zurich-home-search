from __future__ import annotations

import argparse
import imaplib

import uvicorn

from .config import load_config
from .gmail import GmailAlertFetcher, GmailAuth
from .service import TriageService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homegate-triage-assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("imap-check", help="Test IMAP connectivity and mailbox access.")
    subparsers.add_parser("gmail-auth", help="Run Gmail OAuth auth flow and save refresh tokens.")
    subparsers.add_parser("gmail-check", help="Test Gmail API access and Homegate alert search.")
    subparsers.add_parser("triage-once", help="Run one IMAP -> extract -> score cycle.")
    subparsers.add_parser("rescore", help="Re-score all stored listings.")

    run_parser = subparsers.add_parser("run", help="Start the local inbox web app and background poller.")
    run_parser.add_argument("--host", default=None)
    run_parser.add_argument("--port", type=int, default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()
    service = TriageService(config)

    if args.command == "imap-check":
        if not config.imap.is_configured:
            raise SystemExit("IMAP is not configured. Set IMAP_HOST, IMAP_PORT, IMAP_USERNAME, and IMAP_PASSWORD.")
        if config.imap.use_ssl:
            client: imaplib.IMAP4 | imaplib.IMAP4_SSL = imaplib.IMAP4_SSL(
                config.imap.host, config.imap.port
            )
        else:
            client = imaplib.IMAP4(config.imap.host, config.imap.port)
        try:
            login_result = client.login(config.imap.username, config.imap.password)
            select_result = client.select(config.imap.mailbox)
            search_result = client.search(None, config.imap.search_query)
            print(
                {
                    "login": login_result,
                    "mailbox": config.imap.mailbox,
                    "select": select_result,
                    "search_query": config.imap.search_query,
                    "search": search_result,
                }
            )
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()
        return

    if args.command == "gmail-auth":
        tokens = GmailAuth(config).authenticate()
        print(config.gmail.token_path)
        print(f"Saved Gmail tokens. Expires at {tokens.expires_at:.0f}.")
        return

    if args.command == "gmail-check":
        result = GmailAlertFetcher(config).test_access()
        print(result)
        return

    if args.command == "triage-once":
        summary = service.run_cycle()
        print(summary.model_dump_json(indent=2))
        return

    if args.command == "rescore":
        rescored = service.rescore_all()
        print(f"Rescored {rescored} listings.")
        return

    if args.command == "run":
        from .review import create_app

        app = create_app(service, enable_background_poller=True)
        uvicorn.run(
            app,
            host=args.host or config.app.host,
            port=args.port or config.app.port,
        )
        return

    parser.error(f"Unsupported command: {args.command}")
