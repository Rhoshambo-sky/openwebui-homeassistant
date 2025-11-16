# Home Assistant Control Tool for OpenWebUI

This tool connects OpenWebUI to a Home Assistant instance, allowing a Large Language Model (LLM) to control and query smart home devices using natural, human-readable language.

**Author:** Rhoshambo
**Version:** 0.2.1

## What's New in 0.2.1

- **OpenWebUI 0.5 Compliance**: Full compliance with OpenWebUI 0.5 standards
- **Pydantic Valves**: Proper configuration management using Pydantic BaseModel
- **Event Emitter Support**: Real-time progress updates during operations
- **Enhanced Validation**: Improved URL and API key validation with security warnings
- **Better Logging**: More granular debug logging for troubleshooting
- **Type Safety**: Improved type hints throughout the codebase

## Features

- **To-do List Management:** View, add, and complete items on your to-do lists.
- **NAS Monitoring:** Get the status of network storage devices like a Synology NAS.
- **Alarm System Control:** Arm and disarm alarm systems, using a code if required.
- **Alarm System Status:** Get the current status of alarm control panels.
- **Vacuum Control:** Start, stop, pause, and send robot vacuums back to their base.
- **Vacuum Status:** Get the detailed status of robot vacuums, including battery and fan speed.
- **Internet Speed Test:** Get the latest internet connection speeds from the Speedtest.net integration.
- **Generic Sensor Status:** Get the value of sensors like temperature, humidity, and pressure.
- **Binary Sensor Status:** Get the status of sensors like doors, windows, and motion detectors.
- **Lock Control:** Lock, unlock, and open doors.
- **Lock Status:** Get the current status of locks.
- **Person & Device Tracking:** Get the location status of people and device trackers.
- **System Monitoring:** View recent error logs and active system notifications.
- **Detailed Media Player Status:** Get the currently playing media, active app, and volume level.
- **Media Playback Control:** Play, pause, stop, and control the volume of media players.
- **Media Player Control:** Change input sources for TVs and speakers.
- **Cover Control:** Open, close, stop, and set the position of blinds, curtains, and garage doors.
- **Send to Printer:** Send the chat history or other text to a Home Assistant-connected printer.
- **Natural Language Control:** Control devices using their friendly names (e.g., "turn on the kitchen lights").
- **Thermostat Control:** Set the temperature and HVAC mode for climate devices.
- **Device Status Queries:** Ask for the current state of any device (e.g., "is the front door locked?").
- **Detailed Thermostat Status:** Get the current temperature, target temperature, and action of a thermostat.
- **Weather Forecasts:** Get a multi-day forecast from your weather integration.
- **Advanced Light Control:** A single function to control a light's state (on/off), brightness, color, and color temperature simultaneously.
- **Media Source Discovery:** List available input sources for media players like TVs and speakers.
- **Entity Discovery:** List all available devices of a certain type, like lights, scenes, and automations.
- **Automation and Scene Control:** Enable, disable, trigger automations, and activate scenes.
- **Performance & Stability:** Caches device lists for speed and verifies the connection on startup to "fail fast".
- **Robust Error Handling:** Provides clear feedback on connection issues, invalid API keys, or unknown devices.

## Installation

1.  Place the `home_assistant_tool.py` and `requirements.txt` files into your OpenWebUI `tools` directory.
2.  The OpenWebUI backend will automatically install the necessary dependencies from `requirements.txt`.

## Configuration

This tool requires a **Long-Lived Access Token** from your Home Assistant instance. You can create one in your Home Assistant profile under `Security > Long-Lived Access Tokens`.

There are two ways to configure the tool:

### 1. OpenWebUI Settings (Recommended)

After the tool is loaded, you can configure it directly in the OpenWebUI interface:
1.  Go to `Settings > Tools`.
2.  Find the "Home Assistant Controls" tool.
3.  Enter your **Home Assistant URL** (e.g., `http://192.168.1.100:8123`) and your **Home Assistant API Key** (the Long-Lived Access Token).
4.  To enable printing, enter the name of your printer's notify service in the **Home Assistant Printer Notify Service** field (e.g., `my_cups_printer`).
5.  To enable alarm control, enter your **Home Assistant Alarm Code** if your system requires one.

> **Note on Printer Setup:** To use the printing feature, you must first have a printer integration configured in Home Assistant that creates a `notify` service. A common example is the CUPS (Common UNIX Printing System) integration.

### 2. Environment Variables

Alternatively, you can configure the tool by setting environment variables on the server where OpenWebUI is running. This is useful for containerized setups like Docker.

```bash
export HA_URL="http://your-home-assistant-ip:8123"
export HA_API_KEY="your-long-lived-access-token"
export HA_ALARM_CODE="your-alarm-code"
export HA_PRINTER_NOTIFY_SERVICE="my_cups_printer"
```

## Usage Examples

Once configured, you can interact with your Home Assistant devices in your chat with the LLM:

- `"Turn on the living room lamp."`
- `"Please turn off the bedroom fan."`
- `"Is the coffee machine on?"`
- `"Open the garage door."`
- `"What is the status of the garage door?"`
- `"Change the TV source to HDMI 2."`
- `"What's playing on the living room speaker?"`
- `"Show me the latest error logs."`
- `"Unlock the back door."`
- `"Is the front door locked?"`
- `"Is the back door window open?"`
- `"What is the humidity in the basement?"`
- `"What's my internet speed?"`
- `"What is the status of the robot vacuum?"`
- `"What's the status of the Synology NAS?"`
- `"Add 'Buy milk' to the shopping list."`
- `"What's on my to-do list?"`
- `"What is the status of the alarm?"`
- `"Tell the robot vacuum to start cleaning."`
- `"Where is Jane?"`
- `"Are there any notifications?"`
- `"Pause the living room speaker and set the volume to 30%."`
- `"Set the office lamp to 50% brightness and make it a warm white."`
- `"Activate the 'Movie Time' scene."`
- `"Set the thermostat to 72 degrees and put it in heat mode."`
- `"Trigger the 'Good Morning' automation."`
- `"What's the status of the thermostat?"`
- `"What's the weather forecast?"`
- `"What scenes are available?"`
- `"What are the available sources for the Living Room TV?"`
- `"List all of the lights."`
- `"Disable the 'Turn on porch light at sunset' automation."`
- `"Hey, shut off all the lights in the kitchen."` (Note: This requires a "Kitchen Lights" group or device in Home Assistant).

## Architectural Limitations

This tool interacts with Home Assistant via its official REST API, which is designed for controlling and querying the state of existing devices and entities. It is intentionally sandboxed from making deep configuration changes for security and stability reasons.

Therefore, this tool **cannot** perform tasks such as:

- **Creating or Deleting Areas:** Managing areas must be done in the Home Assistant UI.
- **Adding or Removing Device Integrations:** Setting up new hardware or cloud integrations is a UI-driven process.
- **Creating Complex New Automations:** While the tool can enable, disable, and trigger existing automations, creating new automations with multiple triggers and conditions from scratch should be done in the Automation Editor in Home Assistant.

For these types of setup and configuration tasks, you should always use the Home Assistant user interface.