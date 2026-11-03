# Open-Meteo Historical Weather Data

A command line tool for downloading daily historical weather for any location and date range from the [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api). It is written for educational use and as a general purpose helper for research projects that need weather data for one or many locations.

You choose the coordinates, dates, timezone, units, and daily variables. The tool can also add rolling averages, lag values, event indicators (heat wave, freeze, heavy rain, high wind), and calendar features to the downloaded observations.

## Requirements

Python 3.9 or newer. Create and activate a virtual environment, then install dependencies:

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

By default the tool requests the daily variables listed in [`weather_data.py`](./weather_data.py) and adds derived features. To request fewer variables, pass a comma separated list:

```bash
python weather_data.py \
  --latitude 40.71 \
  --longitude -74.01 \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --daily temperature_2m_max,temperature_2m_min,precipitation_sum \
  --output new_york_2020.csv
```

Use `--no-features` to save only API observations and the date column. Temperature is in Celsius by default; pass `--temperature-unit fahrenheit` for Fahrenheit. The `--heat-wave-threshold` and `--freeze-threshold` options use the selected temperature unit. Heavy rain thresholds are in millimeters and high wind thresholds are in kilometers per hour. Output directories are created automatically.

To cover several locations, run the tool once per location and combine the files.

## Data source and attribution

Weather observations come from Open-Meteo and its upstream providers. Review the [documentation](https://open-meteo.com/en/docs/historical-weather-api) and [terms](https://open-meteo.com/en/terms) for attribution and usage requirements. This project is independent and not affiliated with Open-Meteo.

## License

No license has been selected. The source code is publicly visible, but others do not automatically receive permission to reuse or redistribute it.
