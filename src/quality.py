"""Data quality gate: validate tidy frames before they reach Postgres.

The load layer runs `check_frame` on each transformed DataFrame and refuses to
upsert if any hard check fails, so malformed or physically impossible data never
lands in the warehouse. Checks are deliberately simple and explainable:

    - duplicate key      : no repeated (location_name, observation_time) rows
    - null fraction      : each value column's null share <= MAX_NULL_FRACTION
    - value range        : each value stays within its plausible physical range
    - completeness (warn): flags gaps vs. the expected 24 hourly rows/day/location

Duplicate-key, null-fraction, and range violations are hard failures. Sparse
coverage is reported as a warning only — a partial day is still worth loading.

Usage:
    from src.quality import check_frame
    report = check_frame(weather_df, "hourly_weather")
    if not report.ok:
        ...  # abort the load
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.config import MAX_NULL_FRACTION, VALUE_RANGES

logger = logging.getLogger(__name__)

KEY_COLUMNS = ["location_name", "observation_time"]
# Columns that are metadata, not measurements — never range/null checked.
NON_VALUE_COLUMNS = set(KEY_COLUMNS) | {"source_file"}
EXPECTED_ROWS_PER_DAY = 24


@dataclass
class QualityReport:
    """Outcome of validating one frame. `ok` is False if any hard check failed."""

    label: str
    row_count: int
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def log(self) -> None:
        for warning in self.warnings:
            logger.warning("[%s] %s", self.label, warning)
        for error in self.errors:
            logger.error("[%s] %s", self.label, error)
        if self.ok:
            logger.info("[%s] quality OK (%d rows)", self.label, self.row_count)


def _value_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in NON_VALUE_COLUMNS]


def _check_duplicate_keys(df: pd.DataFrame, report: QualityReport) -> None:
    if not set(KEY_COLUMNS).issubset(df.columns):
        return
    dup_count = int(df.duplicated(subset=KEY_COLUMNS).sum())
    if dup_count:
        report.errors.append(
            f"{dup_count} duplicate (location_name, observation_time) rows"
        )


def _check_null_fraction(df: pd.DataFrame, report: QualityReport) -> None:
    for col in _value_columns(df):
        fraction = float(df[col].isna().mean())
        if fraction > MAX_NULL_FRACTION:
            report.errors.append(
                f"column '{col}' is {fraction:.0%} null "
                f"(max allowed {MAX_NULL_FRACTION:.0%})"
            )


def _check_value_ranges(df: pd.DataFrame, report: QualityReport) -> None:
    for col in _value_columns(df):
        bounds = VALUE_RANGES.get(col)
        if bounds is None:
            continue
        low, high = bounds
        values = pd.to_numeric(df[col], errors="coerce")
        if low is not None:
            below = int((values < low).sum())
            if below:
                report.errors.append(
                    f"column '{col}' has {below} value(s) below minimum {low}"
                )
        if high is not None:
            above = int((values > high).sum())
            if above:
                report.errors.append(
                    f"column '{col}' has {above} value(s) above maximum {high}"
                )


def _check_completeness(df: pd.DataFrame, report: QualityReport) -> None:
    """Warn (not fail) when a location/day has fewer than 24 hourly rows."""
    if not set(KEY_COLUMNS).issubset(df.columns) or df.empty:
        return
    times = pd.to_datetime(df["observation_time"], utc=True)
    per_day = df.assign(_day=times.dt.date).groupby(["location_name", "_day"]).size()
    sparse = per_day[per_day < EXPECTED_ROWS_PER_DAY]
    for (location, day), count in sparse.items():
        report.warnings.append(
            f"{location} {day}: {count}/{EXPECTED_ROWS_PER_DAY} hourly rows"
        )


def check_frame(df: pd.DataFrame, label: str) -> QualityReport:
    """Run all quality checks on `df`, returning a QualityReport.

    An empty frame passes with no errors (there is nothing to load, which the
    caller handles separately). `label` names the frame in log output.
    """
    report = QualityReport(label=label, row_count=len(df))
    if df.empty:
        return report

    _check_duplicate_keys(df, report)
    _check_null_fraction(df, report)
    _check_value_ranges(df, report)
    _check_completeness(df, report)
    return report
