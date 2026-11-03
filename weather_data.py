#!/usr/bin/env python3
"""Download daily historical weather data from the Open-Meteo Archive API."""

import argparse
import time
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd
import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT_SECONDS = 60

DEFAULT_VARIABLES = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "apparent_temperature_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "weather_code",
    "cloud_cover_mean",
    "cloud_cover_max",
    "cloud_cover_min",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_max",
    "relative_humidity_2m_min",
    "dew_point_2m_mean",
    "dew_point_2m_max",
    "dew_point_2m_min",
    "surface_pressure_mean",
    "surface_pressure_max",
    "surface_pressure_min",
    "pressure_msl_mean",
    "pressure_msl_max",
    "pressure_msl_min",
    "snowfall_water_equivalent_sum",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "wet_bulb_temperature_2m_mean",
    "wet_bulb_temperature_2m_max",
    "wet_bulb_temperature_2m_min",
    "vapour_pressure_deficit_max",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
    "soil_moisture_28_to_100cm_mean",
    "soil_moisture_0_to_100cm_mean",
    "soil_temperature_0_to_7cm_mean",
    "soil_temperature_7_to_28cm_mean",
    "soil_temperature_28_to_100cm_mean",
    "soil_temperature_0_to_100cm_mean",
)


def fetch_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str,
    daily_variables: Sequence[str],
    temperature_unit: str,
    session: requests.Session,
    retries: int = 3,
    sleep_seconds: float = 2,
) -> dict:
    """Fetch daily weather observations, retrying transient network and server errors."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(daily_variables),
        "timezone": timezone,
        "temperature_unit": temperature_unit,
    }

    for attempt in range(retries):
        try:
            response = session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        else:
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == retries - 1:
                    response.raise_for_status()
            else:
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ValueError("The Open-Meteo API returned invalid JSON.") from exc

                if not isinstance(payload, dict):
                    raise ValueError("The Open-Meteo API response was not an object.")
                if payload.get("error"):
                    raise ValueError(
                        f"Open-Meteo API error: {payload.get('reason', 'unknown error')}"
                    )
                daily = payload.get("daily")
                if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
                    raise ValueError(
                        "The Open-Meteo API response did not contain daily observations."
                    )
                if not daily["time"]:
                    raise ValueError("The Open-Meteo API returned no daily observations.")
                return payload

        if attempt < retries - 1:
            time.sleep(sleep_seconds)

    raise RuntimeError("Weather request failed without returning an error.")


def build_dataframe(daily: dict) -> pd.DataFrame:
    """Convert the API's daily arrays into a date-sorted dataframe."""
    if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
        raise ValueError("Daily data must contain a list-valued 'time' field.")
    if not daily["time"]:
        raise ValueError("Daily data contains no observations.")

    try:
        frame = pd.DataFrame(daily)
    except ValueError as exc:
        raise ValueError("Daily API fields do not have matching lengths.") from exc

    frame["date"] = pd.to_datetime(frame.pop("time"), errors="raise")
    return frame.sort_values("date").reset_index(drop=True)


