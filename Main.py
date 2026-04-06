'''

Chief-Of-The-Verification-Staff

Bot that creates a built-in embed to verify and update users roles in the Calderian Army Discord Servers

'''

# ------------------------------ IMPORTS ------------------------------

import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import sqlite3
import aiohttp
import random
import string
import re
import asyncio

from Ping import keep_alive
keep_alive()

# ------------------------------ .ENV ------------------------------

print("[SETUP] Loading .env variables...")

# Load Environmental Variables
load_dotenv()

# Get .Env Variables
discord_token = os.getenv('DISCORD_TOKEN')

print(f"[SETUP] Loaded.")

# ------------------------------ LOGGING ------------------------------

handler = logging.FileHandler(filename='discord_bot.log', encoding='utf-8', mode='w')

# ------------------------------ INTENTS ------------------------------

intents = discord.Intents.default()
intents.members = True

# ------------------------------ GLOBALS ------------------------------

http_session = None

# ------------------------------ DATABASE ------------------------------

# Sql file setup
DB_FILE = 'main_storage.db'

# Initialise DB
def init_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        role_id INTEGER,
        group_id INTEGER,
        sub_group_id_one INTEGER, 
        sub_group_id_two INTEGER, 
        sub_group_id_three INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS pending_verifications (
        discord_id INTEGER PRIMARY KEY,
        roblox_id INTEGER,
        code TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS verified (
        discord_id INTEGER PRIMARY KEY,
        roblox_id INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS server_rules_ids (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        message_id INTEGER
    )   
    """)

    conn.commit()
    conn.close()

# Set the Guild config to the DB
def set_guild_config(guild_id, channel_id, role_id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO guild_config VALUES (?, ?, ?, ?, ?, ?, ?)", 
        (guild_id, channel_id, role_id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three)
    )
    conn.commit()
    conn.close()

# Get the guild config form the DB, with the guild id
def get_guild_config(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT channel_id, role_id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three FROM guild_config WHERE guild_id = ?", 
        (guild_id,)
    )
    data = c.fetchone()
    conn.close()
    return data

# Save pending verifications
def save_pending(discord_id, roblox_id, code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO pending_verifications VALUES (?, ?, ?)", 
        (discord_id, roblox_id, code)
    )
    conn.commit()
    conn.close()

# Get pending verification with the discord id
def get_pending(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT roblox_id, code FROM pending_verifications WHERE discord_id = ?", 
        (discord_id,)
    )
    data = c.fetchone()
    conn.close()
    return data

# Remove the pending verification (due to time out)
def delete_pending(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "DELETE FROM pending_verifications WHERE discord_id = ?", 
        (discord_id,)
    )
    conn.commit()
    conn.close()

def save_verify(discord_id, roblox_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO verified VALUES (?, ?)", 
        (discord_id, roblox_id)
    )
    conn.commit()
    conn.close()

def get_roblox_id_db(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT roblox_id FROM verified WHERE discord_id = ?", 
        (discord_id,)
    )
    data = c.fetchone()
    conn.commit()
    conn.close()
    return data

def save_server_rules_ids(guild_id, channel_id, messge_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO server_rules_ids VALUES (?, ?, ?)", 
        (guild_id, channel_id, messge_id)
    )
    conn.commit()
    conn.close()

def get_server_rules_ids(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT channel_id, message_id FROM server_rules_ids WHERE guild_id = ?", 
        (guild_id,)
    )
    data = c.fetchone()
    conn.commit()
    conn.close()
    return data

# ------------------------------ ROBLOX API HANDLING ------------------------------

# Generates a six digit code
def generate_code_six():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Get the roblox id of a user using their username
async def get_roblox_id(username):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames" : [username]}
        ) as response:
            data = await response.json()
            if data["data"]:
                return data["data"][0]["id"]
    return None

# Get the profile description of a user using their roblox id
async def get_profile_description(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as response:
            data = await response.json()
            return data.get("description", "")
        
# Get the group rank of a user using their roblox user id and group id
async def get_group_rank(user_id, group_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles") as response:
            data = await response.json()

            for group in data["data"]:
                if group["group"]["id"] == group_id:
                    return group["role"]["rank"]
    return 0

async def fetch_group_data(group_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://groups.roblox.com/v1/groups/{group_id}") as response:
            data = await response.json()
            return data
            
    return None

# ------------------------------ ROBLOX & DISCORD ROLE SYNC ------------------------------

def remove_leading_bracket(string : str) -> str:
    return re.sub(r'^\[.*?\]\s*','',string)

async def FetchRobloxGroupRole(discord_user_id: int, group_id):
    # Fetches the Roblox group role for the specified group ID and interaction
    roblox_user_id = await get_roblox_id(discord_user_id)

    if not roblox_user_id:
        return None

    # ---------------- FETCH GROUP DATA ----------------
    try:
        membership_url = f"https://groups.roblox.com/v1/users/{roblox_user_id}/groups/roles"

        global http_session
        async with http_session.get(membership_url, timeout=10) as response:

            if response.status == 404:
                return None

            data = await response.json()

        # ---------------- FIND TARGET GROUP ----------------
        for group in data.get("data", []):
            if group.get("group", {}).get("id") == group_id:
                return {
                    "name": group.get("role", {}).get("name", "Unknown"),
                    "id": group.get("role", {}).get("id", 0)
                }

        return None  # not in group

    except Exception as e:
        print(f"[ERROR] fetch_roblox_group_role_by_discord: {e}")
        return None

async def set_prefix_nickname(member, role_name: str):
    try: 
        prefix = role_name.split("]")[0]
        if prefix:
            prefix = f"{prefix}]" 
        else:
            if role_name[:3] == "PRE": # Government rank
                prefix = "[PRESIDENT]"
            else:
                prefix = ""

        try:
            await member.edit(nick=f"{prefix} {member.name}")
        except discord.Forbidden:
            print("Missing permissions or role hierarchy prevents change")
        except discord.HTTPException as e:
            print(f"HTTP error: {e}")
            
    except Exception as e:
        print(f"Error extracting prefix: {e}")
        prefix = ""

async def get_group_name_async(group_id):
    try:
        data = await fetch_group_data(group_id)
    except Exception:
        return None
    
    if data:
        return data.get("name")
    return None

async def get_roblox_multi_group_role(member, interaction, group_id, sub_one, sub_two, sub_three):
    # Defer if needed
    if not interaction.response.is_done():
        await interaction.response.defer()

    try:
        group_role = await FetchRobloxGroupRole(member.id, group_id)
    except Exception as e:
        print(f"Error fetching Roblox group role: {e}")
        await interaction.followup.send("An error occurred while fetching your Roblox group role.")
        return

    # Collect subgroup ids that are non-zero in order of priority
    sub_ids = [sid for sid in (sub_one, sub_two, sub_three) if sid]
    if not sub_ids:
        return group_role

    fetch_tasks = [get_group_name_async(sid) for sid in sub_ids]
    names = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Normalize and compare; only re-resolve role if a match is found
    for sid, name in zip(sub_ids, names):
        if isinstance(name, Exception) or name is None:
            continue
        normalized = remove_leading_bracket(name)
        if normalized == group_role:
            try:
                group_role = await FetchRobloxGroupRole(member.id, sid)
            except Exception as e:
                print(f"Error fetching subgroup role for {sid}: {e}")
                await interaction.followup.send("An error occurred while fetching your subgroup role.")
            break

    return group_role

async def sync_discord_roles(member: discord.Member, interaction: discord.Interaction, group_id : int, sub_one : int, sub_two : int, sub_three : int):
    # Defer if needed
    if not interaction.response.is_done():
        await interaction.response.defer()

    # ---------------- FETCH ROLE ----------------
    
    group_role = await get_roblox_multi_group_role(member=member, interaction=interaction, group_id=group_id, sub_one=sub_one, sub_two=sub_two, sub_three=sub_three)

    # ---------------- HELPERS / CONFIG ----------------
    def normalize(name: str) -> str:
        if name is None:
            return ""
        return name.strip().upper()

    # Category role names in the guild
    CATEGORY_ROLE_NAMES = {
        "ENLISTED": "Enlisted",
        "OFFICER": "Officer",
        "CHIEF_OF_STAFF_BOARD": "👑 Chief of Staff Board",
        "DEVELOPER": "[DEV] Developer",
    }

    # Prefix groups (normalized)
    ENLISTED_PREFIX = ("[OR-",)
    OFFICER_PREFIX = ("[OF-",)
    CSB_PREFIXES = ("[CDS", "[VCD", "[SEA", "[CAS", "[VCA", "[ASM")
    DEV_PREFIX = ("[DEV",)

    # ---------------- WHEN USER HAS A ROBLOX GROUP ROLE ----------------
    if group_role:
        role_name = group_role.get("name", "Unknown")
        clean_name = normalize(role_name)

        # Find the exact discord role that matches the Roblox role name
        role = discord.utils.get(interaction.guild.roles, name=role_name)

        if not role:
            # Try a normalized lookup (in case of spacing/casing differences)
            role = discord.utils.get(
                interaction.guild.roles,
                name=next((r for r in (role_name, clean_name) if r), None)
            )

        if not role:
            await interaction.followup.send(
                f"The Discord role **{role_name}** does not exist. Contact a dev."
            )
            return

        # Determine the new category for this role
        new_category_name = None
        if any(clean_name.startswith(p) for p in ENLISTED_PREFIX):
            new_category_name = CATEGORY_ROLE_NAMES["ENLISTED"]
        elif any(clean_name.startswith(p) for p in OFFICER_PREFIX):
            new_category_name = CATEGORY_ROLE_NAMES["OFFICER"]
        elif any(clean_name.startswith(p) for p in CSB_PREFIXES):
            new_category_name = CATEGORY_ROLE_NAMES["CHIEF_OF_STAFF_BOARD"]
        elif any(clean_name.startswith(p) for p in DEV_PREFIX):
            new_category_name = CATEGORY_ROLE_NAMES["DEVELOPER"]

        # Resolve category role object (may be None if not configured)
        category_role = None
        if new_category_name:
            category_role = discord.utils.get(interaction.guild.roles, name=new_category_name)

        # Build sets of roles to keep and to remove
        default_role = interaction.guild.default_role
        keep_role_names = {default_role.name, "Roblox Verified"}
        # Keep the main rank role and the new category role (if present)
        keep_role_names.add(role.name)
        if category_role:
            keep_role_names.add(category_role.name)

        # Identify current category roles on the member (so we can remove ones that don't match)
        current_category_roles = [
            r for r in member.roles
            if r.name in set(CATEGORY_ROLE_NAMES.values())
        ]

        # Roles to remove:
        # - Any role that is not @everyone, not Roblox Verified, not managed,
        #   not above the bot, and not in keep_role_names.
        to_remove = [
            r for r in member.roles
            if (
                r != default_role
                and r.name not in keep_role_names
                and not r.managed
                and r < interaction.guild.me.top_role
            )
        ]

        # Additionally, remove category roles that conflict with the new category.
        # Example: moving from Officer -> Chief of Staff Board should remove Officer role.
        conflicting_category_roles = [
            r for r in current_category_roles
            if r.name not in keep_role_names  # remove category roles that are not the new one
            and r < interaction.guild.me.top_role
        ]

        # Merge lists and deduplicate
        remove_set = {r for r in to_remove + conflicting_category_roles}

        # Perform removals (if any)
        if remove_set:
            try:
                await member.remove_roles(*remove_set, reason="Syncing Roblox rank")
            except discord.HTTPException as e:
                print(f"Failed to remove roles for {member.id}: {e}")

        # Add the main role if missing
        if role not in member.roles:
            try:
                await member.add_roles(role, reason="Syncing Roblox rank")
            except discord.Forbidden:
                print(f"Permission denied when adding role {role.name} to {member.id}")
            except discord.HTTPException as e:
                print(f"Failed to add role {role.name} to {member.id}: {e}")

        # Ensure category role is correct: remove other category roles (defensive) then add the new one
        # Remove any remaining category roles that are not the desired one
        remaining_conflicting = [
            r for r in member.roles
            if r.name in set(CATEGORY_ROLE_NAMES.values())
            and r.name != (category_role.name if category_role else None)
            and r < interaction.guild.me.top_role
        ]
        if remaining_conflicting:
            try:
                await member.remove_roles(*remaining_conflicting, reason="Syncing category roles")
            except discord.HTTPException as e:
                print(f"Failed to remove conflicting category roles for {member.id}: {e}")

        # Add the category role if applicable and missing
        if category_role and category_role not in member.roles:
            try:
                await member.add_roles(category_role, reason="Syncing category role")
            except discord.Forbidden:
                print(f"Permission denied when adding category role {category_role.name} to {member.id}")
            except discord.HTTPException as e:
                print(f"Failed to add category role {category_role.name} to {member.id}: {e}")

        # Nickname update
        try:
            await set_prefix_nickname(member, role_name)
        except Exception as e:
            print(f"Failed to set nickname for {member.id}: {e}")

        # DM the user (best-effort)
        try:
            await member.send(f"You have been ranked in 'Calderian Army' to the '**{role.name}**' rank.")
        except discord.Forbidden:
            pass

# ------------------------------ BOT ------------------------------

# Bot Class
class C_Bot(commands.Bot):
    async def setup_hook(self):
        global http_session
        if http_session is None:
            http_session = aiohttp.ClientSession()
        
        self.add_view(VerifyView())

    async def on_ready(self):
        await self.tree.sync()
        print(f"[SETUP] Bot Online: {self.user}")
        
# Create Bot
Bot = C_Bot(command_prefix='/', intents=intents)

# ------------------------------ MODAL ------------------------------

# Creates a modal to get a players username and begin the verification process
class UsernameModal(discord.ui.Modal, title="Enter Roblox Username"):
    username = discord.ui.TextInput(label="Roblox Username")

    async def on_submit(self, interaction : discord.Interaction):
        roblox_id = await get_roblox_id(self.username.value)

        if not roblox_id:
            await interaction.response.send_message(
                "Username not found. Try again.", 
                ephemeral=True,
            )
            return
        
        code = generate_code_six()
        save_pending(discord_id=interaction.user.id, roblox_id=roblox_id, code=code)

        await interaction.response.send_message(
            f"Put this code into you Roblox bio:\n\n**{code}**\n\nThen press **Complete Verification**",
            ephemeral=True,
        )

# ------------------------------ VIEW ------------------------------

# Creates the ui for verification and handles the main logic
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_safe(self, interaction: discord.Interaction):
        """Helper to defer if needed to prevent timeout"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

    @discord.ui.button(label="Start Verification", style=discord.ButtonStyle.blurple)
    async def start(self, interaction : discord.Interaction, button : discord.ui.Button):
        
        await self.interaction_safe(interaction)

        # Get the server rules ids -> message id & channel id
        ids = get_server_rules_ids(interaction.guild.id)

        if ids is None:
            await interaction.followup.send("❌ Rules not set up in this server.", ephemeral=True)
            return

        channel_id, message_id = ids

        channel = interaction.guild.get_channel(channel_id)

        if channel is None:
            await interaction.followup.send("❌ Rules channel not found.", ephemeral=True)
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.followup.send("❌ Rules message not found.", ephemeral=True)
            return

        # Check reactions
        has_accepted = False

        for reaction in message.reactions:
            if str(reaction.emoji) == '✅':
                async for user in reaction.users():
                    if user.id == interaction.user.id:
                        has_accepted = True
                        break

        # If user has NOT reacted
        if not has_accepted:
            await interaction.followup.send("You must accept the rules first by reacting with '✅' in the rules channel.",ephemeral=True)
            return

        await interaction.response.send_modal(UsernameModal())

    @discord.ui.button(label="Complete Verification", style=discord.ButtonStyle.green)
    async def complete(self, interaction : discord.Interaction, button : discord.ui.Button):
        
        await self.interaction_safe(interaction)

        data = get_pending(interaction.user.id)

        if not data:
            await interaction.followup.send(
                "❌ Start Verification first.", 
                ephemeral=True,
            )
            return
        
        roblox_id, code = data
        description = await get_profile_description(roblox_id)

        if code not in description:
            await interaction.followup.send(
                "❌ Code not in bio.",
                ephemeral=True,
            )
            return
        
        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.followup.send(
                "❌ Server not configured.", 
                ephemeral=True,
            )
            return
        
        # Discord and Roblox role handling
        channel_id, role_id, group_id, sub_one, sub_two, sub_three = config
        

        rank = await get_group_rank(roblox_id, group_id)
        if rank <= 0:
            await interaction.followup.send(
                "❌ Not in Roblox group.", 
                ephemeral=True,
            )
            return
        
        try:

            await sync_discord_roles(interaction.user, interaction, int(group_id), int(sub_one), int(sub_two), int(sub_three))

        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while updating your roles: {e}"
            )
        
        role = interaction.guild.get_role(role_id)

        await interaction.user.add_roles(role) # Adds the verified role
        delete_pending(interaction.user.id)

        await interaction.followup.send(
            "✅ Verified!", 
            ephemeral=True,
        )
    
    @discord.ui.button(label="Update", style=discord.ButtonStyle.green)
    async def update(self, interaction : discord.Interaction, button : discord.ui.Button):
        
        await self.interaction_safe(interaction)

        data = get_roblox_id_db(interaction.user.id)
        if data is None:
            await interaction.followup.send(
                "❌ Your account is not verified.", 
                ephemeral=True,
            )
            return

        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.followup.send(
                "❌ Server not configured.", 
                ephemeral=True,
            )
            return
        
        # Discord and Roblox role handling
        channel_id, role_id, group_id, sub_one, sub_two, sub_three = config
        
        try:

            await sync_discord_roles(interaction.user, interaction, int(group_id), int(sub_one), int(sub_two), int(sub_three))

        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while updating your roles: {e}"
            )

