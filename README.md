# Lovense Discord Bot

A Discord bot that allows you to control Lovense toys using slash commands.

## Features

- Connect to Lovense toys via LAN
- Control toy actions using slash commands:
  - `/vibrate <intensity> <time_sec>`: Vibrate the toy at a specified intensity for a set duration.
  - `/rotate <intensity> <time_sec>`: Rotate the toy at a specified intensity for a set duration.
  - `/stop`: Stop the toy immediately.

## Requirements

- Python 3.8+
- [discord.py](https://discordpy.readthedocs.io/en/stable/)
- [requests](https://docs.python-requests.org/en/latest/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/lovense-discord-bot.git
   cd lovense-discord-bot

Create a .env file in the root directory with your Discord bot token:

DISCORD_TOKEN=your_discord_token_here

UserID=your_user_id_here

Note:
Ensure that your Lovense toy is connected and accessible via LAN.
You will need https://www.lovense.com/app/remote
Once Toy is connected you must go under the Little icon that looks like the toy u connected click it and Enable Allow Control
This will start https://api.lovense.com/api/lan/getToys
Which is need for the program to grab all the data automatically
To make the discord bot follow this to make the token https://discordpy.readthedocs.io/en/stable/discord.html
You may need to adjust the toy settings or permissions to allow the bot to control it.
