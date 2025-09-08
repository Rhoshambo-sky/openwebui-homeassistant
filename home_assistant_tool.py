"""
title: Home Assistant Controls
author: Rhoshambo
Git Respository:https://github.com/Rhoshambo-sky/openwebui-homeassistant
description: Connects to a Home Assistant instance to control and query smart home devices using their human-readable names.
funding_url: https://github.com/open-webui
version: 0.2.0
Requirements: requests.txt; Read the README.md for more information.
License: MIT
"""

import os
import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        HA_URL: str = Field(
            default="http://homeassistant.local:8123",
            description="Home Assistant URL - The full URL of your Home Assistant instance (e.g., http://192.168.1.100:8123)."
        )
        HA_API_KEY: str = Field(
            default="",
            description="Home Assistant API Key - Your Long-Lived Access Token for Home Assistant."
        )
        HA_PRINTER_NOTIFY_SERVICE: str = Field(
            default="",
            description="Home Assistant Printer Notify Service - The name of the notify service to use for printing (e.g., 'my_cups_printer')."
        )
        HA_ALARM_CODE: str = Field(
            default="",
            description="Home Assistant Alarm Code - The code to arm or disarm the alarm system, if required."
        )

    # A map to handle plural, singular, and common aliases for Home Assistant domains.
    # Defined at the class level for clarity and to avoid re-declaration.
    DOMAIN_MAP = {
        "scenes": "scene",
        "scene": "scene",
        "automations": "automation",
        "automation": "automation",
        "lights": "light",
        "light": "light",
        "switches": "switch",
        "switch": "switch",
        "sensors": "sensor",
        "sensor": "sensor",
        "binary_sensors": "binary_sensor",
        "binary_sensor": "binary_sensor",
        "thermostats": "climate",
        "thermostat": "climate",
        "media_players": "media_player",
        "media_player": "media_player",
        "tvs": "media_player",
        "cameras": "camera",
        "camera": "camera",
        "covers": "cover",
        "cover": "cover",
        "blinds": "cover",
        "curtains": "cover",
        "garage_doors": "cover",
        "person": "person",
        "people": "person",
        "device_trackers": "device_tracker",
        "device_tracker": "device_tracker",
        "vacuums": "vacuum",
        "vacuum": "vacuum",
        "alarms": "alarm_control_panel",
        "alarm": "alarm_control_panel",
        "nas": "sensor", # NAS devices are represented by multiple sensors
        "network_storage": "sensor",
        "todo": "todo",
        "to-do": "todo",
        "todo_lists": "todo",
        "locks": "lock",
        "lock": "lock",
        "weather": "weather",
    }

    """
    A tool class for interacting with a Home Assistant instance. It can resolve human-readable
    device names (e.g., "Living Room Lamp") to their system IDs, control their state (on/off),
    and query their current status.
    """
    def __init__(self):
        """
        Initializes the Home Assistant tool, sets up configuration, and verifies the connection.
        Loads configuration from the OpenWebUI Valves system or environment variables.
        """
        self.valves = self.Valves()
        
        # Setup basic logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # Caching mechanism to avoid excessive API calls
        self.entities_cache: Optional[List[Dict]] = None
        self.entities_last_fetched: Optional[datetime] = None

        # Retrieve the configuration values from valves
        self.ha_url = self.valves.HA_URL
        self.ha_api_key = self.valves.HA_API_KEY

        if not self.ha_url or not self.ha_api_key:
            self.logger.warning("HA_URL and HA_API_KEY must be configured in the tool settings.")
            return

        # Clean up trailing slashes from the URL if they exist
        if self.ha_url.endswith("/"):
            self.ha_url = self.ha_url[:-1]

        # Set up a session for connection pooling and default headers
        self.session = requests.Session()
        if self.ha_api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.ha_api_key}",
                "Content-Type": "application/json",
            })

            # Verify the connection on startup to fail fast
            self._verify_connection()

    def _verify_connection(self):
        """Verifies the connection and authentication with Home Assistant on startup."""
        if not self.ha_url or not self.ha_api_key:
            self.logger.warning("Home Assistant URL or API key not configured.")
            return
            
        self.logger.info("Verifying connection to Home Assistant...")
        try:
            # A simple GET request to the base API endpoint to check connectivity and auth
            response = self.session.get(f"{self.ha_url}/api/")
            response.raise_for_status()
            self.logger.info("Home Assistant connection verified successfully.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.logger.error("Authentication failed. Please check your HA_API_KEY.")
                return
            self.logger.error(f"Failed to connect to Home Assistant (HTTP {e.response.status_code}): {e}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to {self.ha_url}. Please check the URL and network connectivity.")
            return

    def _get_all_entities(self) -> List[Dict]:
        """
        Fetches all entity states from Home Assistant, using a cache to avoid repeated calls.
        The cache expires after 60 seconds.
        """
        if not self.ha_url or not self.ha_api_key:
            return []
            
        if self.entities_cache and self.entities_last_fetched and \
           (datetime.now() - self.entities_last_fetched) < timedelta(seconds=60):
            return self.entities_cache

        try:
            response = self.session.get(f"{self.ha_url}/api/states")
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            self.entities_cache = response.json()
            self.entities_last_fetched = datetime.now()
            return self.entities_cache
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching entities from Home Assistant: {e}")
            self.entities_cache = None # Invalidate cache on error
            return []

    def _resolve_entity_id(self, device_name: str) -> Optional[str]:
        """
        Resolves a human-readable device name to its Home Assistant entity ID.
        It performs a case-insensitive search on the 'friendly_name' attribute.
        """
        entities = self._get_all_entities()
        for entity in entities:
            # Check if the friendly_name attribute exists and matches the device name
            if entity.get("attributes", {}).get("friendly_name", "").lower() == device_name.lower():
                return entity["entity_id"]
        return None

    def _get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """A centralized helper to get the state object for a single entity."""
        try:
            response = self.session.get(f"{self.ha_url}/api/states/{entity_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_message = f"An HTTP error occurred while getting state for {entity_id}: {e}. Response: {e.response.text}"
            self.logger.error(error_message)
            return None
        except requests.exceptions.RequestException as e:
            error_message = f"A network error occurred while getting state for {entity_id}: {e}"
            self.logger.error(error_message)
            return None

    def _call_service(self, domain: str, service: str, payload: Dict[str, Any], device_name_for_logging: str) -> Optional[str]:
        """
        A centralized helper to make a service call to Home Assistant.
        Handles endpoint construction, API call, and error handling.

        :param domain: The domain of the service (e.g., "light", "switch").
        :param service: The service to call (e.g., "turn_on", "set_temperature").
        :param payload: The data to send with the service call.
        :param device_name_for_logging: The friendly name of the device for logging purposes.
        :return: An error string if the call fails, otherwise None.
        """
        endpoint = f"{self.ha_url}/api/services/{domain}/{service}"
        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            return None  # Indicates success
        except requests.exceptions.HTTPError as e:
            error_message = f"An HTTP error occurred while controlling '{device_name_for_logging}': {e}. Response: {e.response.text}"
            self.logger.error(error_message)
            return error_message
        except requests.exceptions.RequestException as e:
            error_message = f"A network error occurred while controlling '{device_name_for_logging}': {e}"
            self.logger.error(error_message)
            return error_message

    def control_device_state(self, device_name: str, state: str) -> str:
        """
        Performs simple on/off control for any device. For advanced light controls (brightness, color), use the 'set_light_attributes' function.

        :param device_name: The friendly, human-readable name of the device to control, for example, "Bedroom Fan" or "Coffee Machine".
        :param state: The desired state for the device. Must be "on" or "off".
        :return: A user-facing confirmation of the action or a descriptive error message if it fails.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        # Infer domain from the entity_id (e.g., 'light.living_room' -> 'light')
        domain = entity_id.split('.')[0]

        # Map the simple state to a Home Assistant service
        service_map = {"on": "turn_on", "off": "turn_off"}
        service = service_map.get(state.lower())

        if not service:
            return f"Error: Unsupported state '{state}'. Please use 'on' or 'off'."

        payload = {"entity_id": entity_id}
        error = self._call_service(domain, service, payload, device_name)
        if error:
            return error
        return f"Successfully turned {state} the {device_name}."

    def set_light_attributes(
        self,
        device_name: str,
        state: Optional[str] = None,
        brightness_percent: Optional[int] = None,
        color_name: Optional[str] = None,
        kelvin: Optional[int] = None,
    ) -> str:
        """
        Controls multiple attributes of a light in a single command. This is the primary function for controlling lights.

        :param device_name: The friendly, human-readable name of the light to control.
        :param state: The desired state, either "on" or "off". If other attributes are set, the light will be turned on.
        :param brightness_percent: The desired brightness level as a percentage from 0 to 100.
        :param color_name: The desired color, specified by name (e.g., "red", "blue", "green").
        :param kelvin: The desired color temperature in Kelvin (e.g., 2700 for warm white, 6500 for cool white).
        :return: A user-facing confirmation of the actions taken or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("light."):
            return f"Error: The device '{device_name}' is not a light. Use the 'control_device_state' function for non-light devices."

        # If the state is 'off', we can ignore all other parameters and just turn the light off.
        if state and state.lower() == "off":
            return self.control_device_state(device_name, "off")

        # For all other cases, we use the 'turn_on' service and build the payload.
        payload = {"entity_id": entity_id}
        changes = []

        if brightness_percent is not None:
            if not 0 <= brightness_percent <= 100:
                return "Error: Brightness must be a percentage between 0 and 100."
            payload["brightness_pct"] = brightness_percent
            changes.append(f"brightness to {brightness_percent}%")

        if color_name:
            payload["color_name"] = color_name.lower()
            changes.append(f"color to {color_name}")

        if kelvin is not None:
            if not 1000 <= kelvin <= 10000:
                return "Error: Kelvin temperature must be an integer, typically between 1000 and 10000."
            payload["color_temp_kelvin"] = kelvin
            changes.append(f"color temperature to {kelvin}K")

        # If no attributes are set, it's a simple 'turn_on' command.
        if not changes and state and state.lower() == "on":
            pass  # The payload is already correct for a simple turn_on.
        elif not changes and not (state and state.lower() == "on"):
            return "No action taken. Please specify a state ('on'/'off') or at least one attribute to change for the light."

        error = self._call_service("light", "turn_on", payload, device_name)
        if error:
            return error
        if changes:
            return f"Successfully set {device_name} with {', '.join(changes)}."
        else:
            return f"Successfully turned on {device_name}."

    def get_device_status(self, device_name: str) -> str:
        """
        Checks and returns the current status of a specific device in Home Assistant.

        :param device_name: The friendly, human-readable name of the device to check, for example, "Front Door Lock" or "Living Room Thermostat".
        :return: A user-facing sentence describing the device's current state (e.g., "The current status of Living Room Lamp is on.") or an error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        data = self._get_entity_state(entity_id)
        if not data:
            return f"Error: Could not retrieve state for device '{device_name}'."
        state = data.get("state", "unknown")
        return f"The current status of {device_name} is {state}."

    def control_automation(self, automation_name: str, state: str) -> str:
        """
        Enables, disables, or triggers an existing automation in Home Assistant.

        :param automation_name: The friendly, human-readable name of the automation to control.
        :param state: The desired action. Must be "on" (enable), "off" (disable), or "trigger" (run now).
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(automation_name)
        if not entity_id:
            return f"Error: Could not find an automation named '{automation_name}'."

        if not entity_id.startswith("automation."):
            return f"Error: The entity '{automation_name}' is not an automation."

        state = state.lower()
        valid_states = {"on": "turn_on", "off": "turn_off", "trigger": "trigger"}
        service = valid_states.get(state)

        if not service:
            return f"Error: Invalid state '{state}'. Must be 'on', 'off', or 'trigger'."

        payload = {"entity_id": entity_id}
        error = self._call_service("automation", service, payload, automation_name)
        if error:
            return error
        action_map = {"on": "enabled", "off": "disabled", "trigger": "triggered"}
        return f"Successfully {action_map[state]} the '{automation_name}' automation."

    def activate_scene(self, scene_name: str) -> str:
        """
        Activates a scene in Home Assistant.

        :param scene_name: The friendly, human-readable name of the scene to activate.
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(scene_name)
        if not entity_id:
            return f"Error: Could not find a scene named '{scene_name}'."

        if not entity_id.startswith("scene."):
            return f"Error: The entity '{scene_name}' is not a scene."

        payload = {"entity_id": entity_id}
        error = self._call_service("scene", "turn_on", payload, scene_name)
        if error:
            return error
        return f"Successfully activated the '{scene_name}' scene."

    def list_available_entities(self, entity_type: str) -> str:
        """
        Lists all available entities of a specific type (e.g., lights, switches, scenes) by their friendly names.

        :param entity_type: The type of entity to list (e.g., "lights", "switches", "scenes", "automations", "sensors", "cameras").
        :return: A formatted string listing the available entities or a message if none are found.
        """
        domain = self.DOMAIN_MAP.get(entity_type.lower())

        if not domain:
            return f"Error: Invalid entity type '{entity_type}'. Please specify a valid type like 'lights', 'scenes', etc."

        all_entities = self._get_all_entities()
        found_entities = []
        for entity in all_entities:
            if entity.get("entity_id", "").startswith(f"{domain}."):
                friendly_name = entity.get("attributes", {}).get("friendly_name", entity["entity_id"])
                found_entities.append(friendly_name)

        if not found_entities:
            return f"No available {entity_type} found in Home Assistant."

        # Format the output nicely for the LLM to present.
        entity_list_str = "\n- ".join(found_entities)
        return f"Here are the available {entity_type}:\n- {entity_list_str}"

    def get_weather_forecast(self, device_name: str) -> str:
        """
        Gets the weather forecast from a specified weather entity.

        :param device_name: The friendly, human-readable name of the weather entity (e.g., "Home Weather").
        :return: A formatted string containing the weather forecast for the next few days.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a weather entity named '{device_name}'."

        if not entity_id.startswith("weather."):
            return f"Error: The entity '{device_name}' is not a weather entity."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            forecast_list = attributes.get("forecast")

            if not forecast_list:
                return f"The weather entity '{device_name}' does not have forecast data available."

            output_lines = [f"Weather forecast for {device_name}:"]
            temp_unit = attributes.get("temperature_unit", "°")

            for forecast in forecast_list[:3]:  # Limit to 3 days for brevity
                day = datetime.fromisoformat(forecast["datetime"]).strftime("%A")
                condition = forecast.get("condition", "unknown").capitalize()
                temp_high = forecast.get("temperature")
                temp_low = forecast.get("templow")
                precipitation = forecast.get("precipitation_probability", 0)
                output_lines.append(f"- {day}: {condition}, High: {temp_high}{temp_unit}, Low: {temp_low}{temp_unit}, Precipitation: {precipitation}%")
            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve weather forecast for '{device_name}'."

    def get_thermostat_status(self, device_name: str) -> str:
        """
        Gets the detailed status of a thermostat (climate device).

        :param device_name: The friendly, human-readable name of the thermostat.
        :return: A formatted string describing the thermostat's current state, target temperature, and action.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("climate."):
            return f"Error: The device '{device_name}' is not a thermostat."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            state = data.get("state", "unknown")
            current_temp = attributes.get("current_temperature")
            target_temp = attributes.get("temperature")
            hvac_action = attributes.get("hvac_action", "unknown")
            temp_unit = attributes.get("temperature_unit", "°")

            output_lines = [f"Status for {device_name} ({state}):"]
            if current_temp is not None:
                output_lines.append(f"- Current Temperature: {current_temp}{temp_unit}")
            if target_temp is not None:
                output_lines.append(f"- Target Temperature: {target_temp}{temp_unit}")
            output_lines.append(f"- Action: {hvac_action.replace('_', ' ').capitalize()}")
            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve thermostat status for '{device_name}'."

    def set_thermostat_attributes(
        self,
        device_name: str,
        temperature: Optional[float] = None,
        hvac_mode: Optional[str] = None,
    ) -> str:
        """
        Sets the temperature and/or HVAC mode for a thermostat (climate device).

        :param device_name: The friendly, human-readable name of the thermostat.
        :param temperature: The target temperature to set.
        :param hvac_mode: The desired HVAC mode (e.g., "heat", "cool", "off", "heat_cool").
        :return: A user-facing confirmation of the actions taken or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("climate."):
            return f"Error: The device '{device_name}' is not a thermostat."

        results = []

        # Set HVAC mode if provided
        if hvac_mode:
            hvac_mode = hvac_mode.lower()
            valid_modes = ["heat", "cool", "off", "heat_cool", "auto", "dry", "fan_only"]
            if hvac_mode not in valid_modes:
                return f"Error: Invalid HVAC mode '{hvac_mode}'. Valid modes are: {', '.join(valid_modes)}."

            payload = {"entity_id": entity_id, "hvac_mode": hvac_mode}
            error = self._call_service("climate", "set_hvac_mode", payload, device_name)
            if error:
                return error
            results.append(f"set mode to {hvac_mode}")

        # Set temperature if provided
        if temperature is not None:
            payload = {"entity_id": entity_id, "temperature": temperature}
            error = self._call_service("climate", "set_temperature", payload, device_name)
            if error:
                return error
            results.append(f"set temperature to {temperature}")

        if not results:
            return "No action taken. Please specify a temperature or HVAC mode to set."

        return f"Successfully processed actions for {device_name}: {', '.join(results)}."

    def get_media_player_sources(self, device_name: str) -> str:
        """
        Lists all available media sources for a specific media player (e.g., a TV or smart speaker).

        :param device_name: The friendly, human-readable name of the media player.
        :return: A formatted string listing the available media sources or an error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("media_player."):
            return f"Error: The device '{device_name}' is not a media player."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            source_list = attributes.get("source_list")

            if not source_list:
                return f"The media player '{device_name}' does not have a list of available sources."

            sources_str = "\n- ".join(source_list)
            return f"The following media sources are available for {device_name}:\n- {sources_str}"
        else:
            return f"Error: Could not retrieve media player sources for '{device_name}'."

    def get_tracker_status(self, device_name: str) -> str:
        """
        Gets the location status of a person or device tracker.

        :param device_name: The friendly, human-readable name of the person or device tracker.
        :return: A formatted string describing the tracker's current location and status.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a person or device tracker named '{device_name}'."

        if not (entity_id.startswith("person.") or entity_id.startswith("device_tracker.")):
            return f"Error: The entity '{device_name}' is not a person or device tracker."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            state = data.get("state", "unknown")
            friendly_name = attributes.get("friendly_name", device_name)

            # The state for trackers is the zone name (e.g., 'home', 'work').
            location = state.replace('_', ' ').capitalize()
            output_lines = [f"Location status for {friendly_name}: {location}"]

            if (battery_level := attributes.get("battery_level")) is not None:
                output_lines.append(f"- Battery: {battery_level}%")

            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve tracker status for '{device_name}'."

    def get_lock_status(self, device_name: str) -> str:
        """
        Gets the current status of a lock.

        :param device_name: The friendly, human-readable name of the lock.
        :return: A formatted string describing the lock's current state.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("lock."):
            return f"Error: The device '{device_name}' is not a lock."

        data = self._get_entity_state(entity_id)
        if data:
            state = data.get("state", "unknown")
            friendly_name = data.get("attributes", {}).get("friendly_name", device_name)

            if state == "locked":
                return f"The {friendly_name} is currently locked."
            elif state == "unlocked":
                return f"The {friendly_name} is currently unlocked."
            else:
                return f"The status of {friendly_name} is {state}."
        else:
            return f"Error: Could not retrieve lock status for '{device_name}'."

    def get_binary_sensor_status(self, device_name: str) -> str:
        """
        Gets the current status of a binary sensor (e.g., door, window, motion sensor).

        :param device_name: The friendly, human-readable name of the binary sensor.
        :return: A formatted string describing the sensor's current state (e.g., "The Front Door is open.").
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("binary_sensor."):
            return f"Error: The device '{device_name}' is not a binary sensor."

        data = self._get_entity_state(entity_id)
        if data:
            state = data.get("state", "unknown")
            attributes = data.get("attributes", {})
            friendly_name = attributes.get("friendly_name", device_name)
            device_class = attributes.get("device_class")

            # Make the output more human-readable based on device class
            status_text = state
            if device_class:
                if state == "on":
                    on_map = {"door": "open", "window": "open", "motion": "detecting motion", "moisture": "wet", "smoke": "detecting smoke", "gas": "detecting gas", "carbon_monoxide": "detecting carbon monoxide", "opening": "open", "garage_door": "open", "safety": "unsafe", "lock": "unlocked"}
                    status_text = on_map.get(device_class, "on")
                elif state == "off":
                    off_map = {"door": "closed", "window": "closed", "motion": "clear", "moisture": "dry", "smoke": "clear", "gas": "clear", "carbon_monoxide": "clear", "opening": "closed", "garage_door": "closed", "safety": "safe", "lock": "locked"}
                    status_text = off_map.get(device_class, "off")

            return f"The {friendly_name} is currently {status_text}."
        else:
            return f"Error: Could not retrieve binary sensor status for '{device_name}'."

    def get_sensor_status(self, device_name: str) -> str:
        """
        Gets the current value of a generic sensor (e.g., temperature, humidity, pressure).

        :param device_name: The friendly, human-readable name of the sensor.
        :return: A formatted string describing the sensor's current value and unit.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("sensor."):
            return f"Error: The device '{device_name}' is not a generic sensor. Use get_binary_sensor_status for on/off sensors."

        data = self._get_entity_state(entity_id)
        if data:
            state = data.get("state", "unknown")
            attributes = data.get("attributes", {})
            friendly_name = attributes.get("friendly_name", device_name)
            unit = attributes.get("unit_of_measurement", "")

            if unit:
                return f"The {friendly_name} is currently {state} {unit}."
            else:
                return f"The {friendly_name} is currently {state}."
        else:
            return f"Error: Could not retrieve sensor status for '{device_name}'."

    def get_internet_connection_status(self) -> str:
        """
        Gets the status of the internet connection by looking for Speedtest.net sensors.

        :return: A formatted string with the ping, download, and upload speeds, or a message if the integration is not found.
        """
        all_entities = self._get_all_entities()
        internet_stats = {}

        for entity in all_entities:
            entity_id = entity.get("entity_id", "")
            if "speedtest" in entity_id:
                state = entity.get("state", "unknown")
                unit = entity.get("attributes", {}).get("unit_of_measurement", "")
                
                if "ping" in entity_id:
                    internet_stats["Ping"] = f"{state} {unit}"
                elif "download" in entity_id:
                    internet_stats["Download"] = f"{state} {unit}"
                elif "upload" in entity_id:
                    internet_stats["Upload"] = f"{state} {unit}"

        if not internet_stats:
            return "Could not find any Speedtest.net sensors. Please ensure the Speedtest.net integration is configured in Home Assistant to use this feature."

        output_lines = ["Internet Connection Status:"]
        if "Ping" in internet_stats:
            output_lines.append(f"- Ping: {internet_stats['Ping']}")
        if "Download" in internet_stats:
            output_lines.append(f"- Download Speed: {internet_stats['Download']}")
        if "Upload" in internet_stats:
            output_lines.append(f"- Upload Speed: {internet_stats['Upload']}")
            
        return "\n".join(output_lines)

    def get_vacuum_status(self, device_name: str) -> str:
        """
        Gets the detailed status of a robot vacuum cleaner.

        :param device_name: The friendly, human-readable name of the vacuum.
        :return: A formatted string describing the vacuum's current status, battery, and fan speed.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("vacuum."):
            return f"Error: The device '{device_name}' is not a vacuum."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            state = data.get("state", "unknown").replace('_', ' ').capitalize()
            friendly_name = attributes.get("friendly_name", device_name)

            output_lines = [f"Status for {friendly_name}: {state}"]

            if (battery_level := attributes.get("battery_level")) is not None:
                output_lines.append(f"- Battery: {battery_level}%")
            if (fan_speed := attributes.get("fan_speed")) is not None:
                output_lines.append(f"- Fan Speed: {fan_speed.capitalize()}")

            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve vacuum status for '{device_name}'."

    def get_alarm_status(self, device_name: str) -> str:
        """
        Gets the current status of an alarm control panel.

        :param device_name: The friendly, human-readable name of the alarm system.
        :return: A formatted string describing the alarm's current state.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("alarm_control_panel."):
            return f"Error: The device '{device_name}' is not an alarm control panel."

        data = self._get_entity_state(entity_id)
        if data:
            state = data.get("state", "unknown").replace('_', ' ').capitalize()
            friendly_name = data.get("attributes", {}).get("friendly_name", device_name)
            return f"The {friendly_name} is currently {state}."
        else:
            return f"Error: Could not retrieve alarm status for '{device_name}'."

    def control_alarm(self, device_name: str, state: str) -> str:
        """
        Arms or disarms an alarm control panel.

        :param device_name: The friendly, human-readable name of the alarm system.
        :param state: The desired state: "arm_home", "arm_away", "arm_night", "disarm".
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("alarm_control_panel."):
            return f"Error: The device '{device_name}' is not an alarm control panel."

        state = state.lower()
        valid_states = ["arm_home", "arm_away", "arm_night", "disarm"]
        if state not in valid_states:
            return f"Error: Invalid state '{state}'. Must be one of: {', '.join(valid_states)}."

        payload = {"entity_id": entity_id}
        if alarm_code := self.valves.get("HA_ALARM_CODE"):
            payload["code"] = alarm_code

        error = self._call_service("alarm_control_panel", state, payload, device_name)
        if error:
            return error
        return f"Successfully processed action '{state.replace('_', ' ')}' for {device_name}."

    def get_nas_status(self, device_name: str) -> str:
        """
        Gets the status of a Network Attached Storage (NAS) device by looking for its sensors.
        This is primarily designed for the Synology DSM integration.

        :param device_name: The friendly, human-readable name of the NAS (e.g., "Synology" or "MyNAS").
        :return: A formatted string with key metrics like volume usage, CPU load, and memory usage.
        """
        all_entities = self._get_all_entities()
        nas_stats = {}

        # Find all sensors related to the NAS device name
        relevant_sensors = [
            e for e in all_entities
            if e.get("entity_id", "").startswith("sensor.") and device_name.lower() in e.get("attributes", {}).get("friendly_name", "").lower()
        ]

        if not relevant_sensors:
            return f"Could not find any sensors related to '{device_name}'. Please ensure the Synology DSM or a similar integration is configured."

        # Extract key metrics by looking for keywords in the friendly names
        for sensor in relevant_sensors:
            friendly_name = sensor.get("attributes", {}).get("friendly_name", "").lower()
            state = sensor.get("state", "unknown")
            unit = sensor.get("attributes", {}).get("unit_of_measurement", "")
            value = f"{state} {unit}".strip()

            if "volume_used" in friendly_name:
                nas_stats["Volume Usage"] = value
            elif "cpu_load" in friendly_name and "total" in friendly_name:
                nas_stats["CPU Load"] = value
            elif "memory_usage" in friendly_name:
                nas_stats["Memory Usage"] = value
            elif "status" in friendly_name and "volume" not in friendly_name:
                nas_stats["Security Status"] = state.capitalize()
            elif "temperature" in friendly_name:
                nas_stats["Temperature"] = value

        output_lines = [f"Status for {device_name}:"]
        for key, val in nas_stats.items():
            output_lines.append(f"- {key}: {val}")

        return "\n".join(output_lines)

    def get_todo_list_items(self, list_name: str) -> str:
        """
        Gets all items from a specified to-do list.

        :param list_name: The friendly, human-readable name of the to-do list (e.g., "Shopping List").
        :return: A formatted string listing all items and their status (complete/incomplete).
        """
        entity_id = self._resolve_entity_id(list_name)
        if not entity_id:
            return f"Error: Could not find a to-do list named '{list_name}'."

        if not entity_id.startswith("todo."):
            return f"Error: The entity '{list_name}' is not a to-do list."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            items = attributes.get("items")

            if items is None:
                return f"The to-do list '{list_name}' does not appear to have any items."

            if not items:
                return f"The to-do list '{list_name}' is empty."

            output_lines = [f"Items on the '{list_name}' list:"]
            for item in items:
                summary = item.get("summary", "No summary")
                status = item.get("status", "needs_action")
                prefix = "[x]" if status == "completed" else "[ ]"
                output_lines.append(f"- {prefix} {summary}")

            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve to-do list items for '{list_name}'."

    def add_todo_list_item(self, list_name: str, item: str) -> str:
        """
        Adds a new item to a to-do list.

        :param list_name: The friendly, human-readable name of the to-do list.
        :param item: The summary of the item to add.
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(list_name)
        if not entity_id:
            return f"Error: Could not find a to-do list named '{list_name}'."

        if not entity_id.startswith("todo."):
            return f"Error: The entity '{list_name}' is not a to-do list."

        if not item or not isinstance(item, str):
            return "Error: A valid item description must be provided."

        payload = {"entity_id": entity_id, "item": item}
        error = self._call_service("todo", "add_item", payload, list_name)
        if error:
            return error
        return f"Successfully added '{item}' to the '{list_name}' list."

    def update_todo_list_item(self, list_name: str, item: str, status: str) -> str:
        """
        Updates an item on a to-do list, for example, to mark it as complete.

        :param list_name: The friendly, human-readable name of the to-do list.
        :param item: The exact summary of the item to update.
        :param status: The new status for the item. Must be "complete" or "incomplete".
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(list_name)
        if not entity_id:
            return f"Error: Could not find a to-do list named '{list_name}'."

        if not entity_id.startswith("todo."):
            return f"Error: The entity '{list_name}' is not a to-do list."

        status = status.lower()
        status_map = {"complete": "completed", "incomplete": "needs_action"}
        ha_status = status_map.get(status)

        if not ha_status:
            return f"Error: Invalid status '{status}'. Must be 'complete' or 'incomplete'."

        payload = {"entity_id": entity_id, "item": item, "status": ha_status}
        error = self._call_service("todo", "update_item", payload, list_name)
        if error:
            return error
        return f"Successfully marked '{item}' as {status} on the '{list_name}' list."

    def control_vacuum(
        self,
        device_name: str,
        action: str,
        fan_speed: Optional[str] = None,
    ) -> str:
        """
        Controls a robot vacuum cleaner (start, stop, pause, return to base, set fan speed).

        :param device_name: The friendly, human-readable name of the vacuum.
        :param action: The action to perform: "start", "stop", "pause", "return_to_base", "locate", "set_fan_speed".
        :param fan_speed: The fan speed to set (e.g., "low", "medium", "high", "turbo"), only used when action is "set_fan_speed".
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("vacuum."):
            return f"Error: The device '{device_name}' is not a vacuum."

        action = action.lower()
        service = None
        payload = {"entity_id": entity_id}

        simple_service_map = {"start": "start", "stop": "stop", "pause": "pause", "return_to_base": "return_to_base", "locate": "locate"}

        if action in simple_service_map:
            service = simple_service_map[action]
        elif action == "set_fan_speed":
            if not fan_speed:
                return "Error: To set fan speed, please provide a fan speed level (e.g., 'medium')."
            service = "set_fan_speed"
            payload["fan_speed"] = fan_speed
        else:
            return f"Error: Invalid action '{action}'. Valid actions are: start, stop, pause, return_to_base, locate, set_fan_speed."

        error = self._call_service("vacuum", service, payload, device_name)
        if error:
            return error
        return f"Successfully performed action '{action}' on {device_name}."

    def control_lock(self, device_name: str, state: str) -> str:
        """
        Locks, unlocks, or opens a lock.

        :param device_name: The friendly, human-readable name of the lock.
        :param state: The desired state. Must be "lock", "unlock", or "open".
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("lock."):
            return f"Error: The device '{device_name}' is not a lock."

        state = state.lower()
        service_map = {"lock": "lock", "unlock": "unlock", "open": "open"}
        service = service_map.get(state)

        if not service:
            return f"Error: Invalid state '{state}'. Must be 'lock', 'unlock', or 'open'."

        payload = {"entity_id": entity_id}
        error = self._call_service("lock", service, payload, device_name)
        if error:
            return error
        return f"Successfully processed action '{state}' for {device_name}."

    def get_media_player_status(self, device_name: str) -> str:
        """
        Gets the detailed status of a media player, including what is currently playing.

        :param device_name: The friendly, human-readable name of the media player.
        :return: A formatted string describing the media player's current state and what's playing.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("media_player."):
            return f"Error: The device '{device_name}' is not a media player."

        data = self._get_entity_state(entity_id)
        if data:
            attributes = data.get("attributes", {})
            state = data.get("state", "unknown").capitalize()
            output_lines = [f"Status for {device_name}: {state}"]

            if app_name := attributes.get("app_name"):
                output_lines.append(f"- App: {app_name}")
            if media_title := attributes.get("media_title"):
                if media_artist := attributes.get("media_artist"):
                    output_lines.append(f"- Playing: {media_title} by {media_artist}")
                else:
                    output_lines.append(f"- Playing: {media_title}")
            if (volume := attributes.get("volume_level")) is not None:
                volume_str = f"{int(volume * 100)}%"
                if attributes.get("is_volume_muted", False):
                    volume_str += " (Muted)"
                output_lines.append(f"- Volume: {volume_str}")
            return "\n".join(output_lines)
        else:
            return f"Error: Could not retrieve media player status for '{device_name}'."

    def set_media_player_source(self, device_name: str, source_name: str) -> str:
        """
        Changes the input source for a media player (e.g., a TV or smart speaker).

        :param device_name: The friendly, human-readable name of the media player.
        :param source_name: The name of the source to switch to (e.g., "HDMI 1", "Netflix").
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("media_player."):
            return f"Error: The device '{device_name}' is not a media player."

        if not source_name or not isinstance(source_name, str):
            return "Error: A valid source name must be provided."

        payload = {"entity_id": entity_id, "source": source_name}
        error = self._call_service("media_player", "select_source", payload, device_name)
        if error:
            return error
        return f"Successfully changed the source for {device_name} to {source_name}."

    def control_media_playback(
        self,
        device_name: str,
        action: str,
        volume_percent: Optional[int] = None,
    ) -> str:
        """
        Controls media playback for a media player (play, pause, stop, volume).

        :param device_name: The friendly, human-readable name of the media player.
        :param action: The action to perform: "play", "pause", "stop", "volume_up", "volume_down", "mute", "unmute", "set_volume".
        :param volume_percent: The volume level to set (0-100), only used when action is "set_volume".
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("media_player."):
            return f"Error: The device '{device_name}' is not a media player."

        action = action.lower()
        service = None
        payload = {"entity_id": entity_id}

        simple_service_map = {"play": "media_play", "pause": "media_pause", "stop": "media_stop", "volume_up": "volume_up", "volume_down": "volume_down"}

        if action in simple_service_map:
            service = simple_service_map[action]
        elif action == "set_volume":
            if volume_percent is None or not (0 <= volume_percent <= 100):
                return "Error: To set volume, please provide a volume percentage between 0 and 100."
            service = "volume_set"
            payload["volume_level"] = volume_percent / 100.0
        elif action in ["mute", "unmute"]:
            service = "volume_mute"
            payload["is_volume_muted"] = action == "mute"
        else:
            return f"Error: Invalid action '{action}'. Valid actions are: play, pause, stop, volume_up, volume_down, mute, unmute, set_volume."

        error = self._call_service("media_player", service, payload, device_name)
        if error:
            return error
        return f"Successfully performed action '{action}' on {device_name}."

    def control_cover(self, device_name: str, state: str) -> str:
        """
        Controls covers like blinds, curtains, or garage doors.

        :param device_name: The friendly, human-readable name of the cover to control.
        :param state: The desired state. Can be "open", "close", "stop", or a position percentage (e.g., "50").
        :return: A user-facing confirmation of the action or a descriptive error message.
        """
        entity_id = self._resolve_entity_id(device_name)
        if not entity_id:
            return f"Error: Could not find a device named '{device_name}'."

        if not entity_id.startswith("cover."):
            return f"Error: The device '{device_name}' is not a cover."

        # Check if state is a position percentage
        try:
            position = int(state)
            if not (0 <= position <= 100):
                return "Error: Cover position must be a percentage between 0 and 100."

            payload = {"entity_id": entity_id, "position": position}
            error = self._call_service("cover", "set_cover_position", payload, device_name)
            if error:
                return error
            return f"Successfully processed action for {device_name}: set position to {position}%."
        except ValueError:
            # State is not a number, treat as a string command
            state = state.lower()
            service_map = {"open": "open_cover", "close": "close_cover", "stop": "stop_cover"}
            service = service_map.get(state)
            if not service:
                return f"Error: Invalid state '{state}'. Must be 'open', 'close', 'stop', or a position percentage."
            payload = {"entity_id": entity_id}
            error = self._call_service("cover", service, payload, device_name)
            if error:
                return error
            return f"Successfully processed action for {device_name}: {state}."

    def send_to_printer(self, text_to_print: str) -> str:
        """
        Sends text content to a configured printer in Home Assistant via a notify service.
        The LLM should pass the relevant chat history as the 'text_to_print' argument.

        :param text_to_print: The text content to be printed.
        :return: A user-facing confirmation or an error message.
        """
        printer_service = self.valves.get("HA_PRINTER_NOTIFY_SERVICE")
        if not printer_service:
            return "Error: The printer notify service has not been configured in the tool settings. Please set it up first."

        if not isinstance(text_to_print, str) or not text_to_print:
            return "Error: No text was provided to print."

        payload = {"message": text_to_print}
        error = self._call_service("notify", printer_service, payload, f"printer ({printer_service})")
        if error:
            return error
        return f"Successfully sent the text to the printer service '{printer_service}'."

    def get_error_logs(self, limit: int = 5) -> str:
        """
        Retrieves the most recent error logs from Home Assistant.

        :param limit: The maximum number of log entries to retrieve. Defaults to 5.
        :return: A formatted string of the recent error logs, or a message if none are found.
        """
        if not (1 <= limit <= 20):
            return "Error: Limit must be between 1 and 20."

        endpoint = f"{self.ha_url}/api/error/all"
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            logs = response.json()

            if not logs:
                return "No error logs found in Home Assistant."

            output_lines = ["Recent Home Assistant Error Logs:"]
            # Logs are newest first, so we take the first `limit` items.
            for log_entry in logs[:limit]:
                timestamp = log_entry.get("timestamp_pretty", "No timestamp")
                message = log_entry.get("message", "No message")
                output_lines.append(f"- [{timestamp}] {message}")

            return "\n".join(output_lines)
        except requests.exceptions.HTTPError as e:
            return f"An HTTP error occurred while fetching error logs: {e}. Response: {e.response.text}"
        except requests.exceptions.RequestException as e:
            return f"A network error occurred while fetching error logs: {e}"

    def get_persistent_notifications(self) -> str:
        """
        Retrieves all active persistent notifications from Home Assistant.

        :return: A formatted string listing all active notifications, or a message if none are found.
        """
        all_entities = self._get_all_entities()
        notifications = []
        for entity in all_entities:
            if entity.get("entity_id", "").startswith("persistent_notification."):
                title = entity.get("attributes", {}).get("friendly_name", "Notification")
                message = entity.get("state")
                notifications.append(f"{title}: {message}")

        if not notifications:
            return "There are no active notifications in Home Assistant."

        notification_list_str = "\n- ".join(notifications)
        return f"The following notifications are active:\n- {notification_list_str}"

class App:
    """
    This is the main application class for the OpenWebUI tool, compliant with the 0.5 standard.
    It is responsible for initializing the tool and handling its lifecycle.
    It acts as an entry point for the OpenWebUI, which will instantiate it and manage its lifecycle.
    """
    def __init__(self, valves: Any):
        self.valves = valves
        self.tools = Tools(valves)

    def __call__(self, *args, **kwargs):
        return self.tools