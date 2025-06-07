import discord
from discord.ext import commands
import requests
import urllib3
import os
import logging
import time
import random
import asyncio
import json
from dotenv import load_dotenv
from typing import Optional, Tuple, List, Dict
from buttplug import Client, WebsocketConnector, ProtocolSpec

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('buttplug_bot.log'),
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
BUTTPLUG_WS_URL = "ws://127.0.0.1:12345"  # Default Intiface Central WebSocket URL

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

class ButtplugDevice:
    def __init__(self, device_id: str, device_name: str, device_type: str, client: Client):
        self.device_id = device_id
        self.device_name = device_name
        self.device_type = device_type
        self.client = client
        self.device = None
        self.current_task = None

    async def connect(self):
        """Connect to the device through Buttplug."""
        try:
            # Find the device in the client's device list
            for device in self.client.devices.values():
                if device.name == self.device_name:
                    self.device = device
                    logger.info(f"Connected to device: {self.device_name}")
                    return True
            logger.error(f"Device {self.device_name} not found in client devices")
            return False
        except Exception as e:
            logger.error(f"Error connecting to device {self.device_name}: {e}")
            return False

    async def send_command(self, action: str, intensity: float = 0.0, time_sec: int = 0):
        """Send command to the device through Buttplug."""
        if not self.device:
            logger.error(f"Device {self.device_name} is not connected")
            return False

        try:
            # Cancel any existing command
            if self.current_task and not self.current_task.done():
                self.current_task.cancel()
                try:
                    await self.current_task
                except asyncio.CancelledError:
                    pass

            # Convert intensity to 0-1 range
            normalized_intensity = intensity / 100.0

            if action == "Vibrate":
                # Use scalar actuators for vibration
                if len(self.device.actuators) > 0:
                    await self.device.actuators[0].command(normalized_intensity)
                else:
                    logger.error(f"No actuators found on device {self.device_name}")
                    return False
            elif action == "Rotate":
                # Use rotatory actuators for rotation
                if len(self.device.rotatory_actuators) > 0:
                    await self.device.rotatory_actuators[0].command(normalized_intensity, True)
                else:
                    logger.error(f"No rotatory actuators found on device {self.device_name}")
                    return False
            elif action == "Linear":
                # Use linear actuators for linear movement
                if len(self.device.linear_actuators) > 0:
                    await self.device.linear_actuators[0].command(time_sec * 1000, normalized_intensity)
                else:
                    logger.error(f"No linear actuators found on device {self.device_name}")
                    return False
            elif action == "Stop":
                # Stop all actuators
                if len(self.device.actuators) > 0:
                    await self.device.actuators[0].command(0.0)
                if len(self.device.rotatory_actuators) > 0:
                    await self.device.rotatory_actuators[0].command(0.0, True)
                if len(self.device.linear_actuators) > 0:
                    await self.device.linear_actuators[0].command(0, 0.0)
                return True
            else:
                logger.error(f"Unknown action: {action}")
                return False

            logger.info(f"Command sent successfully to {self.device_name}")

            # If a duration is specified, create a task to stop the device after that duration
            if time_sec > 0 and action != "Linear":  # Linear commands handle duration internally
                async def stop_after_duration():
                    try:
                        await asyncio.sleep(time_sec)
                        # Stop all actuators
                        if len(self.device.actuators) > 0:
                            await self.device.actuators[0].command(0.0)
                        if len(self.device.rotatory_actuators) > 0:
                            await self.device.rotatory_actuators[0].command(0.0, True)
                        if len(self.device.linear_actuators) > 0:
                            await self.device.linear_actuators[0].command(0, 0.0)
                        logger.info(f"Stopped device {self.device_name} after {time_sec} seconds")
                    except asyncio.CancelledError:
                        logger.info(f"Duration task cancelled for device {self.device_name}")
                    except Exception as e:
                        logger.error(f"Error in duration task for device {self.device_name}: {e}")

                self.current_task = asyncio.create_task(stop_after_duration())

            return True
        except Exception as e:
            logger.error(f"Error sending command to {self.device_name}: {e}")
            return False

    async def stop(self):
        """Stop the device and cancel any pending duration tasks."""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        await self.send_command("Stop", 0, 0)

