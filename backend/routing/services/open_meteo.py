"""
Open-Meteo Weather Forecast API service module.
Provides hourly forecast retrieval, timestamp matching against checkpoint arrival times,
unit conversions (wind speed in mph, precipitation & snowfall intensity in in/h),
missing value handling without zero-replacement, and graceful error degradation.
Does not require or expose any secrets.
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple
import requests

from .weather_engine import BaseWeatherEngine

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Exceptions
# -------------------------------------------------------------------------

class WeatherServiceError(Exception):
    """Base exception for weather service errors."""
    pass


class WeatherProviderError(WeatherServiceError):
    """Raised when the weather provider returns an HTTP error or malformed payload."""
    pass


class WeatherTimeoutError(WeatherServiceError):
    """Raised when the request to the weather provider times out."""
    pass


class WeatherConnectionError(WeatherServiceError):
    """Raised when a network connection error occurs while reaching the weather provider."""
    pass


class WeatherRateLimitError(WeatherServiceError):
    """Raised when the weather provider rate limit is exceeded (HTTP 429)."""
    pass


# -------------------------------------------------------------------------
# WMO Weather Interpretation Codes (WMO Code 4677)
# -------------------------------------------------------------------------

WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


# -------------------------------------------------------------------------
# Service Implementation
# -------------------------------------------------------------------------

class OpenMeteoWeatherService(BaseWeatherEngine):
    """
    Retrieves weather forecasts from the Open-Meteo Forecast API.
    Operates without API keys. Uses hourly forecasts matched to checkpoint estimated arrival times.
    """

    DEFAULT_BASE_URL = "https://api.open-meteo.com/v1/forecast"
    DEFAULT_TIMEOUT_SECONDS = 10.0
    HOURLY_VARIABLES = (
        "temperature_2m,"
        "precipitation_probability,"
        "precipitation,"
        "snowfall,"
        "weather_code,"
        "wind_speed_10m,"
        "wind_gusts_10m"
    )

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = timeout

    def fetch_forecast_raw(
        self,
        unique_coords: List[Tuple[float, float]],
    ) -> List[Dict[str, Any]]:
        """
        Calls Open-Meteo forecast API for a list of unique (lat, lon) coordinates in batch.
        Returns a list of raw forecast dictionaries corresponding to each coordinate.
        """
        if not unique_coords:
            return []

        MAX_CHUNK_SIZE = 25
        results: List[Dict[str, Any]] = []

        # If 25 or fewer coordinates, single request; otherwise chunk into batches of 25
        coord_chunks = (
            [unique_coords]
            if len(unique_coords) <= MAX_CHUNK_SIZE
            else [unique_coords[i : i + MAX_CHUNK_SIZE] for i in range(0, len(unique_coords), MAX_CHUNK_SIZE)]
        )

        for chunk in coord_chunks:
            latitudes_str = ",".join(f"{lat:.4f}" for lat, _ in chunk)
            longitudes_str = ",".join(f"{lon:.4f}" for _, lon in chunk)

            params = {
                "latitude": latitudes_str,
                "longitude": longitudes_str,
                "hourly": self.HOURLY_VARIABLES,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "temperature_unit": "fahrenheit",
                "timezone": "UTC",
            }

            response = None
            for attempt in range(2):
                try:
                    response = requests.get(
                        self.base_url,
                        params=params,
                        timeout=self.timeout,
                    )
                    if response.status_code == 503 and attempt == 0:
                        import time
                        time.sleep(0.5)
                        continue
                    break
                except requests.exceptions.Timeout as exc:
                    if attempt == 0:
                        import time
                        time.sleep(0.5)
                        continue
                    logger.warning("Open-Meteo forecast request timed out: %s", exc)
                    raise WeatherTimeoutError("Weather provider request timed out.") from exc
                except requests.exceptions.ConnectionError as exc:
                    logger.error("Open-Meteo connection failure: %s", exc)
                    raise WeatherConnectionError("Unable to connect to weather forecast provider.") from exc
                except requests.exceptions.RequestException as exc:
                    logger.error("Open-Meteo request error: %s", exc)
                    raise WeatherServiceError(f"Weather request error: {exc}") from exc

            if response is None:
                raise WeatherTimeoutError("Weather provider request timed out.")

            if response.status_code == 429:
                logger.warning("Open-Meteo rate limit exceeded.")
                raise WeatherRateLimitError("Weather provider rate limit exceeded.")

            if response.status_code == 400:
                logger.warning("Open-Meteo returned HTTP 400 Bad Request.")
                raise WeatherProviderError("Weather provider rejected request (invalid coordinates or query).")

            if not response.ok:
                logger.error("Open-Meteo returned HTTP %s", response.status_code)
                raise WeatherProviderError(f"Weather provider returned status code {response.status_code}.")

            try:
                data = response.json()
            except ValueError as exc:
                logger.error("Open-Meteo returned invalid JSON: %s", exc)
                raise WeatherProviderError("Weather provider returned malformed JSON.") from exc

            # When querying multiple coordinates, Open-Meteo returns a JSON list.
            # When querying a single coordinate, it returns a single JSON object.
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                if data.get("error"):
                    reason = data.get("reason", "Unknown provider error")
                    raise WeatherProviderError(f"Weather provider error: {reason}")
                # If multiple coordinates were requested but provider or mock returned a single dict,
                # replicate it across all requested unique coordinates in this chunk
                results.extend([data] * len(chunk))
            else:
                raise WeatherProviderError("Unexpected response format from weather provider.")

        # Basic structure validation
        for res in results:
            if not isinstance(res, dict) or "hourly" not in res:
                raise WeatherProviderError("Weather provider response missing required 'hourly' block.")

        return results

    def _parse_utc_datetime(self, val: Any) -> Optional[datetime]:
        """Safely parses a datetime or ISO string into a timezone-aware UTC datetime."""
        if val is None:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc)
        if isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError):
                return None
        return None

    def match_forecast_for_arrival(
        self,
        forecast_data: Dict[str, Any],
        arrival_dt: Optional[datetime],
    ) -> Dict[str, Any]:
        """
        Matches a checkpoint's arrival datetime to the nearest hourly forecast slot.
        Handles horizon limits, missing values, and unit conversions.
        """
        default_units = {
            "temperature": "°F",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "precipitation": "in/h",
            "snowfall": "in/h",
            "precipitation_probability": "%",
            "visibility": "miles",
        }

        if arrival_dt is None:
            return {
                "timestamp": None,
                "forecast_timestamp": None,
                "data_availability": "unavailable",
                "temperature": None,
                "condition": None,
                "weather_code": None,
                "wind_speed_mph": None,
                "wind_gust_mph": None,
                "precipitation_probability": None,
                "precipitation_in_per_hour": None,
                "snowfall_in_per_hour": None,
                "precipitation_rate_in_per_hour": None,
                "snowfall_rate_in_per_hour": None,
                "precipitation_accumulation_in": None,
                "snowfall_accumulation_in": None,
                "visibility_miles": None,
                "notes": "Checkpoint is missing estimated arrival time.",
                "limitations": ["Forecast matching requires an arrival timestamp."],
                "units": default_units,
            }

        hourly = forecast_data.get("hourly", {})
        time_strings = hourly.get("time", [])

        if not time_strings:
            return {
                "timestamp": arrival_dt.isoformat(),
                "forecast_timestamp": None,
                "data_availability": "unavailable",
                "temperature": None,
                "condition": None,
                "weather_code": None,
                "wind_speed_mph": None,
                "wind_gust_mph": None,
                "precipitation_probability": None,
                "precipitation_in_per_hour": None,
                "snowfall_in_per_hour": None,
                "precipitation_rate_in_per_hour": None,
                "snowfall_rate_in_per_hour": None,
                "precipitation_accumulation_in": None,
                "snowfall_accumulation_in": None,
                "visibility_miles": None,
                "notes": "No hourly forecast records provided by weather service.",
                "limitations": ["Hourly forecast array was empty."],
                "units": default_units,
            }

        # Parse all hourly time slots
        parsed_slots: List[Tuple[int, datetime]] = []
        for idx, t_str in enumerate(time_strings):
            parsed = self._parse_utc_datetime(t_str)
            if parsed:
                parsed_slots.append((idx, parsed))

        if not parsed_slots:
            return {
                "timestamp": arrival_dt.isoformat(),
                "forecast_timestamp": None,
                "data_availability": "unavailable",
                "temperature": None,
                "condition": None,
                "weather_code": None,
                "wind_speed_mph": None,
                "wind_gust_mph": None,
                "precipitation_probability": None,
                "precipitation_in_per_hour": None,
                "snowfall_in_per_hour": None,
                "precipitation_rate_in_per_hour": None,
                "snowfall_rate_in_per_hour": None,
                "precipitation_accumulation_in": None,
                "snowfall_accumulation_in": None,
                "visibility_miles": None,
                "notes": "Could not parse hourly forecast timestamps.",
                "limitations": ["Hourly timestamps could not be parsed into UTC datetimes."],
                "units": default_units,
            }

        # Check forecast horizon boundaries (allow within +/- 2 hours of closest slot)
        first_slot = parsed_slots[0][1]
        last_slot = parsed_slots[-1][1]

        if arrival_dt < (first_slot - timedelta(hours=2)) or arrival_dt > (last_slot + timedelta(hours=2)):
            return {
                "timestamp": arrival_dt.isoformat(),
                "forecast_timestamp": None,
                "data_availability": "out_of_forecast_horizon",
                "temperature": None,
                "condition": None,
                "weather_code": None,
                "wind_speed_mph": None,
                "wind_gust_mph": None,
                "precipitation_probability": None,
                "precipitation_in_per_hour": None,
                "snowfall_in_per_hour": None,
                "precipitation_rate_in_per_hour": None,
                "snowfall_rate_in_per_hour": None,
                "precipitation_accumulation_in": None,
                "snowfall_accumulation_in": None,
                "visibility_miles": None,
                "notes": (
                    f"Arrival time ({arrival_dt.isoformat()}) is outside the available Open-Meteo forecast "
                    f"horizon ({first_slot.isoformat()} to {last_slot.isoformat()})."
                ),
                "limitations": [
                    "Forecast data is only available within provider horizon (typically up to 7-14 days). "
                    "Weather values are preserved as null rather than defaulted to zero."
                ],
                "units": default_units,
            }

        # Find closest hourly slot
        best_idx, best_dt = min(
            parsed_slots,
            key=lambda item: abs((item[1] - arrival_dt).total_seconds()),
        )

        # Extract values for the slot
        def get_val(key: str) -> Any:
            arr = hourly.get(key, [])
            if best_idx < len(arr):
                return arr[best_idx]
            return None

        raw_temp = get_val("temperature_2m")
        raw_wcode = get_val("weather_code")
        raw_wspeed = get_val("wind_speed_10m")
        raw_wgust = get_val("wind_gusts_10m")
        raw_pprob = get_val("precipitation_probability")
        raw_precip = get_val("precipitation")
        raw_snow = get_val("snowfall")

        # Type conversion and validation preserving nulls (NEVER default to 0.0)
        temp_val = round(float(raw_temp), 1) if raw_temp is not None else None
        wcode_val = int(raw_wcode) if raw_wcode is not None else None
        condition_val = WMO_WEATHER_CODES.get(wcode_val) if wcode_val is not None else None

        wind_speed_mph = round(float(raw_wspeed), 1) if raw_wspeed is not None else None
        wind_gust_mph = round(float(raw_wgust), 1) if raw_wgust is not None else None
        precip_prob = float(raw_pprob) if raw_pprob is not None else None

        precip_accum = round(float(raw_precip), 2) if raw_precip is not None else None
        snow_accum = round(float(raw_snow), 2) if raw_snow is not None else None

        # Intensity calculation rules:
        # Open-Meteo 'precipitation' is preceding 1-hour liquid equivalent in inches.
        # Open-Meteo 'snowfall' is preceding 1-hour snowfall depth in inches.
        # For a 1-hour accumulation window, the hourly average rate is accumulated value / 1 hour = value in/h.
        # If raw value is null, rate is null (unavailable).
        precipitation_in_per_hour = precip_accum
        snowfall_in_per_hour = snow_accum

        limitations: List[str] = [
            "Open-Meteo reports preceding 1-hour accumulated precipitation and snowfall depth. "
            "Hourly precipitation and snowfall rates reflect 1-hour averages derived from these accumulations, "
            "not instantaneous radar reflectivity rates."
        ]

        has_missing = any(v is None for v in (wind_speed_mph, precipitation_in_per_hour, snowfall_in_per_hour))
        if has_missing:
            limitations.append(
                "One or more core weather variables were missing from the provider response and were "
                "represented as null rather than treated as zero."
            )
            data_availability = "partial"
        else:
            data_availability = "available"

        return {
            "timestamp": arrival_dt.isoformat(),
            "forecast_timestamp": best_dt.isoformat(),
            "data_availability": data_availability,
            "temperature": temp_val,
            "condition": condition_val,
            "weather_code": wcode_val,
            "wind_speed_mph": wind_speed_mph,
            "wind_gust_mph": wind_gust_mph,
            "precipitation_probability": precip_prob,
            "precipitation_in_per_hour": precipitation_in_per_hour,
            "snowfall_in_per_hour": snowfall_in_per_hour,
            "precipitation_rate_in_per_hour": precipitation_in_per_hour,
            "snowfall_rate_in_per_hour": snowfall_in_per_hour,
            "precipitation_accumulation_in": precip_accum,
            "snowfall_accumulation_in": snow_accum,
            "visibility_miles": None,
            "notes": None,
            "limitations": limitations,
            "units": default_units,
        }

    def get_weather_for_checkpoints(
        self,
        checkpoints: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Retrieves weather forecasts for checkpoints using their real coordinates and estimated arrival times.
        Deduplicates coordinates to avoid unnecessary repeated API calls.
        Updates each checkpoint's 'weather' field in-place and returns the list.
        """
        if not checkpoints:
            return checkpoints

        # Deduplicate coordinates by rounding to 3 decimal places (~110m)
        unique_coord_map: Dict[Tuple[float, float], Tuple[float, float]] = {}
        for cp in checkpoints:
            lat = float(cp["latitude"])
            lon = float(cp["longitude"])
            key = (round(lat, 3), round(lon, 3))
            if key not in unique_coord_map:
                unique_coord_map[key] = (lat, lon)

        unique_coords = list(unique_coord_map.values())
        coord_to_index = {coord: idx for idx, coord in enumerate(unique_coords)}

        try:
            forecast_results = self.fetch_forecast_raw(unique_coords)
        except WeatherServiceError as exc:
            logger.warning("Weather retrieval failed: %s", exc)
            # Annotate all checkpoints as unavailable rather than crashing
            err_msg = str(exc)
            for cp in checkpoints:
                arr_dt = self._parse_utc_datetime(cp.get("estimated_arrival"))
                cp["weather"] = {
                    "timestamp": arr_dt.isoformat() if arr_dt else None,
                    "forecast_timestamp": None,
                    "data_availability": "unavailable",
                    "temperature": None,
                    "condition": None,
                    "weather_code": None,
                    "wind_speed_mph": None,
                    "wind_gust_mph": None,
                    "precipitation_probability": None,
                    "precipitation_in_per_hour": None,
                    "snowfall_in_per_hour": None,
                    "precipitation_rate_in_per_hour": None,
                    "snowfall_rate_in_per_hour": None,
                    "precipitation_accumulation_in": None,
                    "snowfall_accumulation_in": None,
                    "visibility_miles": None,
                    "notes": f"Weather data unavailable: {err_msg}",
                    "limitations": ["Weather forecast provider was unreachable or returned an error."],
                    "units": {
                        "temperature": "°F",
                        "wind_speed": "mph",
                        "wind_gust": "mph",
                        "precipitation": "in/h",
                        "snowfall": "in/h",
                        "precipitation_probability": "%",
                        "visibility": "miles",
                    },
                }
            return checkpoints

        # Match each checkpoint with the appropriate forecast
        for cp in checkpoints:
            lat = float(cp["latitude"])
            lon = float(cp["longitude"])
            key = (round(lat, 3), round(lon, 3))
            canonical_coord = unique_coord_map.get(key, (lat, lon))
            coord_idx = coord_to_index.get(canonical_coord, 0)

            forecast_data = forecast_results[coord_idx] if coord_idx < len(forecast_results) else {}
            arr_dt = self._parse_utc_datetime(cp.get("estimated_arrival"))

            cp["weather"] = self.match_forecast_for_arrival(forecast_data, arr_dt)
            cp["hourly_forecast"] = self.extract_hourly_forecast_series(forecast_data, arr_dt)

        return checkpoints

    def extract_hourly_forecast_series(
        self,
        forecast_data: Dict[str, Any],
        base_dt: Optional[datetime],
        hours: int = 48,
    ) -> List[Dict[str, Any]]:
        """
        Extracts hourly forecast observations for a 0–48 hour horizon relative to base_dt.
        """
        if not forecast_data or not base_dt:
            return []

        hourly = forecast_data.get("hourly", {})
        time_strings = hourly.get("time", [])
        if not time_strings:
            return []

        slot_map: Dict[str, int] = {}
        for idx, t_str in enumerate(time_strings):
            parsed = self._parse_utc_datetime(t_str)
            if parsed:
                slot_map[parsed.strftime("%Y-%m-%dT%H:00")] = idx

        start_hour = base_dt.replace(minute=0, second=0, microsecond=0)
        series = []

        temps = hourly.get("temperature_2m", [])
        wcodes = hourly.get("weather_code", [])
        wspeeds = hourly.get("wind_speed_10m", [])
        wgusts = hourly.get("wind_gusts_10m", [])
        precips = hourly.get("precipitation", [])
        snows = hourly.get("snowfall", [])
        pprobs = hourly.get("precipitation_probability", [])

        for h in range(hours + 1):
            slot_dt = start_hour + timedelta(hours=h)
            slot_key = slot_dt.strftime("%Y-%m-%dT%H:00")
            idx = slot_map.get(slot_key)
            if idx is not None and idx < len(temps):
                raw_temp = temps[idx]
                raw_wcode = wcodes[idx] if idx < len(wcodes) else None
                raw_wspeed = wspeeds[idx] if idx < len(wspeeds) else None
                raw_wgust = wgusts[idx] if idx < len(wgusts) else None
                raw_precip = precips[idx] if idx < len(precips) else None
                raw_snow = snows[idx] if idx < len(snows) else None
                raw_pprob = pprobs[idx] if idx < len(pprobs) else None

                temp_val = round(float(raw_temp), 1) if raw_temp is not None else None
                wcode_val = int(raw_wcode) if raw_wcode is not None else None
                wind_mph = round(float(raw_wspeed), 1) if raw_wspeed is not None else None
                gust_mph = round(float(raw_wgust), 1) if raw_wgust is not None else None
                precip_rate = round(float(raw_precip), 2) if raw_precip is not None else None
                snow_rate = round(float(raw_snow), 2) if raw_snow is not None else None

                series.append({
                    "forecast_timestamp": slot_dt.isoformat(),
                    "hour_offset": h,
                    "temperature": temp_val,
                    "condition": WMO_WEATHER_CODES.get(wcode_val) if wcode_val is not None else None,
                    "weather_code": wcode_val,
                    "wind_speed_mph": wind_mph,
                    "wind_gust_mph": gust_mph,
                    "precipitation_in_per_hour": precip_rate,
                    "snowfall_in_per_hour": snow_rate,
                    "precipitation_rate_in_per_hour": precip_rate,
                    "snowfall_rate_in_per_hour": snow_rate,
                    "precipitation_probability": float(raw_pprob) if raw_pprob is not None else None,
                })

        return series

    def attach_weather_to_routes(
        self,
        routes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Attaches weather observations to all checkpoints across routes and computes a weather summary.
        """
        for route in routes:
            cps = route.get("checkpoints", [])
            if not cps:
                continue

            self.get_weather_for_checkpoints(cps)

            # Compute route-level weather summary
            wind_speeds = [
                cp["weather"]["wind_speed_mph"]
                for cp in cps
                if cp.get("weather") and cp["weather"].get("wind_speed_mph") is not None
            ]
            precip_rates = [
                cp["weather"]["precipitation_in_per_hour"]
                for cp in cps
                if cp.get("weather") and cp["weather"].get("precipitation_in_per_hour") is not None
            ]
            snow_rates = [
                cp["weather"]["snowfall_in_per_hour"]
                for cp in cps
                if cp.get("weather") and cp["weather"].get("snowfall_in_per_hour") is not None
            ]
            conditions = sorted({
                cp["weather"]["condition"]
                for cp in cps
                if cp.get("weather") and cp["weather"].get("condition")
            })
            available_count = sum(
                1 for cp in cps
                if cp.get("weather") and cp["weather"].get("data_availability") in ("available", "partial")
            )

            route["weather_summary"] = {
                "total_checkpoints": len(cps),
                "available_checkpoints": available_count,
                "max_wind_speed_mph": max(wind_speeds) if wind_speeds else None,
                "max_precipitation_in_per_hour": max(precip_rates) if precip_rates else None,
                "max_snowfall_in_per_hour": max(snow_rates) if snow_rates else None,
                "conditions_observed": conditions,
                "provider": "Open-Meteo Forecast API",
                "limitations": (
                    "Hourly precipitation and snowfall represent 1-hour average rates derived from "
                    "accumulated forecast amounts, not instantaneous radar rates. "
                    "Missing values are preserved as null."
                ),
            }

        return routes
