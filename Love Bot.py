import discord
from discord.ext import commands
import requests
import urllib3
import os
import logging
import time
import random
import asyncio
from dotenv import load_dotenv
from typing import Optional, Tuple, List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lovense_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
MAX_INTENSITY = 100
MIN_INTENSITY = 0
MAX_TIME_SEC = 3600  # 1 hour
MIN_TIME_SEC = 1

# AI Control Constants
PATTERN_TYPES = {
    "wave": [(20, 2), (40, 2), (60, 2), (80, 2), (100, 2), (80, 2), (60, 2), (40, 2), (20, 2)],
    "pulse": [(100, 1), (0, 1), (100, 1), (0, 1), (100, 1), (0, 1)],
    "escalate": [(20, 3), (40, 3), (60, 3), (80, 3), (100, 3)],
    "random": None  # Will be generated dynamically
}

intents = discord.Intents.all()
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)

def validate_intensity(intensity: int) -> bool:
    """Validate the intensity parameter."""
    return MIN_INTENSITY <= intensity <= MAX_INTENSITY

def validate_time(time_sec: int) -> bool:
    """Validate the time parameter."""
    return MIN_TIME_SEC <= time_sec <= MAX_TIME_SEC

def get_lovense_toy_info() -> Optional[dict]:
    """Get information about connected Lovense toys with retry mechanism."""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get("https://api.lovense.com/api/lan/getToys", verify=False)
            logger.info(f"Fetching toys... Status Code: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error fetching toys: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while fetching toys: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching toys: {e}")
            return None

def parse_toy_info(toy_info: Optional[dict]) -> Tuple[List[str], Optional[str], Optional[int]]:
    """Parse toy information and return toy IDs, domain, and port."""
    if not toy_info:
        return [], None, None
        
    try:
        toy_ids = []
        domain = None
        https_port = None
        
        for domain_key, domain_info in toy_info.items():
            domain = domain_info.get("domain")
            https_port = domain_info.get("httpsPort")
            for toy_id, toy_details in domain_info["toys"].items():
                toy_ids.append(toy_id)
                logger.info(f"Found toy: {toy_details.get('toyType', 'Unknown')} ({toy_id})")
                
        return toy_ids, domain, https_port
    except Exception as e:
        logger.error(f"Error parsing toy info: {e}")
        return [], None, None

