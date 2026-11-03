import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import requests

from weather_data import add_features, build_dataframe, fetch_weather, main


def api_response():
    return {
        "daily": {
            "time": ["2024-01-01", "2024-01-02"],
            "temperature_2m_max": [36.0, 20.0],
            "temperature_2m_min": [2.0, -1.0],
            "temperature_2m_mean": [18.0, 10.0],
            "precipitation_sum": [30.0, 0.0],
            "wind_speed_10m_max": [45.0, 10.0],
        }
    }


class FetchWeatherTests(unittest.TestCase):
    def test_build_dataframe_parses_date_and_sorts_rows(self):
        result = build_dataframe(
            {"time": ["2024-01-02", "2024-01-01"], "temperature_2m_max": [2, 1]}
        )

        self.assertEqual(result["date"].dt.strftime("%Y-%m-%d").tolist(), [
            "2024-01-01",
            "2024-01-02",
        ])
        self.assertEqual(result["temperature_2m_max"].tolist(), [1, 2])

    def test_fetch_sends_config_and_checks_response(self):
        session = MagicMock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = api_response()

        result = fetch_weather(
            latitude=33.64,
            longitude=-84.42,
            start_date="2024-01-01",
            end_date="2024-01-02",
            timezone="America/New_York",
            daily_variables=["temperature_2m_max"],
            temperature_unit="celsius",
            session=session,
        )

        self.assertIn("daily", result)
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["params"]["daily"], "temperature_2m_max")
        self.assertEqual(kwargs["params"]["temperature_unit"], "celsius")
        session.get.return_value.raise_for_status.assert_called_once()

    def test_retries_temporary_server_error(self):
        session = MagicMock()
        first = MagicMock(status_code=503)
        second = MagicMock(status_code=200)
        second.json.return_value = api_response()
        session.get.side_effect = [first, second]

        with patch("weather_data.time.sleep") as sleep:
            result = fetch_weather(
                latitude=33.64,
                longitude=-84.42,
                start_date="2024-01-01",
                end_date="2024-01-02",
                timezone="auto",
                daily_variables=["temperature_2m_max"],
                temperature_unit="celsius",
                session=session,
            )

        self.assertIn("daily", result)
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_rejects_mismatched_daily_arrays(self):
        with self.assertRaisesRegex(ValueError, "matching lengths"):
            build_dataframe({"time": ["2024-01-01"], "temperature_2m_max": [1, 2]})


class FeatureTests(unittest.TestCase):
    def test_add_features_uses_celsius_thresholds_and_calendar(self):
        frame = build_dataframe(api_response()["daily"])

        result = add_features(frame, temperature_unit="celsius")

        self.assertEqual(result["heat_wave"].tolist(), [1, 0])
        self.assertEqual(result["freeze"].tolist(), [0, 1])
        self.assertEqual(result["heavy_rain"].tolist(), [1, 0])
        self.assertEqual(result["high_wind"].tolist(), [1, 0])
        self.assertEqual(result["month"].tolist(), [1, 1])
        self.assertEqual(result["year"].tolist(), [2024, 2024])
        self.assertTrue(pd.isna(result.loc[0, "temp_7d_avg"]))

    def test_fahrenheit_thresholds_match_api_unit(self):
        frame = build_dataframe(
            {"time": ["2024-07-01"], "temperature_2m_max": [96], "temperature_2m_min": [31]}
        )

        result = add_features(frame, temperature_unit="fahrenheit")

        self.assertEqual(result["heat_wave"].tolist(), [1])
        self.assertEqual(result["freeze"].tolist(), [1])


class CommandLineTests(unittest.TestCase):
    @patch("weather_data.fetch_weather")
    def test_writes_csv_with_features(self, fetch_mock):
        fetch_mock.return_value = api_response()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "weather.csv"

            result = main(
                [
                    "--latitude",
                    "33.64",
                    "--longitude",
                    "-84.42",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-01-02",
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(result, 0)
            self.assertTrue(output_path.is_file())
            output = pd.read_csv(output_path)
            self.assertIn("heat_wave", output.columns)
            self.assertEqual(output["year"].tolist(), [2024, 2024])

    def test_rejects_invalid_date_range(self):
        with self.assertRaises(SystemExit) as error:
            main(
                [
                    "--latitude",
                    "33.64",
                    "--longitude",
                    "-84.42",
                    "--start-date",
                    "2024-01-02",
                    "--end-date",
                    "2024-01-01",
                ]
            )

        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
