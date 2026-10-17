from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import zipfile

import requests


# Download one week of historical Binance BTCUSDT spot data.
SYMBOL = "BTCUSDT"
START_DATE = date(2025, 7, 1)
END_DATE = date(2025, 7, 31)

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "raw"


def is_valid_archive(path: Path) -> bool:
    """Check that an existing ZIP contains a CSV and is readable."""
    try:
        with zipfile.ZipFile(path) as archive:
            has_csv = any(
                name.lower().endswith(".csv")
                for name in archive.namelist()
            )
            return has_csv and archive.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def dates_in_range():
    """Yield every date, including both endpoints."""
    current = START_DATE
    while current <= END_DATE:
        yield current
        current += timedelta(days=1)


def download_day(day: date) -> bool:
    filename = f"{SYMBOL}-aggTrades-{day:%Y-%m-%d}.zip"
    destination = RAW_DIR / filename
    url = (
        "https://data.binance.vision/data/spot/daily/aggTrades/"
        f"{SYMBOL}/{filename}"
    )

    if destination.exists() and is_valid_archive(destination):
        print(f"Already downloaded: {filename}")
        return True

    print(f"Downloading: {filename}")

    try:
        response = requests.get(url, timeout=(10, 60))

        if response.status_code == 404:
            print(f"  ERROR: archive not found: {url}")
            return False

        response.raise_for_status()
        content = response.content

        # Validate the ZIP before saving it.
        with zipfile.ZipFile(BytesIO(content)) as archive:
            has_csv = any(
                name.lower().endswith(".csv")
                for name in archive.namelist()
            )
            if not has_csv or archive.testzip() is not None:
                print("  ERROR: downloaded ZIP failed validation.")
                return False

        destination.write_bytes(content)
        print(f"  Saved {len(content):,} bytes")
        return True

    except (
        requests.RequestException,
        zipfile.BadZipFile,
        OSError,
    ) as error:
        print(f"  ERROR: {error}")
        return False


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results = [
        (day, download_day(day))
        for day in dates_in_range()
    ]

    successful = sum(ok for _, ok in results)
    failed_dates = [
        day.isoformat()
        for day, ok in results
        if not ok
    ]

    print(f"\nCompleted: {successful}/{len(results)} days")

    if failed_dates:
        print("Failed dates:", ", ".join(failed_dates))
        raise SystemExit(1)

    print(f"Archives are saved in: {RAW_DIR}")


if __name__ == "__main__":
    main()
