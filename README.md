# Discord Buttplug Bot

A Discord bot that allows users to control their toys through Discord commands, with support for multiple devices, command queuing, and automatic connection management.

## Features

### Device Management
- Automatic device discovery and connection
- Support for multiple device types (Vibrators, Rotators, Linear actuators)
- Real-time connection monitoring and auto-reconnection
- Device status tracking and reporting

### Command System
- Command queuing to prevent overrides
- Support for multiple users
- Queue status monitoring
- Command duration enforcement

### Basic Commands
- `/vibrate` - Control vibration intensity and duration
- `/rotate` - Control rotation speed and duration
- `/linear` - Control linear actuator position and duration
- `/stop` - Stop current command and clear queue

### Device Management Commands
- `/list_devices` - Show all connected devices and their capabilities
- `/rescan` - Manually scan for and reconnect toys
- `/connection_status` - Check connection status of bot and toys
- `/queue_status` - Check command queue status for a device
- `/clear_queue` - Clear the command queue for a device

### AI Control Commands
- `/ai_control` - Start AI-controlled patterns
- `/stop_ai` - Stop current AI pattern
- `/list_patterns` - Show available AI patterns

## Prerequisites

- Python 3.7 or higher
- Windows 10 or higher (for Intiface Central compatibility)
- Discord Bot Token
- Intiface Central running locally
- Buttplug-compatible toys

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Reclassified/Love-s-Bot.git
cd Love-s-Bot
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
DISCORD_TOKEN=your_discord_bot_token
UserID=your_discord_user_id
```

4. Start Intiface Central and ensure it's running on the default WebSocket URL (ws://127.0.0.1:12345)

## Usage

### Basic Commands
```
/vibrate device_id intensity time_sec
Example: /vibrate 0 50 30  # Vibrate device 0 at 50% intensity for 30 seconds

/rotate device_id intensity time_sec
Example: /rotate 0 50 30  # Rotate device 0 at 50% speed for 30 seconds

/linear device_id position time_sec
Example: /linear 0 50 30  # Move linear actuator to 50% position over 30 seconds
```

### Device Management
```
/list_devices  # Show all connected devices
/rescan  # Manually scan for toys
/connection_status  # Check connection status
/queue_status device_id  # Check queue status
/clear_queue device_id  # Clear command queue
```

### AI Control
```
/ai_control device_id pattern duration
Example: /ai_control 0 wave 30  # Run wave pattern on device 0 for 30 seconds

Available patterns:
- wave: Gradually increases and decreases intensity
- pulse: Alternates between high and low intensity
- escalate: Gradually increases intensity
- random: Generates random intensity patterns
```

## Command Queue System

The bot implements a command queue system to prevent command overrides and ensure proper execution:

1. Each device has its own command queue
2. Commands are processed in order (FIFO)
3. Each command runs for its full duration
4. Next command starts only after current command completes
5. Stop commands bypass the queue for immediate response

### Queue Status
- Use `/queue_status` to check:
  - Current device status (Idle/Busy)
  - Number of commands in queue
  - Position of your command in queue

### Queue Management
- `/stop` - Stops current command and clears queue
- `/clear_queue` - Clears all pending commands

## Connection Management

The bot includes automatic connection management:

1. Monitors connections to:
   - Discord
   - Intiface Central
   - Individual devices

2. Automatic reconnection for:
   - Lost Discord connection
   - Lost Intiface Central connection
   - Disconnected devices

3. Connection status monitoring:
   - Real-time status updates
   - Automatic reconnection attempts
   - Detailed error logging

## Safety Features

- Intensity limits (0-100%)
- Time limits (1-3600 seconds)
- Command validation
- Automatic device stopping
- Queue management for safe operation

## Troubleshooting

1. **Device Not Found**
   - Ensure Intiface Central is running
   - Use `/rescan` to manually scan for devices
   - Check device is in pairing mode

2. **Connection Issues**
   - Check Intiface Central is running
   - Verify WebSocket URL (ws://127.0.0.1:12345)
   - Use `/connection_status` to check status

3. **Command Not Working**
   - Check device is connected
   - Verify command parameters
   - Check queue status with `/queue_status`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot is intended for adult use only. Users are responsible for using this bot safely and responsibly. 