class CommandQueue:
    def __init__(self):
        self.queues = {}  # device_id -> asyncio.Queue
        self.running = {}  # device_id -> bool
        self.locks = {}    # device_id -> asyncio.Lock

    def get_queue(self, device_id: str) -> asyncio.Queue:
        """Get or create a queue for a device."""
        if device_id not in self.queues:
            self.queues[device_id] = asyncio.Queue()
            self.running[device_id] = False
            self.locks[device_id] = asyncio.Lock()
        return self.queues[device_id]

    async def add_command(self, device_id: str, command: dict) -> bool:
        """Add a command to the device's queue."""
        queue = self.get_queue(device_id)
        await queue.put(command)
        return True

    async def process_queue(self, device_id: str, device: ButtplugDevice):
        """Process commands in the device's queue."""
        queue = self.get_queue(device_id)
        
        while True:
            try:
                # Get the next command
                command = await queue.get()
                
                async with self.locks[device_id]:
                    self.running[device_id] = True
                    try:
                        # Execute the command
                        success = await device.send_command(
                            command['action'],
                            command['intensity'],
                            command['time_sec']
                        )
                        
                        # Notify the user of the result
                        if command.get('interaction'):
                            if success:
                                await command['interaction'].followup.send(
                                    f"✅ Command executed: {command['action']} at {command['intensity']}% for {command['time_sec']}s"
                                )
                            else:
                                await command['interaction'].followup.send(
                                    f"❌ Failed to execute command: {command['action']}"
                                )

                        # Wait for the command duration before processing next command
                        if success and command['time_sec'] > 0 and command['action'] != 'Stop':
                            await asyncio.sleep(command['time_sec'])
                            # Ensure device is stopped after duration
                            await device.send_command('Stop', 0, 0)
                            
                    finally:
                        self.running[device_id] = False
                        queue.task_done()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing command for device {device_id}: {e}")
                if command.get('interaction'):
                    await command['interaction'].followup.send(f"❌ Error executing command: {str(e)}")

    def is_device_busy(self, device_id: str) -> bool:
        """Check if a device is currently processing commands."""
        return self.running.get(device_id, False)

    def get_queue_size(self, device_id: str) -> int:
        """Get the number of commands waiting in the queue."""
        return self.queues.get(device_id, asyncio.Queue()).qsize()

    async def clear_queue(self, device_id: str):
        """Clear all pending commands for a device."""
        queue = self.get_queue(device_id)
        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                break

