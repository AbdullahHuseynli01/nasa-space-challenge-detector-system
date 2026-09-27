"""Load and normalize NASA Giovanni sea-ice CSV exports."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATASET_PATHS: dict[str, Path] = {
    "arctic": DATA_DIR / "arctic.csv",
    "antarctic": DATA_DIR / "antarctic.csv",
}


def available_datasets() -> tuple[str, ...]:
    """Return the dataset identifiers exposed by the backend."""

    return tuple(DATASET_PATHS)


def get_dataset_path(dataset: str) -> Path:
    """Return a configured dataset path or raise for an unknown dataset."""

    try:
        return DATASET_PATHS[dataset]
    except KeyError as exc:
        raise ValueError(f"Unknown dataset: {dataset}") from exc


def _read_lines(path: Path) -> list[str]:
    """Read a NASA export as text while supporting an optional UTF-8 BOM."""

    if not path.is_file():
        raise FileNotFoundError(
            f"NASA CSV file for dataset does not exist: {path}"
        )

    try:
        return path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read NASA CSV file '{path}': {exc}") from exc


def _find_data_header(lines: list[str], path: Path) -> int:
    """Find the zero-based line index of the time-series CSV header.

    NASA exports put metadata before the actual CSV table. Detecting the
    header by its first field keeps parsing independent of the number of
    metadata rows in a particular export.
    """

    for line_number, line in enumerate(lines):
        if not line.strip():
            continue

        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error:
            continue

        if fields and fields[0].strip().lower() == "time":
            return line_number

    raise ValueError(
        f"Invalid NASA CSV format in '{path}': "
        "could not find a data header whose first column is 'time'."
    )


def _extract_fill_values(lines: list[str], header_index: int) -> set[float]:
    """Extract numeric fill values declared in the metadata rows."""

    fill_values: set[float] = set()

    for line in lines[:header_index]:
        if not line.strip():
            continue

        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error:
            continue

        if len(fields) < 2 or not fields[0].strip().lower().startswith("fill value"):
            continue

        try:
            fill_values.add(float(fields[1].strip()))
        except ValueError:
            # An unreadable fill value should not make valid data unusable.
            # The value will still be handled by normal numeric coercion.
            continue

    return fill_values


def _read_data_frame(lines: list[str], header_index: int, path: Path) -> pd.DataFrame:
    """Read the table portion of a NASA export into a raw DataFrame."""

    csv_text = "\n".join(lines[header_index:])

    try:
        frame = pd.read_csv(StringIO(csv_text), dtype="string")
    except (pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"Invalid time-series table in '{path}': {exc}") from exc

    frame.columns = [str(column).strip() for column in frame.columns]

    if len(frame.columns) != 2:
        raise ValueError(
            f"Invalid NASA CSV format in '{path}': expected exactly two columns "
            f"(time and value), found {len(frame.columns)}."
        )

    if frame.columns[0].lower() != "time":
        raise ValueError(
            f"Invalid NASA CSV format in '{path}': the first data column must "
            f"be 'time', found '{frame.columns[0]}'."
        )

    if not frame.columns[1]:
        raise ValueError(
            f"Invalid NASA CSV format in '{path}': the value column has no name."
        )

    return frame


def load_csv(dataset: str) -> pd.DataFrame:
    """Load one configured NASA dataset as a clean ``date``/``value`` frame.

    Invalid timestamps, missing values, non-finite numbers, NASA fill values,
    and values outside the sea-ice fraction range ``[0, 1]`` are removed.
    """

    path = get_dataset_path(dataset)
    lines = _read_lines(path)
    header_index = _find_data_header(lines, path)
    raw_frame = _read_data_frame(lines, header_index, path)
    fill_values = _extract_fill_values(lines, header_index)

    time_column, value_column = raw_frame.columns
    dates = pd.to_datetime(raw_frame[time_column].str.strip(), errors="coerce")
    values = pd.to_numeric(raw_frame[value_column].str.strip(), errors="coerce")

    finite_values = pd.Series(
        np.isfinite(values.to_numpy(dtype=float, na_value=np.nan)),
        index=raw_frame.index,
    )
    valid_rows = dates.notna() & values.notna() & finite_values

    if fill_values:
        valid_rows &= ~values.isin(fill_values)

    # The source field is a covered fraction, so numbers outside this range
    # cannot represent valid observations.
    valid_rows &= values.ge(0) & values.le(1)

    cleaned = pd.DataFrame(
        {
            "date": dates[valid_rows],
            "value": values[valid_rows],
        }
    )

    if cleaned.empty:
        raise ValueError(
            f"NASA CSV '{path}' contains no valid time-series rows after "
            "date and value validation."
        )

    cleaned = (
        cleaned.loc[:, ["date", "value"]]
        .sort_values("date")
        .reset_index(drop=True)
    )

    if cleaned["date"].duplicated().any():
        raise ValueError(
            f"NASA CSV '{path}' contains duplicate timestamps; "
            "each timestamp must identify one observation."
        )

    return cleaned


def load_arctic() -> pd.DataFrame:
    """Load the Arctic dataset."""

    return load_csv("arctic")


def load_antarctic() -> pd.DataFrame:
    """Load the Antarctic dataset."""

    return load_csv("antarctic")


def validate_datasets() -> None:
    """Print a thorough validation report for every configured dataset."""

    expected_ranges = {
        "arctic": (pd.Timestamp("1980-01-01"), pd.Timestamp("2026-01-01")),
        "antarctic": (pd.Timestamp("1980-01-01"), pd.Timestamp("2026-01-01")),
    }

    for dataset in available_datasets():
        frame = load_csv(dataset)

        expected_start, expected_end = expected_ranges[dataset]
        actual_start = frame["date"].min()
        actual_end = frame["date"].max()
        expected_observations = len(
            pd.date_range(expected_start, expected_end, freq="MS")
        )
        expected_dates = pd.date_range(actual_start, actual_end, freq="MS")

        checks = {
            "DataFrame is not empty": not frame.empty,
            "Date column is datetime": pd.api.types.is_datetime64_any_dtype(
                frame["date"]
            ),
            "Value column is numeric": pd.api.types.is_numeric_dtype(
                frame["value"]
            ),
            "Dates sorted ascending": frame["date"].is_monotonic_increasing,
            "No duplicate dates": not frame["date"].duplicated().any(),
            "No missing values": not frame[["date", "value"]].isna().any().any(),
            "Values within [0, 1]": frame["value"].between(0, 1).all(),
            "Start date is correct": actual_start == expected_start,
            "End date is correct": actual_end == expected_end,
            "Monthly coverage is complete": len(frame) == expected_observations
            and frame["date"].reset_index(drop=True).equals(
                expected_dates.to_series(index=range(len(expected_dates)))
            ),
        }

        print(f"{dataset} CSV validation")
        print("-" * 24)
        print(f"number of rows: {len(frame)}")
        print(f"expected monthly observations: {expected_observations}")
        print(f"first date: {actual_start}")
        print(f"last date: {actual_end}")
        print(f"minimum value: {frame['value'].min()}")
        print(f"maximum value: {frame['value'].max()}")
        print(f"missing values: {int(frame.isna().sum().sum())}")
        for check_name, passed in checks.items():
            print(f"{'PASS' if passed else 'FAIL'} - {check_name}")

        if not all(checks.values()):
            raise AssertionError(f"Validation failed for {dataset}: {checks}")

        print("overall result: PASS")
        print()


if __name__ == "__main__":
    validate_datasets()
