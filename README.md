# Lovense Discord Bot 🤖

A powerful Discord bot that allows you to control Lovense toys through Discord commands. This bot provides both basic control features and advanced AI-controlled patterns for an enhanced experience.

## Features ✨

- **Basic Toy Control**
  - Vibrate toys with customizable intensity and duration
  - Rotate toys with adjustable settings
  - Control individual toys or all toys simultaneously
  - Control toys by type (e.g., all vibrators)

- **AI Control Patterns**
  - Wave: Gradual intensity changes in a wave pattern
  - Pulse: Quick alternating high and low intensity
  - Escalate: Progressive intensity increase
  - Random: Dynamic random patterns

- **Toy Management**
  - List all connected toys
  - Get detailed toy information
  - Support for multiple toy types
  - Real-time toy status updates

## Prerequisites 📋

- Python 3.7 or higher
- Discord Bot Token
- Lovense Connect App running
- Lovense toys connected to your device
- Windows 10 or higher (for Lovense Connect compatibility)

## Installation 🚀

1. Clone the repository:
```bash
git clone https://github.com/Reclassified/Love-s-Bot.git
cd lovense-discord-bot
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

Required packages (requirements.txt):
```
discord.py>=2.0.0
python-dotenv>=0.19.0
requests>=2.26.0
urllib3>=1.26.0
```

3. Create a `.env` file in the project root with the following variables:
```env
DISCORD_TOKEN=your_discord_bot_token
UserID=your_discord_user_id
```

4. Set up Discord Bot:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to the "Bot" section and create a bot
   - Enable "Message Content Intent" under Privileged Gateway Intents
   - Copy the bot token and add it to your `.env` file

5. Set up Lovense Connect:
   - Download and install [Lovense Connect](https://www.lovense.com/download)
   - Launch Lovense Connect
   - Connect your Lovense toys
   - Ensure the toys are discoverable

## Usage 💡

### Basic Commands

- `/vibrate [toy_id] [intensity] [time_sec]` - Vibrate a specific toy
  - Example: `/vibrate 123456 50 30` - Vibrate toy ID 123456 at 50% intensity for 30 seconds
- `/rotate [intensity] [time_sec]` - Rotate the toy
  - Example: `/rotate 75 20` - Rotate at 75% intensity for 20 seconds
- `/stop` - Stop all toy functions
- `/list_toys` - Show all connected toys

### AI Control Commands

- `/ai_control [pattern] [duration]` - Start AI-controlled pattern
  - Patterns: wave, pulse, escalate, random
  - Duration in seconds
  - Example: `/ai_control wave 60` - Run wave pattern for 60 seconds
- `/stop_ai` - Stop current AI pattern
- `/list_patterns` - Show available AI patterns

### Group Control Commands

- `/vibrate_all [intensity] [time_sec]` - Vibrate all connected toys
  - Example: `/vibrate_all 80 45` - Vibrate all toys at 80% for 45 seconds
- `/vibrate_type [toy_type] [intensity] [time_sec]` - Vibrate all toys of a specific type
  - Example: `/vibrate_type vibrator 60 30` - Vibrate all vibrators at 60% for 30 seconds

## Safety and Limits ⚠️

- Intensity range: 0-100
- Time range: 1-3600 seconds (1 hour max)
- All commands require proper Discord permissions
- Bot will automatically stop patterns if they exceed time limits
- Maximum of 10 toys can be controlled simultaneously
- Minimum 1-second delay between commands

## Troubleshooting 🔧

### Common Issues

1. **Bot not responding to commands**
   - Check if the bot is online in Discord
   - Verify the bot has proper permissions in the server
   - Ensure the bot token in `.env` is correct

2. **Toys not connecting**
   - Ensure Lovense Connect is running
   - Check if toys are powered on and in range
   - Verify toys are properly paired with Lovense Connect
   - Restart Lovense Connect if issues persist

3. **Commands not working**
   - Check if the toy ID is correct
   - Verify the intensity and time values are within limits
   - Ensure you have the latest version of the bot

4. **Connection errors**
   - Check your internet connection
   - Verify Lovense Connect is running
   - Restart the bot if connection issues persist

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request. Before contributing:

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer ⚠️

This bot is for educational and personal use only. Please use responsibly and in accordance with Discord's Terms of Service and Lovense's usage guidelines.

## Support 💬

If you need help or have questions:
- Open an issue on GitHub
- Check the [Discord Support Server](https://discord.gg/your-support-server)
- Review the troubleshooting section above 
