"""Command-line entry point for Agent Reliability Lab."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agentlab",
        description="Agent Reliability Lab local trace tools.",
    )
    parser.parse_args()
