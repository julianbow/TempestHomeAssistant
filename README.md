# Tempest Integration for Home Assistant
Home Assistant integration for Tempest using local UDP and REST API

<p align="center">
  <img width="384" src="https://github.com/julianbow/TempestHomeAssistant/blob/master/images/logo@2x.png?raw=true">
</p>

This integration adds support for retrieving the Forecast, Current condition and optionally realtime data from your Tempest weather station. **This is a BETA Build and should only be used for testing purposes.**

For this integration you **must own a Tempest weather station**. This integration uses OAuth to hook up your station to the Tempest API.

#### This integration will set up the following platforms.

Platform | Description
-- | --
`weather` | A Home Assistant `weather` entity, with current data, daily- and hourly forecast data.
`sensor` | A Home Assistant `sensor` entity, with all available sensor from the API, plus a few local calculated.

## Installation through HACS (Recommended Method)

This Integration is part of the default HACS store. Search for Tempest under Integrations and install from there. You can also download using this My link:

After the installation of the files, you must restart Home Assistant, or else you will not be able to add Tempest from the Integration Page.

Once restarted, you can go to "Configuration" -> "Integrations" click "+" and search for "Tempest" or use this My link:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tempest)

If you are not familiar with HACS, or haven't installed it, I would recommend to [look through the HACS documentation](https://hacs.xyz/), before continuing. Even though you can install the Integration manually, I would recommend using HACS, as you would always be reminded when a new release is published.

## Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `tempest`.
4. Download _all_ the files from the `custom_components/tempest/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "WeatherFlow Forecast" or use this My link:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=weatherflow_forecast)

## Configuration

To add Tempest to your installation, do the following:

- Go to Configuration and Integrations
- Click the + ADD INTEGRATION button in the lower right corner.
- Search for *Tempest** and click the integration.
- When loaded, there will be a configuration box, where you must choose either local or cloud.
- If you click cloud, it will redirect to tempest website where you will have to authorize the integration.

You can only configure one of each instance.