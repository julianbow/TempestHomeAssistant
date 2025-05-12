"""Unified sensor platform for Tempest integration (local UDP and cloud REST)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import logging
from typing import Any

from pyweatherflowudp.const import EVENT_RAPID_WIND
from pyweatherflowudp.device import (
    EVENT_OBSERVATION,
    EVENT_STATUS_UPDATE,
    WeatherFlowDevice,
)
from weatherflow4py.models.rest.observation import Observation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UV_INDEX,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN, format_dispatch_call
from .coordinator import WeatherFlowCloudDataUpdateCoordinator
from .entity import WeatherFlowCloudEntity

_LOGGER = logging.getLogger(__name__)


def _precipitation_raw_conversion_fn(raw_data: Enum) -> str | None:
    """Convert raw precipitation enum to string or None."""
    if raw_data.name.lower() == "unknown":
        return None
    return raw_data.name.lower()


@dataclass(frozen=True, kw_only=True)
class WeatherFlowSensorEntityDescription(SensorEntityDescription):
    """Describes a WeatherFlow local sensor entity."""

    raw_data_conv_fn: Callable[[Any], datetime | StateType]
    event_subscriptions: list[str] = field(default_factory=lambda: [EVENT_OBSERVATION])
    imperial_suggested_unit: str | None = None

    def get_native_value(self, device: WeatherFlowDevice) -> datetime | StateType:
        """Return the parsed sensor value from a WeatherFlowDevice."""
        raw_val = getattr(device, self.key, None)
        if raw_val is None:
            return None
        return self.raw_data_conv_fn(raw_val)


# Local (UDP) sensor descriptions
SENSORS: tuple[WeatherFlowSensorEntityDescription, ...] = (
    WeatherFlowSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        native_unit_of_measurement="kg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="dew_point_temperature",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="feels_like_temperature",
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="battery",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="illuminance",
        translation_key="illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_average_distance",
        translation_key="lightning_average_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_count",
        state_class=SensorStateClass.TOTAL,
        raw_data_conv_fn=lambda d: d,
    ),
    WeatherFlowSensorEntityDescription(
        key="precipitation_type",
        translation_key="precipitation_type",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "rain", "hail", "rain_hail", "unknown"],
        raw_data_conv_fn=_precipitation_raw_conversion_fn,
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_accumulation_previous_minute",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        imperial_suggested_unit=UnitOfPrecipitationDepth.INCHES,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="relative_humidity",
        translation_key="relative_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        event_subscriptions=[EVENT_STATUS_UPDATE],
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="station_pressure",
        translation_key="station_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        imperial_suggested_unit=UnitOfPressure.INHG,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="solar_radiation",
        translation_key="solar_radiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="up_since",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        event_subscriptions=[EVENT_STATUS_UPDATE],
        raw_data_conv_fn=lambda d: d,
    ),
    WeatherFlowSensorEntityDescription(
        key="uv",
        translation_key="uv",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda d: d,
    ),
    WeatherFlowSensorEntityDescription(
        key="vapor_pressure",
        translation_key="vapor_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        imperial_suggested_unit=UnitOfPressure.INHG,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_average",
        translation_key="wind_speed_average",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        native_unit_of_measurement=DEGREE,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction_average",
        translation_key="wind_direction_average",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        native_unit_of_measurement=DEGREE,
        raw_data_conv_fn=lambda d: d.magnitude,
    ),
)


@dataclass(frozen=True, kw_only=True)
class WeatherFlowCloudSensorEntityDescription(SensorEntityDescription):
    """Describes a WeatherFlow cloud sensor entity."""

    value_fn: Callable[[Observation], StateType | datetime]


# Cloud (REST) sensor descriptions
WF_SENSORS: tuple[WeatherFlowCloudSensorEntityDescription, ...] = (
    WeatherFlowCloudSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        native_unit_of_measurement="kg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        value_fn=lambda d: d.air_density,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.air_temperature,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="station_pressure",
        translation_key="station_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: d.barometric_pressure,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="pressure_trend",
        translation_key="pressure_trend",
        value_fn=lambda d: d.pressure_trend,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="brightness",
        translation_key="brightness",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.brightness,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="delta_t",
        translation_key="delta_t",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.delta_t,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.dew_point,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="feels_like",
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.feels_like,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.heat_index,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_strike_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.lightning_strike_count,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count_last_3hr",
        translation_key="lightning_strike_count_last_3hr",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.lightning_strike_count_last_3hr,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_distance",
        translation_key="lightning_strike_last_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.lightning_strike_last_distance,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_epoch",
        translation_key="lightning_strike_last_epoch",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: datetime.fromtimestamp(d.lightning_strike_last_epoch, tz=UTC)
        if d.lightning_strike_last_epoch is not None
        else None,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="precip",
        translation_key="precip",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: d.precip,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="precip_accum_local_day_final",
        translation_key="precip_accum_local_day_final",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precip_accum_local_day_final,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="precip_accum_local_yesterday_final",
        translation_key="precip_accum_local_yesterday_final",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precip_accum_local_yesterday_final,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="precip_minutes_local_day",
        translation_key="precip_minutes_local_day",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precip_minutes_local_day,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="precip_minutes_local_yesterday",
        translation_key="precip_minutes_local_yesterday",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precip_minutes_local_yesterday,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="relative_humidity",
        translation_key="relative_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.relative_humidity,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="sea_level_pressure",
        translation_key="sea_level_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.sea_level_pressure,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="solar_radiation",
        translation_key="solar_radiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.solar_radiation,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="uv",
        translation_key="uv",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.uv,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="timestamp",
        translation_key="timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: datetime.fromtimestamp(d.timestamp, tz=UTC),
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wet_bulb_temperature,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_globe_temperature",
        translation_key="wet_bulb_globe_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wet_bulb_globe_temperature,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_avg",
        translation_key="wind_avg",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wind_avg,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_chill",
        translation_key="wind_chill",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wind_chill,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.wind_direction,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wind_gust,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.wind_lull,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all Tempest Test sensors, choosing local or cloud mode."""
    if "token" in entry.data:
        # Cloud mode
        coordinator = hass.data[DOMAIN][entry.entry_id]
        async_add_entities(
            WeatherFlowCloudSensor(coordinator, desc, station)
            for station in coordinator.data
            for desc in WF_SENSORS
        )
    else:
        # Local mode
        @callback
        def async_add_sensor(device: WeatherFlowDevice) -> None:
            _LOGGER.info("Adding local sensors for %s", device)
            entities = [
                WeatherFlowSensorEntity(
                    device=device,
                    entity_description=desc,
                    is_metric=(hass.config.units == METRIC_SYSTEM),
                )
                for desc in SENSORS
                if hasattr(device, desc.key)
            ]
            async_add_entities(entities)

        entry.async_on_unload(
            async_dispatcher_connect(
                hass,
                format_dispatch_call(entry),
                async_add_sensor,
            )
        )