# ------------------------------ EMBED ------------------------------

def create_verification_embed():
    return discord.Embed(
        title="- Roblox Verification -",
        description="1. React with a '✅' to the message in the '📘・server-rules' channel.\n2. Click the 'Start Verification' button below. \n\n> If you are already Verified click 'Update' to update your server roles.",
        color=0xffd739
    )

# ------------------------------ BOT COMMANDS ------------------------------

# /setup_cotvs
@Bot.tree.command(name="setup-cotvs", description="Sets up the 'Chief-Of-The-Verification-Staff' Bot.")
@app_commands.checks.has_permissions(administrator=True)
async def setup_cotvs(interaction : discord.Interaction, role : discord.Role, server_rules_channel_id : str, server_rules_message_id : str,  group_id : int, sub_group_id_one : int, sub_group_id_two : int, sub_group_id_three : int):
    
    set_guild_config(interaction.guild.id, interaction.channel.id, role.id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three)
    save_server_rules_ids(interaction.guild.id, int(server_rules_channel_id), int(server_rules_message_id))

    await interaction.response.send_message(
        "✅ Setup complete.", 
        ephemeral=True,
    )
    await interaction.channel.send(embed=create_verification_embed(), view=VerifyView())

# ------------------------------ MAIN ------------------------------

async def close_session():
    global http_session
    if http_session:
        await http_session.close()

init_database()
try:
    Bot.run(discord_token, log_handler=handler, log_level=logging.DEBUG)
finally:
    asyncio.run(close_session())