def add_features(
    frame: pd.DataFrame,
    temperature_unit: str,
    heat_wave_threshold: Optional[float] = None,
    freeze_threshold: Optional[float] = None,
    heavy_rain_threshold: float = 25.4,
    high_wind_threshold: float = 40,
) -> pd.DataFrame:
    """Add rolling, lagged, extreme-event, and calendar features."""
    result = frame.copy()

    if {"temperature_2m_max", "temperature_2m_min"}.issubset(result.columns):
        result["temp_range"] = (
            result["temperature_2m_max"] - result["temperature_2m_min"]
        )

    rolling_specs = {
        "temperature_2m_mean": ("temp_7d_avg", "mean"),
        "precipitation_sum": ("precip_7d_sum", "sum"),
        "wind_speed_10m_max": ("wind_7d_avg", "mean"),
        "relative_humidity_2m_mean": ("humidity_7d_avg", "mean"),
        "cloud_cover_mean": ("cloud_7d_avg", "mean"),
    }
    for column, (feature, operation) in rolling_specs.items():
        if column in result.columns:
            rolling = result[column].rolling(7)
            result[feature] = rolling.mean() if operation == "mean" else rolling.sum()

    lag_columns = (
        "temperature_2m_mean",
        "precipitation_sum",
        "wind_speed_10m_max",
        "relative_humidity_2m_mean",
        "cloud_cover_mean",
        "surface_pressure_mean",
    )
    for column in lag_columns:
        if column in result.columns:
            result[f"{column}_lag1"] = result[column].shift(1)
            result[f"{column}_lag7"] = result[column].shift(7)

    if temperature_unit == "celsius":
        heat_wave_threshold = 35 if heat_wave_threshold is None else heat_wave_threshold
        freeze_threshold = 0 if freeze_threshold is None else freeze_threshold
    else:
        heat_wave_threshold = 95 if heat_wave_threshold is None else heat_wave_threshold
        freeze_threshold = 32 if freeze_threshold is None else freeze_threshold

    if "temperature_2m_max" in result.columns:
        result["heat_wave"] = (
            result["temperature_2m_max"] > heat_wave_threshold
        ).astype(int)
    if "temperature_2m_min" in result.columns:
        result["freeze"] = (result["temperature_2m_min"] < freeze_threshold).astype(int)
    if "precipitation_sum" in result.columns:
        result["heavy_rain"] = (
            result["precipitation_sum"] > heavy_rain_threshold
        ).astype(int)
    if "wind_speed_10m_max" in result.columns:
        result["high_wind"] = (
            result["wind_speed_10m_max"] > high_wind_threshold
        ).astype(int)
    if "snowfall_sum" in result.columns:
        result["snow_day"] = (result["snowfall_sum"] > 0).astype(int)

    if "date" not in result.columns:
        raise ValueError("Daily data must include a 'date' column for calendar features.")
    dates = pd.to_datetime(result["date"], errors="raise")
    result["year"] = dates.dt.year
    result["month"] = dates.dt.month
    result["quarter"] = dates.dt.quarter
    result["day_of_week"] = dates.dt.dayofweek
    result["day_of_year"] = dates.dt.dayofyear
    result["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    result["sin_annual"] = np.sin(2 * np.pi * result["day_of_year"] / 365.25)
    result["cos_annual"] = np.cos(2 * np.pi * result["day_of_year"] / 365.25)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download daily historical weather data from Open-Meteo."
    )
    parser.add_argument("--latitude", required=True, type=float, help="Location latitude.")
    parser.add_argument("--longitude", required=True, type=float, help="Location longitude.")
    parser.add_argument(
        "--start-date",
        required=True,
        help="First date to download, in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="Last date to download, in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--timezone",
        default="auto",
        help="IANA timezone or 'auto' (default: auto).",
    )
    parser.add_argument(
        "--temperature-unit",
        choices=("celsius", "fahrenheit"),
        default="celsius",
        help="Temperature unit used by the API and feature thresholds (default: celsius).",
    )
    parser.add_argument(
        "--daily",
        default=",".join(DEFAULT_VARIABLES),
        help="Comma-separated Open-Meteo daily variables (default: the full variable set).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("weather_data.csv"),
        help="Output CSV path (default: ./weather_data.csv).",
    )
    parser.add_argument(
        "--no-features",
        action="store_true",
        help="Save the requested API variables without derived features.",
    )
    parser.add_argument("--heat-wave-threshold", type=float)
    parser.add_argument("--freeze-threshold", type=float)
    parser.add_argument("--heavy-rain-threshold", type=float, default=25.4)
    parser.add_argument("--high-wind-threshold", type=float, default=40)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
    except ValueError as exc:
        parser.error(f"dates must use YYYY-MM-DD format: {exc}")

    if end < start:
        parser.error("--end-date must be on or after --start-date.")
    if not -90 <= args.latitude <= 90:
        parser.error("--latitude must be between -90 and 90.")
    if not -180 <= args.longitude <= 180:
        parser.error("--longitude must be between -180 and 180.")

    daily_variables = [value.strip() for value in args.daily.split(",") if value.strip()]
    if not daily_variables:
        parser.error("--daily must contain at least one variable.")

    try:
        with requests.Session() as session:
            payload = fetch_weather(
                latitude=args.latitude,
                longitude=args.longitude,
                start_date=args.start_date,
                end_date=args.end_date,
                timezone=args.timezone,
                daily_variables=daily_variables,
                temperature_unit=args.temperature_unit,
                session=session,
            )

        frame = build_dataframe(payload["daily"])
        if not args.no_features:
            frame = add_features(
                frame,
                temperature_unit=args.temperature_unit,
                heat_wave_threshold=args.heat_wave_threshold,
                freeze_threshold=args.freeze_threshold,
                heavy_rain_threshold=args.heavy_rain_threshold,
                high_wind_threshold=args.high_wind_threshold,
            )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
    except (requests.RequestException, ValueError, OSError) as exc:
        parser.error(str(exc))

    print(f"Saved {len(frame)} daily observation(s) to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