class WeatherFlowSensorEntity(SensorEntity):
    """Local UDP WeatherFlow sensor entity."""

    entity_description: WeatherFlowSensorEntityDescription

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: WeatherFlowDevice,
        entity_description: WeatherFlowSensorEntityDescription,
        is_metric: bool = True,
    ) -> None:
        """Initialize local sensor entity."""
        self.device = device
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial_number}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            manufacturer="WeatherFlow",
            model=device.model,
            name=device.serial_number,
            sw_version=device.firmware_revision,
        )
        # Apply imperial unit override
        if entity_description.imperial_suggested_unit and not is_metric:
            self._attr_suggested_unit_of_measurement = (
                entity_description.imperial_suggested_unit
            )

    @property
    def last_reset(self) -> datetime | None:
        """Return last reset for total sensors."""
        if self.entity_description.state_class == SensorStateClass.TOTAL:
            return self.device.last_report
        return None

    def _async_update_state(self) -> None:
        """Fetch new data and write state."""
        val = self.entity_description.get_native_value(self.device)
        self._attr_available = val is not None
        self._attr_native_value = val
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events on add."""
        self._async_update_state()
        for evt in self.entity_description.event_subscriptions:
            self.async_on_remove(
                self.device.on(evt, lambda _: self._async_update_state())
            )


class WeatherFlowCloudSensor(WeatherFlowCloudEntity, SensorEntity):
    """REST cloud WeatherFlow sensor entity."""

    entity_description: WeatherFlowCloudSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        entity_description: WeatherFlowCloudSensorEntityDescription,
        station_id: int,
    ) -> None:
        """Initialize cloud sensor entity."""
        super().__init__(coordinator, station_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{station_id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return latest cloud value."""
        obs = self.station.observation.obs

        # log the full list and the first element
        _LOGGER.info(
            "WeatherFlowCloudSensor [%s] raw obs_list=%r",
            self.entity_description.key,
            obs,
        )
        return self.entity_description.value_fn(obs[0])
