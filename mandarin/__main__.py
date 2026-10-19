from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="mandarin", description="Context-aware offline file conversion for Ubuntu"
    )
    parser.add_argument("files", nargs="*")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--convert", metavar="FORMAT")
    parser.add_argument("--tool", metavar="OPERATION")
    parser.add_argument("--options", default="{}", help="JSON object of typed tool settings")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--popup", action="store_true")
    parser.add_argument("--service", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.health:
        from .runtime import health

        result = health()
        print(json.dumps(result, indent=2))
        return 0 if result["isolation"].get("available") and all(result["engines"].values()) else 1
    if arguments.convert or arguments.tool:
        from .jobs import JobManager

        manager = JobManager()
        try:
            job = manager.submit(
                [Path(p) for p in arguments.files],
                "convert:" + arguments.convert if arguments.convert else arguments.tool,
                json.loads(arguments.options),
                arguments.output,
            )
            while job.state in {"queued", "running", "validating", "publishing"}:
                time.sleep(0.1)
            print(
                json.dumps(
                    {
                        "id": job.id,
                        "state": job.state,
                        "outputs": [str(p) for p in job.outputs],
                        "error": job.error,
                    }
                )
            )
            return 0 if job.state == "succeeded" else 1
        except (ValueError, RuntimeError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        finally:
            manager.close()
    from .ui import Application

    app = Application(arguments.popup, arguments.service)
    return app.run([sys.argv[0]] + arguments.files)


if __name__ == "__main__":
    raise SystemExit(main())
