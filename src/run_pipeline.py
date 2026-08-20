"""Pipeline entrypoint: ingest, then quality-gated load, in one process.

This is what the scheduler invokes. It runs ingestion followed by the load
(which internally runs the data quality gate), emits a single log stream, and
returns a non-zero exit code if any stage fails — so cron / Task Scheduler can
detect a bad run.

Usage:
    python -m src.run_pipeline                        # daily run
    python -m src.run_pipeline --start 2026-01-01 \\
                               --end   2026-01-31      # backfill a range

Scheduling (daily at 06:00 America/Chicago):

    # Linux / macOS crontab -- adjust paths, and set CRON_TZ for local time:
    CRON_TZ=America/Chicago
    0 6 * * * cd /path/to/weather-etl-pipeline && \\
        venv/bin/python -m src.run_pipeline >> logs/pipeline.log 2>&1

    # Windows Task Scheduler (PowerShell, run once to register):
    $py = "C:\\path\\to\\weather-etl-pipeline\\venv\\Scripts\\python.exe"
    $action  = New-ScheduledTaskAction -Execute $py `
        -Argument "-m src.run_pipeline" `
        -WorkingDirectory "C:\\path\\to\\weather-etl-pipeline"
    $trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
    Register-ScheduledTask -TaskName "weather-etl-daily" `
        -Action $action -Trigger $trigger
"""

import logging
import sys

from src import ingest, load

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main(argv=None) -> int:
    # ingest.parse_args validates --start/--end and exits on bad input.
    args = ingest.parse_args(argv)

    mode = f"backfill {args.start}..{args.end}" if args.start else "daily"
    logger.info("Pipeline starting (%s mode)", mode)

    ingest_rc = ingest.main(argv)
    if ingest_rc != 0:
        logger.error("Ingestion failed (rc=%d); skipping load", ingest_rc)
        return ingest_rc

    load_rc = load.main()
    if load_rc != 0:
        logger.error("Load failed (rc=%d)", load_rc)
        return load_rc

    logger.info("Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
