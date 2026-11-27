"""Command-line entry point for Agent Reliability Lab."""

import argparse
import json

from agentlab.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agentlab",
        description="Agent Reliability Lab local trace tools.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("config", help="show nonsecret settings")

    if parser.parse_args().command == "config":
        try:
            settings = get_settings()
        except ValueError as exc:
            parser.error(str(exc))

        # URLs can carry credentials in userinfo, paths, queries, or fragments.
        # Display only the HTTP origin. Never dump the process environment.
        origin = settings.api_url.copy_with(
            userinfo=b"", path="", query=None, fragment=None
        )
        print(
            json.dumps(
                {
                    "db_path": str(settings.db_path),
                    "api_origin": str(origin),
                    "capture_payloads": settings.capture_payloads,
                },
                indent=2,
            )
        )
