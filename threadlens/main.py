"""ThreadLens CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
import threading

from threadlens import __version__
from threadlens.agent.lifecycle import run_agent
from threadlens.config import RuntimeMode, ensure_data_directories, load_config
from threadlens.server.lifecycle import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="threadlens",
        description="ThreadLens — read-only Thread and Matter-over-Thread observability",
    )
    parser.add_argument(
        "--mode",
        choices=[m.value for m in RuntimeMode],
        help="Runtime mode: server, agent, or both",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Path to config.yaml (default: /config/config.yaml or THREADLENS_CONFIG_PATH)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ThreadLens {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config_path, mode_override=args.mode)
    ensure_data_directories(config)

    mode = config.mode
    if mode == RuntimeMode.SERVER:
        run_server(config, active_mode=RuntimeMode.SERVER)
        return 0

    if mode == RuntimeMode.AGENT:
        run_agent(config)
        return 0

    if mode == RuntimeMode.BOTH:
        agent_thread = threading.Thread(
            target=run_agent,
            args=(config,),
            name="threadlens-agent",
            daemon=True,
        )
        agent_thread.start()
        run_server(config, active_mode=RuntimeMode.BOTH)
        return 0

    print(f"Unsupported mode: {mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
