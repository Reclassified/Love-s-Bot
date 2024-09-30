import discord
from discord.ext import commands
import requests
import urllib3
import os
from dotenv import load_dotenv  # Import dotenv

# Load environment variables from .env file
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Debugging line to check if the token is loaded correctly
print("Discord Token:", os.getenv('DISCORD_TOKEN'))

intents = discord.Intents.all()
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)

def get_lovense_toy_info():
    try:
        response = requests.get("https://api.lovense.com/api/lan/getToys", verify=False)
        print(f"Fetching toys... Status Code: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching toys: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception while fetching toys: {e}")
        return None

def parse_toy_info(toy_info):
    if toy_info:
        toy_ids = []
        domain = None
        https_port = None
        for domain_key, domain_info in toy_info.items():
            domain = domain_info.get("domain")
            https_port = domain_info.get("httpsPort")
            for toy_id, toy_details in domain_info["toys"].items():
                toy_ids.append(toy_id)
        return toy_ids, domain, https_port
    return [], None, None

def send_lovense_command(domain, https_port, action, intensity=0, time_sec=0):
    params = {
        "command": "Function",
        "action": f"{action}:{intensity}",
        "timeSec": time_sec,
        "loopRunningSec": 1,
        "loopPauseSec": 1,
        "apiVer": 1,
        "stopPrevious": 1
    }
    url = f"https://{domain}:{https_port}/command"
    print(f"Sending command to {url}: {params}")
    response = requests.post(url, json=params, verify=False)
    if response.status_code == 200:
        print(f"Command sent: {response.json()}")
    else:
        print(f"Error sending command: {response.status_code} - {response.text}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        await client.change_presence(activity=discord.Game(" with your lovense"))
        toy_info = get_lovense_toy_info()
        toy_ids, domain, https_port = parse_toy_info(toy_info)

        # Create a message with toy types and IDs
        message = "Connected! Found Lovense toys: "
        if toy_info:
            toy_details_list = []  # List to hold toy types and IDs
            for domain_key, domain_info in toy_info.items():
                for toy_id, toy_details in domain_info["toys"].items():
                    toy_type = toy_details.get("toyType", "Unknown")
                    toy_details_list.append(f"{toy_type} ({toy_id})")  # Format: ToyType (ToyID)
            message += ", ".join(toy_details_list)  # Join with commas
        else:
            message += "No Lovense toys found."

        user = await client.fetch_user(os.getenv('UserID'))
        await user.send(message)
    except Exception as e:
        print(f"Error checking Lovense toys: {e}")

@client.tree.command(name="vibrate", description="Vibrate the Lovense toy")
async def vibrate(interaction: discord.Interaction, intensity: int, time_sec: int):
    action = "Vibrate"
    if time_sec <= 1:
        await interaction.response.send_message("Error: Running time must be greater than 1.")
        return
    toy_info = get_lovense_toy_info()
    toy_ids, domain, https_port = parse_toy_info(toy_info)
    if domain and https_port:
        send_lovense_command(domain, https_port, action, intensity, time_sec)
        await interaction.response.send_message(f"Vibration command sent at intensity {intensity} for {time_sec} seconds.")
    else:
        await interaction.response.send_message("Error: No Lovense toys found.")

@client.tree.command(name="rotate", description="Rotate the Lovense toy")
async def rotate(interaction: discord.Interaction, intensity: int, time_sec: int):
    action = "Rotate"
    if time_sec <= 1:
        await interaction.response.send_message("Error: Running time must be greater than 1.")
        return
    toy_info = get_lovense_toy_info()
    toy_ids, domain, https_port = parse_toy_info(toy_info)
    if domain and https_port:
        send_lovense_command(domain, https_port, action, intensity, time_sec)
        await interaction.response.send_message(f"Rotation command sent at intensity {intensity} for {time_sec} seconds.")
    else:
        await interaction.response.send_message("Error: No Lovense toys found.")

@client.tree.command(name="stop", description="Stop the Lovense toy")
async def stop(interaction: discord.Interaction):
    action = "Stop"
    toy_info = get_lovense_toy_info()
    toy_ids, domain, https_port = parse_toy_info(toy_info)
    if domain and https_port:
        send_lovense_command(domain, https_port, action, 0, 0)
        await interaction.response.send_message("Stop command sent.")
    else:
        await interaction.response.send_message("Error: No Lovense toys found.")

client.run(os.getenv('DISCORD_TOKEN'))