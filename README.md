# Open-Meteo Historical Weather Data

Download daily historical weather data for a location and date range from the
[Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api).
Choose coordinates, dates, timezone, units, and daily variables from the command
line. The tool can also add rolling averages, lag values, event indicators, and
calendar features to the downloaded observations.

## Requirements

- Python 3.9 or newer

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Example

Download daily weather for Atlanta from 2000 through 2024:

```bash
python weather_data.py \
  --latitude 33.64 \
  --longitude -84.42 \
  --start-date 2000-01-01 \
  --end-date 2024-12-31 \
  --timezone America/New_York \
  --output atlanta_weather.csv
```

By default, the tool requests the daily variables listed in
[`weather_data.py`](./weather_data.py) and adds derived features. To request a
smaller set of variables, pass a comma-separated list:

```bash
python weather_data.py \
  --latitude 40.71 \
  --longitude -74.01 \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --daily temperature_2m_max,temperature_2m_min,precipitation_sum \
  --output new_york_2020.csv
```

Use `--no-features` to save only API observations and the date column. The
temperature unit is Celsius by default; pass `--temperature-unit fahrenheit` to
request Fahrenheit. `--heat-wave-threshold` and `--freeze-threshold` use the
selected temperature unit. Heavy-rain thresholds are in millimeters, and
high-wind thresholds are in kilometers per hour (the API's default wind-speed
unit). Output directories are created automatically.

## Data source and attribution

Weather observations come from Open-Meteo and its upstream providers. Review the
[Open-Meteo documentation](https://open-meteo.com/en/docs/historical-weather-api)
and [terms](https://open-meteo.com/en/terms) for current attribution,
availability, and usage requirements. This project is independent and is not
affiliated with Open-Meteo.

## License

No license has been selected for this project. The source code is publicly
visible, but others do not automatically receive permission to reuse or
redistribute it.