# Create global command queue
command_queue = CommandQueue()

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, ButtplugDevice] = {}
        self.client = None
        self.is_connected = False
        self.connection_check_task = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        self.queue_tasks = {}  # device_id -> task

    async def connect_to_server(self):
        """Connect to Buttplug server."""
        try:
            connector = WebsocketConnector(BUTTPLUG_WS_URL, logger=logger)
            self.client = Client("Discord Bot", ProtocolSpec.v3)
            await self.client.connect(connector)
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info("Connected to Buttplug server")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Buttplug server: {e}")
            self.is_connected = False
            return False

    async def check_connection(self):
        """Check connection status and attempt reconnection if needed."""
        while True:
            try:
                if not self.is_connected or not self.client:
                    logger.warning("Connection lost to Buttplug server. Attempting to reconnect...")
                    if await self.connect_to_server():
                        await self.update_devices()
                        logger.info("Successfully reconnected to Buttplug server")
                    else:
                        self.reconnect_attempts += 1
                        if self.reconnect_attempts >= self.max_reconnect_attempts:
                            logger.error("Max reconnection attempts reached. Please check your connection and restart the bot.")
                            break
                        logger.warning(f"Reconnection attempt {self.reconnect_attempts} failed. Retrying in {self.reconnect_delay} seconds...")
                        await asyncio.sleep(self.reconnect_delay)
                else:
                    # Check if devices are still connected
                    for device_id, device in list(self.devices.items()):
                        if not device.device or device.device not in self.client.devices.values():
                            logger.warning(f"Device {device_id} disconnected. Attempting to reconnect...")
                            if not await device.connect():
                                logger.error(f"Failed to reconnect device {device_id}")
                                del self.devices[device_id]
                            else:
                                logger.info(f"Successfully reconnected device {device_id}")

                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in connection check: {e}")
                await asyncio.sleep(5)

    async def start_connection_monitoring(self):
        """Start the connection monitoring task."""
        if not self.connection_check_task:
            self.connection_check_task = asyncio.create_task(self.check_connection())
            logger.info("Started connection monitoring")

    async def stop_connection_monitoring(self):
        """Stop the connection monitoring task."""
        if self.connection_check_task:
            self.connection_check_task.cancel()
            try:
                await self.connection_check_task
            except asyncio.CancelledError:
                pass
            self.connection_check_task = None
            logger.info("Stopped connection monitoring")

    async def start_queue_processing(self, device_id: str, device: ButtplugDevice):
        """Start processing commands for a device."""
        if device_id not in self.queue_tasks:
            self.queue_tasks[device_id] = asyncio.create_task(
                command_queue.process_queue(device_id, device)
            )

    async def stop_queue_processing(self, device_id: str):
        """Stop processing commands for a device."""
        if device_id in self.queue_tasks:
            self.queue_tasks[device_id].cancel()
            try:
                await self.queue_tasks[device_id]
            except asyncio.CancelledError:
                pass
            del self.queue_tasks[device_id]

    async def update_devices(self):
        """Update the list of available devices."""
        if not self.client:
            return

        try:
            # Start scanning for devices
            await self.client.start_scanning()
            await asyncio.sleep(10)  # Wait longer for devices to be discovered
            await self.client.stop_scanning()

            # Update device list
            for device in self.client.devices.values():
                device_id = str(device.index)
                if device_id not in self.devices:
                    # Get device type based on available actuators
                    device_type = "Unknown"
                    if len(device.actuators) > 0:
                        device_type = "Vibrator"
                    if len(device.rotatory_actuators) > 0:
                        device_type = "Rotator"
                    if len(device.linear_actuators) > 0:
                        device_type = "Linear"

                    self.devices[device_id] = ButtplugDevice(
                        device_id=device_id,
                        device_name=device.name,
                        device_type=device_type,
                        client=self.client
                    )
                    await self.devices[device_id].connect()
                    # Start queue processing for the new device
                    await self.start_queue_processing(device_id, self.devices[device_id])
                    logger.info(f"Added new device: {device.name} ({device_id}) of type {device_type}")
        except Exception as e:
            logger.error(f"Error updating devices: {e}")

    def get_device(self, device_id: str) -> Optional[ButtplugDevice]:
        """Get a specific device by ID."""
        return self.devices.get(device_id)

    def get_all_devices(self) -> List[ButtplugDevice]:
        """Get all available devices."""
        return list(self.devices.values())

    def get_devices_by_type(self, device_type: str) -> List[ButtplugDevice]:
        """Get all devices of a specific type."""
        return [device for device in self.devices.values() 
                if device.device_type.lower() == device_type.lower()]

# Global device manager instance
device_manager = DeviceManager()

@client.tree.command(name="sync", description="Sync bot commands with Discord (Admin only)")
async def sync(interaction: discord.Interaction):
    """Sync bot commands with Discord."""
    # Check if user is the bot owner
    if str(interaction.user.id) != os.getenv('UserID'):
        await interaction.response.send_message("❌ This command is only available to the bot owner.", ephemeral=True)
        return

    try:
        await interaction.response.send_message("🔄 Syncing commands...", ephemeral=True)
        await client.tree.sync()
        await interaction.followup.send("✅ Commands synced successfully!", ephemeral=True)
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
        await interaction.followup.send(f"❌ Error syncing commands: {str(e)}", ephemeral=True)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        # Sync commands with Discord
        print("Syncing commands with Discord...")
        await client.tree.sync()
        print("Commands synced with Discord!")
        
        await client.change_presence(activity=discord.Game(" with your toys"))
        
        # Connect to Buttplug server and start monitoring
        if await device_manager.connect_to_server():
            await device_manager.update_devices()
            await device_manager.start_connection_monitoring()
            
            # Create a message with device types and IDs
            message = "Connected! Found devices: "
            if device_manager.devices:
                device_details_list = []
                for device in device_manager.get_all_devices():
                    device_details_list.append(f"{device.device_name} ({device.device_id})")
                message += ", ".join(device_details_list)
            else:
                message += "No devices found."

            user = await client.fetch_user(os.getenv('UserID'))
            await user.send(message)
    except Exception as e:
        print(f"Error checking devices: {e}")

