"""One-off operational commands for the backend (Sprint 8).

Run inside the container image, e.g. as the compose ``migrate`` service:

    alembic upgrade head
    python -m app.cli recover-runs

Keeping these as explicit commands (instead of baking recovery into
``create_app``) keeps startup idempotent and multi-worker safe. Stdlib
``argparse`` only — no extra runtime dependency for an ops path.
"""

import argparse
import asyncio


def _recover_runs() -> None:
    """Mark stranded active analysis runs as failed (restart recovery)."""
    from app.db.session import session_factory
    from app.domains.analysis.reaper import recover_stranded_runs

    async def _run() -> int:
        async with session_factory() as session:
            recovered = await recover_stranded_runs(session)
        return len(recovered)

    recovered_count = asyncio.run(_run())
    print(f"Recovered {recovered_count} stranded analysis run(s).")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="evoshield", description="EvoShield operational commands."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "recover-runs",
        help="Fail stranded queued/running analysis runs left by a restart.",
    )
    args = parser.parse_args()

    if args.command == "recover-runs":
        _recover_runs()


if __name__ == "__main__":
    main()