def send_lovense_command(domain: str, https_port: int, action: str, intensity: int = 0, time_sec: int = 0) -> bool:
    """Send command to Lovense toy with error handling."""
    try:
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
        logger.info(f"Sending command to {url}: {params}")
        
        response = requests.post(url, json=params, verify=False)
        if response.status_code == 200:
            logger.info(f"Command sent successfully: {response.json()}")
            return True
        else:
            logger.error(f"Error sending command: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return False

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        # Sync commands with Discord
        await client.tree.sync()
        print("Commands synced with Discord!")
        
        await client.change_presence(activity=discord.Game(" with your lovense"))
        toy_info = get_lovense_toy_info()
        toy_manager.update_toys(toy_info)

        # Create a message with toy types and IDs
        message = "Connected! Found Lovense toys: "
        if toy_manager.toys:
            toy_details_list = []
            for toy in toy_manager.get_all_toys():
                toy_details_list.append(f"{toy.toy_type} ({toy.toy_id})")
            message += ", ".join(toy_details_list)
        else:
            message += "No Lovense toys found."

        user = await client.fetch_user(os.getenv('UserID'))
        await user.send(message)
    except Exception as e:
        print(f"Error checking Lovense toys: {e}")

@client.tree.command(name="help", description="Show all available commands and their usage")
async def help_command(interaction: discord.Interaction):
    """Show all available commands and their usage."""
    commands_info = {
        "Basic Commands": {
            "vibrate": "Vibrate the Lovense toy\nUsage: `/vibrate intensity time_sec`\nExample: `/vibrate 50 30`",
            "rotate": "Rotate the Lovense toy\nUsage: `/rotate intensity time_sec`\nExample: `/rotate 50 30`",
            "stop": "Stop the Lovense toy\nUsage: `/stop`"
        },
        "AI Control Commands": {
            "ai_control": "Start AI-controlled pattern\nUsage: `/ai_control pattern duration`\nPatterns: wave, pulse, escalate, random\nExample: `/ai_control wave 30`",
            "stop_ai": "Stop the current AI pattern\nUsage: `/stop_ai`"
        }
    }

    embed = discord.Embed(
        title="Lovense Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )

    for category, cmds in commands_info.items():
        cmd_list = "\n\n".join([f"**{cmd}**\n{desc}" for cmd, desc in cmds.items()])
        embed.add_field(name=category, value=cmd_list, inline=False)

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="list_patterns", description="List all available AI patterns")
async def list_patterns(interaction: discord.Interaction):
    """List all available AI patterns and their descriptions."""
    patterns_info = {
        "wave": "Gradually increases and decreases intensity in a wave pattern",
        "pulse": "Alternates between high and low intensity in quick pulses",
        "escalate": "Gradually increases intensity from low to high",
        "random": "Generates random intensity patterns for variety"
    }

    embed = discord.Embed(
        title="Available AI Patterns",
        description="Here are all available patterns for AI control:",
        color=discord.Color.green()
    )

    for pattern, description in patterns_info.items():
        embed.add_field(
            name=pattern.capitalize(),
            value=description,
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="vibrate", description="Vibrate the Lovense toy")
async def vibrate(interaction: discord.Interaction, toy_id: str, intensity: int, time_sec: int):
    """Vibrate a specific Lovense toy."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    toy = toy_manager.get_toy(toy_id)
    if not toy:
        await interaction.response.send_message(f"Error: Toy with ID {toy_id} not found.")
        return

    success = toy.send_command("Vibrate", intensity, time_sec)
    if success:
        await interaction.response.send_message(f"Vibration command sent to toy {toy_id} at intensity {intensity} for {time_sec} seconds.")
    else:
        await interaction.response.send_message(f"Error: Failed to send vibration command to toy {toy_id}.")

@client.tree.command(name="rotate", description="Rotate the Lovense toy")
async def rotate(interaction: discord.Interaction, intensity: int, time_sec: int):
    """Rotate command with input validation."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return
        
    action = "Rotate"
    toy_info = get_lovense_toy_info()
    toy_ids, domain, https_port = parse_toy_info(toy_info)
    
    if domain and https_port:
        success = send_lovense_command(domain, https_port, action, intensity, time_sec)
        if success:
            await interaction.response.send_message(f"Rotation command sent at intensity {intensity} for {time_sec} seconds.")
        else:
            await interaction.response.send_message("Error: Failed to send rotation command.")
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

class AIController:
    def __init__(self, domain: str, https_port: int):
        self.domain = domain
        self.https_port = https_port
        self.is_running = False
        self.current_pattern = None
        self.current_task = None

    def generate_random_pattern(self, duration: int = 30) -> List[Tuple[int, int]]:
        """Generate a random pattern of intensities and durations."""
        pattern = []
        remaining_time = duration
        while remaining_time > 0:
            intensity = random.randint(20, 100)
            step_duration = random.randint(1, min(5, remaining_time))
            pattern.append((intensity, step_duration))
            remaining_time -= step_duration
        return pattern

    async def run_pattern(self, pattern_name: str, duration: int = 30):
        """Run a specific pattern for the given duration."""
        if pattern_name == "random":
            pattern = self.generate_random_pattern(duration)
        else:
            pattern = PATTERN_TYPES.get(pattern_name)
            if not pattern:
                return False

        self.is_running = True
        total_time = 0

        try:
            for intensity, step_duration in pattern:
                if not self.is_running:
                    break
                
                if total_time >= duration:
                    break

                success = send_lovense_command(
                    self.domain,
                    self.https_port,
                    "Vibrate",
                    intensity,
                    step_duration
                )
                
                if not success:
                    logger.error(f"Failed to execute pattern step: {intensity} for {step_duration}s")
                    break

                await asyncio.sleep(step_duration)
                total_time += step_duration

        except Exception as e:
            logger.error(f"Error running pattern: {e}")
            return False
        finally:
            self.is_running = False
            # Ensure toy is stopped
            send_lovense_command(self.domain, self.https_port, "Stop", 0, 0)

        return True

    def stop(self):
        """Stop the current pattern."""
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
        send_lovense_command(self.domain, self.https_port, "Stop", 0, 0)

# Global AI controller instance
ai_controller = None

@client.tree.command(name="ai_control", description="Start AI-controlled pattern")
async def ai_control(interaction: discord.Interaction, pattern: str, duration: int = 30):
    """Start AI-controlled pattern for the Lovense toy."""
    global ai_controller
    
    if pattern not in PATTERN_TYPES:
        await interaction.response.send_message(
            f"Error: Invalid pattern. Available patterns: {', '.join(PATTERN_TYPES.keys())}"
        )
        return

    if not validate_time(duration):
        await interaction.response.send_message(
            f"Error: Duration must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds."
        )
        return

    toy_info = get_lovense_toy_info()
    toy_ids, domain, https_port = parse_toy_info(toy_info)

    if not domain or not https_port:
        await interaction.response.send_message("Error: No Lovense toys found.")
        return

    # Initialize AI controller if not exists
    if not ai_controller:
        ai_controller = AIController(domain, https_port)
    elif ai_controller.is_running:
        await interaction.response.send_message("Error: AI control is already running.")
        return

    await interaction.response.send_message(f"Starting AI control with {pattern} pattern for {duration} seconds...")
    
    # Run the pattern
    success = await ai_controller.run_pattern(pattern, duration)
    
    if success:
        await interaction.followup.send("AI control completed successfully.")
    else:
        await interaction.followup.send("Error: AI control failed.")

@client.tree.command(name="stop_ai", description="Stop AI-controlled pattern")
async def stop_ai(interaction: discord.Interaction):
    """Stop the current AI-controlled pattern."""
    global ai_controller
    
    if not ai_controller or not ai_controller.is_running:
        await interaction.response.send_message("Error: No AI control is currently running.")
        return

    ai_controller.stop()
    await interaction.response.send_message("AI control stopped.")

class ToyController:
    def __init__(self, toy_id: str, toy_type: str, domain: str, https_port: int):
        self.toy_id = toy_id
        self.toy_type = toy_type
        self.domain = domain
        self.https_port = https_port
        self.is_running = False

    def send_command(self, action: str, intensity: int = 0, time_sec: int = 0) -> bool:
        """Send command to specific toy."""
        try:
            params = {
                "command": "Function",
                "action": f"{action}:{intensity}",
                "timeSec": time_sec,
                "loopRunningSec": 1,
                "loopPauseSec": 1,
                "apiVer": 1,
                "stopPrevious": 1,
                "toyId": self.toy_id
            }
            url = f"https://{self.domain}:{self.https_port}/command"
            logger.info(f"Sending command to toy {self.toy_id}: {params}")
            
            response = requests.post(url, json=params, verify=False)
            if response.status_code == 200:
                logger.info(f"Command sent successfully to toy {self.toy_id}: {response.json()}")
                return True
            else:
                logger.error(f"Error sending command to toy {self.toy_id}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending command to toy {self.toy_id}: {e}")
            return False

class ToyManager:
    def __init__(self):
        self.toys: Dict[str, ToyController] = {}
        self.ai_controllers: Dict[str, AIController] = {}

    def update_toys(self, toy_info: dict) -> None:
        """Update the list of available toys."""
        if not toy_info:
            return

        for domain_key, domain_info in toy_info.items():
            domain = domain_info.get("domain")
            https_port = domain_info.get("httpsPort")
            
            for toy_id, toy_details in domain_info["toys"].items():
                toy_type = toy_details.get("toyType", "Unknown")
                if toy_id not in self.toys:
                    self.toys[toy_id] = ToyController(toy_id, toy_type, domain, https_port)
                    logger.info(f"Added new toy: {toy_type} ({toy_id})")

    def get_toy(self, toy_id: str) -> Optional[ToyController]:
        """Get a specific toy by ID."""
        return self.toys.get(toy_id)

    def get_all_toys(self) -> List[ToyController]:
        """Get all available toys."""
        return list(self.toys.values())

    def get_toys_by_type(self, toy_type: str) -> List[ToyController]:
        """Get all toys of a specific type."""
        return [toy for toy in self.toys.values() if toy.toy_type.lower() == toy_type.lower()]

# Global toy manager instance
toy_manager = ToyManager()

@client.tree.command(name="list_toys", description="List all connected Lovense toys")
async def list_toys(interaction: discord.Interaction):
    """List all connected Lovense toys."""
    toy_info = get_lovense_toy_info()
    toy_manager.update_toys(toy_info)
    
    if not toy_manager.toys:
        await interaction.response.send_message("No Lovense toys found.")
        return

    embed = discord.Embed(
        title="Connected Lovense Toys",
        description="Here are all connected toys:",
        color=discord.Color.blue()
    )

    # Group toys by type
    toys_by_type = {}
    for toy in toy_manager.get_all_toys():
        if toy.toy_type not in toys_by_type:
            toys_by_type[toy.toy_type] = []
        toys_by_type[toy.toy_type].append(toy.toy_id)

    for toy_type, toy_ids in toys_by_type.items():
        embed.add_field(
            name=toy_type,
            value="\n".join([f"ID: {toy_id}" for toy_id in toy_ids]),
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="vibrate_all", description="Vibrate all Lovense toys")
async def vibrate_all(interaction: discord.Interaction, intensity: int, time_sec: int):
    """Vibrate all connected Lovense toys."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    toy_info = get_lovense_toy_info()
    toy_manager.update_toys(toy_info)
    
    if not toy_manager.toys:
        await interaction.response.send_message("No Lovense toys found.")
        return

    success_count = 0
    for toy in toy_manager.get_all_toys():
        if toy.send_command("Vibrate", intensity, time_sec):
            success_count += 1

    await interaction.response.send_message(f"Vibration command sent to {success_count} out of {len(toy_manager.toys)} toys.")

@client.tree.command(name="vibrate_type", description="Vibrate all toys of a specific type")
async def vibrate_type(interaction: discord.Interaction, toy_type: str, intensity: int, time_sec: int):
    """Vibrate all toys of a specific type."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    toy_info = get_lovense_toy_info()
    toy_manager.update_toys(toy_info)
    
    toys = toy_manager.get_toys_by_type(toy_type)
    if not toys:
        await interaction.response.send_message(f"No toys of type {toy_type} found.")
        return

    success_count = 0
    for toy in toys:
        if toy.send_command("Vibrate", intensity, time_sec):
            success_count += 1

    await interaction.response.send_message(f"Vibration command sent to {success_count} out of {len(toys)} {toy_type} toys.")

client.run(os.getenv('DISCORD_TOKEN'))