@client.event
async def on_disconnect():
    """Handle Discord disconnection."""
    logger.warning("Discord connection lost. Attempting to reconnect...")
    await device_manager.stop_connection_monitoring()

@client.event
async def on_resumed():
    """Handle Discord reconnection."""
    logger.info("Discord connection resumed")
    await device_manager.start_connection_monitoring()

@client.tree.command(name="help", description="Show all available commands and their usage")
async def help_command(interaction: discord.Interaction):
    """Show all available commands and their usage."""
    commands_info = {
        "Admin Commands": {
            "sync": "Sync bot commands with Discord (Admin only)\nUsage: `/sync`",
        },
        "Device Management": {
            "list_devices": "List all connected devices and their capabilities\nUsage: `/list_devices`",
            "rescan": "Manually scan for and reconnect toys\nUsage: `/rescan`",
            "connection_status": "Check connection status of bot and toys\nUsage: `/connection_status`",
        },
        "Basic Commands": {
            "vibrate": "Vibrate the device\nUsage: `/vibrate device_id intensity time_sec`\nExample: `/vibrate 0 50 30`",
            "rotate": "Rotate the device\nUsage: `/rotate device_id intensity time_sec`\nExample: `/rotate 0 50 30`",
            "linear": "Control linear actuator\nUsage: `/linear device_id position time_sec`\nExample: `/linear 0 50 30`",
            "stop": "Stop the device\nUsage: `/stop device_id`"
        },
        "AI Control Commands": {
            "ai_control": "Start AI-controlled pattern\nUsage: `/ai_control device_id pattern duration`\nPatterns: wave, pulse, escalate, random\nExample: `/ai_control 0 wave 30`",
            "stop_ai": "Stop the current AI pattern\nUsage: `/stop_ai device_id`"
        }
    }

    embed = discord.Embed(
        title="Buttplug Bot Commands",
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

@client.tree.command(name="vibrate", description="Vibrate a device")
async def vibrate(interaction: discord.Interaction, device_id: str, intensity: int, time_sec: int):
    """Vibrate a specific device."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    # Check if device is busy
    if command_queue.is_device_busy(device_id):
        queue_size = command_queue.get_queue_size(device_id)
        await interaction.response.send_message(
            f"⏳ Device is busy. Your command has been queued. Position in queue: {queue_size + 1}"
        )
    else:
        await interaction.response.send_message("⏳ Processing your command...")

    # Add command to queue
    await command_queue.add_command(device_id, {
        'action': 'Vibrate',
        'intensity': intensity,
        'time_sec': time_sec,
        'interaction': interaction
    })

@client.tree.command(name="rotate", description="Rotate the device")
async def rotate(interaction: discord.Interaction, device_id: str, intensity: int, time_sec: int):
    """Rotate command with input validation."""
    if not validate_intensity(intensity):
        await interaction.response.send_message(f"Error: Intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    # Check if device is busy
    if command_queue.is_device_busy(device_id):
        queue_size = command_queue.get_queue_size(device_id)
        await interaction.response.send_message(
            f"⏳ Device is busy. Your command has been queued. Position in queue: {queue_size + 1}"
        )
    else:
        await interaction.response.send_message("⏳ Processing your command...")

    # Add command to queue
    await command_queue.add_command(device_id, {
        'action': 'Rotate',
        'intensity': intensity,
        'time_sec': time_sec,
        'interaction': interaction
    })

@client.tree.command(name="stop", description="Stop the device and clear its command queue")
async def stop(interaction: discord.Interaction, device_id: str):
    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    # Stop current command and clear queue
    await device.send_command("Stop", 0, 0)
    await command_queue.clear_queue(device_id)
    
    await interaction.response.send_message(f"✅ Device stopped and command queue cleared.")

class AIController:
    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
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

                success = await self.send_command(intensity, step_duration)
                
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
            # Ensure device is stopped
            await self.send_command(0, 0)

        return True

    async def send_command(self, intensity: float, time_sec: int):
        """Send command to the device through Buttplug."""
        device = device_manager.get_device(self.device_id)
        if not device:
            logger.error(f"Device with ID {self.device_id} not found")
            return False

        try:
            success = await device.send_command("Vibrate", intensity, time_sec)
            if success:
                logger.info(f"Command sent successfully to device {self.device_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending command to device {self.device_id}: {e}")
            return False

    def stop(self):
        """Stop the current pattern."""
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
        device_manager.get_device(self.device_id).send_command("Stop", 0, 0)

# Global AI controller instance
ai_controller = None

@client.tree.command(name="ai_control", description="Start AI-controlled pattern")
async def ai_control(interaction: discord.Interaction, device_id: str, pattern: str, duration: int = 30):
    """Start AI-controlled pattern for the device."""
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

    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    # Initialize AI controller if not exists
    if not ai_controller:
        ai_controller = AIController(device_id, device.device_type)
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
async def stop_ai(interaction: discord.Interaction, device_id: str):
    """Stop the current AI-controlled pattern."""
    global ai_controller
    
    if not ai_controller or not ai_controller.is_running:
        await interaction.response.send_message("Error: No AI control is currently running.")
        return

    ai_controller.stop()
    await interaction.response.send_message("AI control stopped.")

@client.tree.command(name="linear", description="Control linear actuator")
async def linear(interaction: discord.Interaction, device_id: str, position: int, time_sec: int):
    """Control linear actuator with position and duration."""
    if not validate_intensity(position):
        await interaction.response.send_message(f"Error: Position must be between {MIN_INTENSITY} and {MAX_INTENSITY}.")
        return
        
    if not validate_time(time_sec):
        await interaction.response.send_message(f"Error: Time must be between {MIN_TIME_SEC} and {MAX_TIME_SEC} seconds.")
        return

    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    success = await device.send_command("Linear", position, time_sec)
    if success:
        await interaction.response.send_message(f"Linear command sent to device {device_id} at position {position} for {time_sec} seconds.")
    else:
        await interaction.response.send_message(f"Error: Failed to send linear command to device {device_id}.")

@client.tree.command(name="list_devices", description="List all connected devices and their capabilities")
async def list_devices(interaction: discord.Interaction):
    """List all connected devices with their IDs and capabilities."""
    if not device_manager.devices:
        await interaction.response.send_message("No devices found. Make sure your devices are connected and Intiface Central is running.")
        return

    embed = discord.Embed(
        title="Connected Devices",
        description="Here are all connected devices and their capabilities:",
        color=discord.Color.blue()
    )

    for device in device_manager.get_all_devices():
        # Get device capabilities
        capabilities = []
        if device.device.actuators:
            capabilities.append("Vibration")
        if device.device.rotatory_actuators:
            capabilities.append("Rotation")
        if device.device.linear_actuators:
            capabilities.append("Linear Movement")

        device_info = f"**ID:** {device.device_id}\n"
        device_info += f"**Type:** {device.device_type}\n"
        device_info += f"**Capabilities:** {', '.join(capabilities) if capabilities else 'None'}\n"
        device_info += f"**Name:** {device.device_name}"

        embed.add_field(
            name=f"Device {device.device_id}",
            value=device_info,
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Add a new command to check connection status
@client.tree.command(name="connection_status", description="Check the connection status of the bot and devices")
async def connection_status(interaction: discord.Interaction):
    """Check and display the connection status of the bot and devices."""
    embed = discord.Embed(
        title="Connection Status",
        color=discord.Color.blue()
    )

    # Check Discord connection
    discord_status = "🟢 Connected" if client.is_ws_ratelimited() else "🔴 Disconnected"
    embed.add_field(name="Discord Connection", value=discord_status, inline=False)

    # Check Buttplug server connection
    buttplug_status = "🟢 Connected" if device_manager.is_connected else "🔴 Disconnected"
    embed.add_field(name="Buttplug Server", value=buttplug_status, inline=False)

    # Check device connections
    if device_manager.devices:
        device_statuses = []
        for device in device_manager.get_all_devices():
            status = "🟢 Connected" if device.device and device.device in device_manager.client.devices.values() else "🔴 Disconnected"
            device_statuses.append(f"{device.device_name} ({device.device_id}): {status}")
        embed.add_field(name="Devices", value="\n".join(device_statuses), inline=False)
    else:
        embed.add_field(name="Devices", value="No devices connected", inline=False)

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="rescan", description="Manually scan for and reconnect toys")
async def rescan(interaction: discord.Interaction):
    """Manually scan for and reconnect toys."""
    await interaction.response.send_message("🔄 Scanning for toys...")
    
    try:
        # Start scanning for devices
        await device_manager.client.start_scanning()
        await asyncio.sleep(10)  # Wait for devices to be discovered
        await device_manager.client.stop_scanning()
        
        # Update device list
        old_devices = set(device_manager.devices.keys())
        await device_manager.update_devices()
        new_devices = set(device_manager.devices.keys())
        
        # Create status message
        embed = discord.Embed(
            title="Toy Scan Results",
            color=discord.Color.blue()
        )
        
        # Check for new devices
        added_devices = new_devices - old_devices
        if added_devices:
            device_list = []
            for device_id in added_devices:
                device = device_manager.get_device(device_id)
                device_list.append(f"🟢 {device.device_name} (ID: {device_id})")
            embed.add_field(
                name="New Toys Found",
                value="\n".join(device_list),
                inline=False
            )
        
        # Check for lost devices
        lost_devices = old_devices - new_devices
        if lost_devices:
            device_list = []
            for device_id in lost_devices:
                device_list.append(f"🔴 Device {device_id}")
            embed.add_field(
                name="Lost Toys",
                value="\n".join(device_list),
                inline=False
            )
        
        # Show current devices
        if device_manager.devices:
            device_list = []
            for device in device_manager.get_all_devices():
                status = "🟢 Connected" if device.device and device.device in device_manager.client.devices.values() else "🔴 Disconnected"
                device_list.append(f"{status} {device.device_name} (ID: {device.device_id})")
            embed.add_field(
                name="Current Toys",
                value="\n".join(device_list),
                inline=False
            )
        else:
            embed.add_field(
                name="Current Toys",
                value="No toys connected",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error during rescan: {e}")
        await interaction.followup.send(f"❌ Error scanning for toys: {str(e)}")

# Add a command to check queue status
@client.tree.command(name="queue_status", description="Check the command queue status for a device")
async def queue_status(interaction: discord.Interaction, device_id: str):
    """Check the command queue status for a device."""
    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    embed = discord.Embed(
        title=f"Queue Status for Device {device_id}",
        color=discord.Color.blue()
    )

    is_busy = command_queue.is_device_busy(device_id)
    queue_size = command_queue.get_queue_size(device_id)

    status = "🟢 Idle" if not is_busy else "🟡 Busy"
    embed.add_field(name="Status", value=status, inline=False)
    embed.add_field(name="Commands in Queue", value=str(queue_size), inline=False)

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="clear_queue", description="Clear the command queue for a device")
async def clear_queue(interaction: discord.Interaction, device_id: str):
    """Clear the command queue for a device."""
    device = device_manager.get_device(device_id)
    if not device:
        await interaction.response.send_message(f"Error: Device with ID {device_id} not found.")
        return

    # Stop current command
    await device.send_command("Stop", 0, 0)
    
    # Clear the queue
    await command_queue.clear_queue(device_id)
    
    await interaction.response.send_message(f"✅ Command queue cleared for device {device_id}")

client.run(os.getenv('DISCORD_TOKEN'))
