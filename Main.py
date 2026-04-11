'''

Chief-Of-The-Verification-Staff

A Discord Bot that creates a built-in embed to verify, update users roles and present server rules in the Calderian Army Discord Servers

Discord Command List:
/setup_embeds
/setup_config

'''

# ------------------------------ IMPORTS ------------------------------

import discord
from discord import app_commands
from discord.ext import commands

from flask import Flask
from threading import Thread

import logging
from dotenv import load_dotenv
import os
import aiohttp
import random
import string
import re
import asyncio
import time

# Other files
import db

# ------------------------------ .ENV ------------------------------

print("[SETUP] Loading .env variables...")

# Load Environmental Variables 
load_dotenv()

# Get .Env Variables
discord_token = os.getenv('DISCORD_TOKEN')
print(f"[SETUP] discord_token: {bool(discord_token)}")
main_guild_id = int(os.getenv('MAIN_GUILD_ID'))
print(f"[SETUP] main_guild_id: {bool(main_guild_id)}")

print(f"[SETUP] Loaded all .env variables.")

# ------------------------------ FLASK KEEP ALIVE ------------------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ------------------------------ LOGGING ------------------------------

handler = logging.FileHandler(filename='discord_bot.log', encoding='utf-8', mode='w')

# Error logger
async def log_error(interaction: discord.Interaction | None, func: str, code: int, e: Exception | str):
    msg = f"[ERROR] func = {func} ({code}), Error: {e}"
    
    # Print to console
    print(msg)

    # Try to notify user if interaction exists
    if interaction:
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ An error occurred. Please contact a developer.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ An error occurred. Please contact a developer.", ephemeral=True)
        except Exception:
            # If even that fails, just ignore
            pass

# ------------------------------ INTENTS ------------------------------

intents = discord.Intents.default()
intents.members = True

# ------------------------------ HTTP SESSION HANDLING ------------------------------

http_session = None

async def ensure_http_session():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

# ------------------------------ ROBLOX API HANDLING ------------------------------

# Generates a six digit code
def generate_code_six() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Get the roblox id of a user using their username
async def get_roblox_id(username):
    await ensure_http_session()
    async with http_session.post(
        "https://users.roblox.com/v1/usernames/users",
        json={"usernames" : [username]}, 
        timeout=10
    ) as response:
        try:
            data = await response.json()
        except Exception:
            return 0
        if data.get("data"):
            return data["data"][0]["id"]
    return None

# Get the profile description of a user using their roblox id
async def get_profile_description(user_id):
    await ensure_http_session()
    async with http_session.get(f"https://users.roblox.com/v1/users/{user_id}", timeout=10) as response:
        try:
            data = await response.json()
        except Exception:
            return 0
        return data.get("description", "")
        
# Get the group rank of a user using their roblox user id and group id
async def get_group_rank(user_id, group_id):
    await ensure_http_session()
    async with http_session.get(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles", timeout=10) as response:
        try:
            data = await response.json()
        except Exception:
            return 0

        for group in data.get("data", []):
            if group["group"]["id"] == group_id:
                return group["role"]["rank"]
    return 0

async def get_roblox_username(roblox_user_id : int):
    await ensure_http_session()
    async with http_session.get(f"https://users.roblox.com/v1/users/{roblox_user_id}", timeout=10) as response:
        try:
            data = await response.json()
        except Exception:
            return 0
        return data.get("name", "Unknown")

async def fetch_group_data(group_id):
    await ensure_http_session()
    async with http_session.get(f"https://groups.roblox.com/v1/groups/{group_id}", timeout=10) as response:
        try:
            data = await response.json()
        except Exception:
            return 0
        return data
            
    return None

# ------------------------------ ROBLOX & DISCORD ROLE SYNC ------------------------------

def remove_leading_bracket(string : str) -> str:
    return re.sub(r'^\[.*?\]\s*','',string)

async def FetchRobloxGroupRole(discord_user_id: int, group_id):
    await ensure_http_session()
    
    # Fetches the Roblox group role for the specified group ID and interaction
    data = db.get_roblox_id(discord_user_id)
    if not data:
        return None

    roblox_user_id = data[0]

    if not roblox_user_id:
        return None

    # ---------------- FETCH GROUP DATA ----------------
    try:
        membership_url = f"https://groups.roblox.com/v1/users/{roblox_user_id}/groups/roles"

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
        await log_error(None, "FetchRobloxGroupRole", 1, e)
        return None

async def set_prefix_nickname(member, role_name: str):
    try: 
        match = re.match(r'^\[.*?\]', role_name)
        prefix = match.group(0) if match else ""

        if prefix != "":
            prefix = f"{prefix}]" 
        else:
            if role_name[:3] == "PRE": # Government rank
                prefix = "[PRESIDENT]"
            else:
                prefix = ""

        try:
            data = db.get_roblox_id(member.id)
            if data is not None:
                rblx_username = await get_roblox_username(data[0])
            else:
                rblx_username = "Unknown"
            await member.edit(nick=f"{prefix} {rblx_username}")
        except discord.Forbidden:
            await log_error(None, "set_prefix_nickname", 1, "Missing Permissions")
            return
        except discord.HTTPException as e:
            await log_error(None, "set_prefix_nickname", 2, e)
            return
            
    except Exception as e:
        await log_error(None, "set_prefix_nickname", 3, e)
        return

async def get_group_name_async(group_id):
    try:
        data = await fetch_group_data(group_id)
    except Exception:
        return None
    
    if data:
        return data.get("name")
    return None

async def get_roblox_multi_group_role(member : discord.member, interaction : discord.Interaction, group_id : int, sub_one : int, sub_two : int, sub_three : int):

    try:
        group_role = await FetchRobloxGroupRole(member.id, group_id)
        subgroup_name = None
    except Exception as e:
        await log_error(interaction, "get_roblox_multi_group_role", 1, e)
        return None, None

    # Collect subgroup ids that are non-zero in order of priority
    sub_ids = [sid for sid in (sub_one, sub_two, sub_three) if sid]
    if not sub_ids:
        return group_role, None

    fetch_tasks = [get_group_name_async(sid) for sid in sub_ids]
    names = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Normalize and compare; only re-resolve role if a match is found
    for sid, name in zip(sub_ids, names):
        if isinstance(name, Exception) or name is None:
            continue
        normalized = remove_leading_bracket(name)
        if group_role and normalized == group_role.get("name"):
            try:
                group_role = await FetchRobloxGroupRole(member.id, sid)
                subgroup_name = normalized
            except Exception as e:
                await log_error(interaction, "get_roblox_multi_group_role", 2, f"Error fetching subgroup role for {sid}: {e}")
            break
    
    return group_role, subgroup_name

async def sync_discord_roles(member: discord.Member, interaction: discord.Interaction, group_id : int, sub_one : int, sub_two : int, sub_three : int):

    bot_member = interaction.guild.me

    if not bot_member.guild_permissions.manage_roles:
        await log_error(interaction, "sync_discord_roles", 1, "Missing Manage roles permission")
        return

    if not bot_member.guild_permissions.manage_nicknames:
        await log_error(interaction, "sync_discord_roles", 2, "Missing Change nicknames permission")
        return

    # ---------------- FETCH ROLE ----------------
    
    group_role, subgroup_name = await get_roblox_multi_group_role(member, interaction, group_id, sub_one, sub_two, sub_three)

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
        if role:
            keep_role_names.add(role.name)

        if not role:
            # Try a normalized lookup (in case of spacing/casing differences)
            role = discord.utils.find(
                lambda r: r.name.lower() == role_name.lower(),
                interaction.guild.roles
            )

        if not role:
            await log_error(interaction, "sync_discord_roles", 3, f"The {role_name} discord role does not exist.")
            return

        # Determine the new category for this role
        new_category_name = None
        if subgroup_name:
            new_category_name = subgroup_name
        else:
            if interaction.guild.id == main_guild_id or any(clean_name.startswith(p) for p in CSB_PREFIXES):
                if any(clean_name.startswith(p) for p in ENLISTED_PREFIX):
                    new_category_name = CATEGORY_ROLE_NAMES["ENLISTED"]
                elif any(clean_name.startswith(p) for p in OFFICER_PREFIX):
                    new_category_name = CATEGORY_ROLE_NAMES["OFFICER"]
                elif any(clean_name.startswith(p) for p in CSB_PREFIXES):
                    new_category_name = CATEGORY_ROLE_NAMES["CHIEF_OF_STAFF_BOARD"]
                elif any(clean_name.startswith(p) for p in DEV_PREFIX):
                    new_category_name = CATEGORY_ROLE_NAMES["DEVELOPER"]
            else:
                new_category_name = "HQ"

        # Resolve category role object (may be None if not configured)
        category_role = None
        if new_category_name:
            try:
                category_role = discord.utils.get(interaction.guild.roles, name=new_category_name)
            except Exception as e:
                await log_error(interaction, "sync_discord_roles", 4, f"The {new_category_name} discord role does not exist. Error Msg: {e}")

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
                await log_error(interaction, "sync_discord_roles", 5, f"Failed to remove roles for {member.id}. Error Msg: {e}")

        # Add the main role if missing
        if role not in member.roles:
            try:
                await member.add_roles(role, reason="Syncing Roblox rank")
            except discord.Forbidden:
                await log_error(interaction, "sync_discord_roles", 6, f"Permission denied when adding role {role.name} to {member.id}")
            except discord.HTTPException as e:
                await log_error(interaction, "sync_discord_roles", 7, f"Failed to add role {role.name} to {member.id}. Error Msg: {e}")

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
                await log_error(interaction, "sync_discord_roles", 8, f"Failed to remove conflicting category roles for {member.id}. Error Msg: {e}")

        # Add the category role if applicable and missing
        if category_role and category_role not in member.roles:
            try:
                await member.add_roles(category_role, reason="Syncing category role")
            except discord.Forbidden:
                await log_error(interaction, "sync_discord_roles", 9, f"Permission denied when adding category role {category_role.name} to {member.id}")
            except discord.HTTPException as e:
                await log_error(interaction, "sync_discord_roles", 10, f"Failed to add category role {category_role.name} to {member.id}. Error Msg: {e}")

        # Nickname update
        try:
            await set_prefix_nickname(member, role_name)
        except Exception as e:
            await log_error(interaction, "sync_discord_roles", 11, f"Failed to set nickname for {member.id}. Error Msg: {e}")

        # DM the user (best-effort)
        try:
            await member.send(f"You have been ranked in 'Calderian Army' to the '**{role.name}**' rank.")
        except discord.Forbidden:
            pass

        return 1
    
    # ---------------- WHEN USER HAS NO ROBLOX GROUP ROLE ----------------
    else:
        # Remove all non-exempt roles (we will keep category roles only if desired)
        default_role = interaction.guild.default_role
        roles_to_strip = [
            r for r in member.roles
            if (
                r.name not in ["Roblox Verified", default_role.name]
                and not r.managed
                and r < interaction.guild.me.top_role
            )
        ]
        if roles_to_strip:
            try:
                await member.remove_roles(*roles_to_strip, reason="User not in Roblox group")
            except discord.HTTPException as e:
                await log_error(interaction, "sync_discord_roles", 12, f"Failed to strip roles for {member.id}. Error Msg: {e}")

        civilian_role = discord.utils.get(interaction.guild.roles, name="[CIV] Civilian")
        if civilian_role and civilian_role not in member.roles:
            try:
                await member.add_roles(civilian_role, reason="Assign civilian role")
            except discord.Forbidden:
                await log_error(interaction, "sync_discord_roles", 13, f"Permission denied when adding civilian role to {member.id}")
            except discord.HTTPException as e:
                await log_error(interaction, "sync_discord_roles", 14, f"Failed to add civilian role to {member.id}. Error Msg: {e}")

        try:
            await member.send(
                f"You have been ranked in the {interaction.guild.name} Discord Server\n"
                "You are not in the Roblox group. You have been given the role: **Civilian**."
            )
        except discord.Forbidden:
            pass

        return 1


# ------------------------------ BOT ------------------------------

# Bot Class
class C_Bot(commands.Bot):
    async def setup_hook(self):
        keep_alive()
        await ensure_http_session()

        self.add_view(VerifyView())

    async def on_ready(self):
        try:
            await self.tree.sync()
            print(f"[SETUP] Complete - Bot Online: {self.user}")
        except Exception as e:
            print(f"[ERROR] func = on_ready (1), Error: {e}")
        
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
        db.save_pending(discord_id=interaction.user.id, roblox_id=roblox_id, code=code, created_at=int(time.time()))

        await interaction.response.send_message(
            f"Put this code into your Roblox bio:\n\n**{code}**\n\nThen press **Complete Verification**",
            ephemeral=True,
        )

# ------------------------------ TRACK REACTIONS ------------------------------

@Bot.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != "✅":
        return

    guild = Bot.get_guild(payload.guild_id)
    if not guild:
        return

    ids = db.get_server_rules_ids(payload.guild_id)
    if not ids:
        return

    channel_id, message_id = ids

    if payload.channel_id == channel_id and payload.message_id == message_id:
        db.save_accepted_rules(payload.guild_id, payload.user_id)


# ------------------------------ VIEW ------------------------------

# Creates the ui for verification and handles the main logic

class StartVerificationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Start Verification",
            style=discord.ButtonStyle.blurple,
            custom_id="persistent_start_verification"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            ids = db.get_server_rules_ids(interaction.guild.id)
            if ids is None:
                log_error(interaction, "StartVerificationButton", 1, "Guild not configured")
                return

            channel_id, message_id = ids
            channel = interaction.guild.get_channel(channel_id)

            if not channel:
                await interaction.response.send_message("❌ Rules channel not found.", ephemeral=True)
                return

            # FAST DB CHECK
            if not db.has_accepted_rules(interaction.guild.id, interaction.user.id):
                await interaction.response.send_message(
                    "You must accept the rules first by reacting with '✅' in the rules channel.",
                    ephemeral=True
                )
                return

            # MODAL
            await interaction.response.send_modal(UsernameModal())

        except Exception as e:
            await log_error(interaction, "StartVerificationButton", 2, e)

class CompleteVerificationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Complete Verification",
            style=discord.ButtonStyle.green,
            custom_id="persistent_complete_verification"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            data = db.get_pending(interaction.user.id)
            if not data:
                await interaction.followup.send("❌ Start Verification first.", ephemeral=True)
                return
            roblox_id, code, created_at = data

            # Expiry check (10 minutes = 600 seconds)
            if time.time() - created_at > 600:
                db.delete_pending(interaction.user.id)
                await interaction.followup.send("❌ Verification expired. Start again.", ephemeral=True)
                return
            
            config = db.get_guild_config(interaction.guild.id)
            if not config:
                log_error(interaction, "CompleteVerificationButton", 1, "Guild not configured")
                return
            channel_id, role_id, group_id, sub_one, sub_two, sub_three = config
            
            description = await get_profile_description(roblox_id)
            if code not in description:
                await interaction.followup.send("❌ Code not in bio.", ephemeral=True)
                return
            
            try:
                result = await sync_discord_roles(interaction.user, interaction, int(group_id), int(sub_one), int(sub_two), int(sub_three))
                if result == 1:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        await interaction.user.add_roles(role) # adds verified role

                    db.save_verify(interaction.user.id, roblox_id)  
                    db.delete_pending(interaction.user.id)

                    await interaction.followup.send("✅ Verified!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error with Verification.", ephemeral=True)
                    return
            except Exception as e:
                await log_error(interaction, "CompleteVerificationButton", 2, e)

        except Exception as e:
            await log_error(interaction, "CompleteVerificationButton", 3, e)
        
        

class UpdateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Update",
            style=discord.ButtonStyle.green,
            custom_id="persistent_update_verification",
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            data = db.get_roblox_id(interaction.user.id)
            if data is None:
                await interaction.followup.send("❌ Your account is not verified.", ephemeral=True)
                return
            
            config = db.get_guild_config(interaction.guild.id)
            if not config:
                log_error(interaction, "UpdateButton", 1, "Guild not configured")
                return
            channel_id, role_id, group_id, sub_one, sub_two, sub_three = config

            try:
                result = await sync_discord_roles(interaction.user, interaction, int(group_id), int(sub_one), int(sub_two), int(sub_three))
                if result == 1:
                    await interaction.followup.send("✅ Roles updated!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Roles not updated.", ephemeral=True)
            except Exception as e:
                await log_error(interaction, "UpdateButton", 1, e)
                return
            
        except Exception as e:
            await log_error(interaction, "UpdateButton", 2, e)
        
        


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent
        self.add_item(StartVerificationButton())
        self.add_item(CompleteVerificationButton())
        self.add_item(UpdateButton())

# ------------------------------ EMBED ------------------------------

def create_verification_embed():
    return discord.Embed(
        title="- Roblox Verification -",
        description="1. React with a '✅' to the message in the '📘・server-rules' channel.\n"
        "2. Click the 'Start Verification' button below. \n\n"
        "> If you are already Verified click 'Update' to update your server roles.",
        color=discord.Color(0xffd739)
    )

def create_server_rules_embed():
    return discord.Embed(
        description="1. **ALL** Not-Safe-For-Work (NSFW) content or actions are prohibited.\n"
            "2. **DO NOT** Spam anything on any channels.\n"
            "3. Be kind to **EVERYONE** on this server, we don't want bullying of any sort.\n"
            "4. **NO** Abusing any power as you are privileged to have it :slight_smile: . \n"
            "5. **DO NOT** Make fake bug reports or post dumb ideas on ideas-and-suggestions.\n"
            "6. **NO** Excessive profanity.\n"
            "7. **NO** Discriminatory language or profanity.\n"
            "8. **ALL** Forms of Online dating are prohibited.\n"
            "9. **NO** Pinging Command or High ranking staff.\n"
            "10. **NO** Advertisement unless by command staff.\n"
            "11. **DO NOT** Attempt to hack or exploit any moderation or other systems.\n"
            "12. **DO NOT** Share any personal information with anyone, or ask someone for their Personal Information.\n\n"
            "> Ask someone or reach out to our development team, if you have any *important* questions about the rules.\n\n"
            "## If ANY of these rules are broken, appropriate action will be taken depending on the severity and frequency of the offense. This may include a warning, mute, kick, or ban from the server.", 
        color=discord.Color(0xffd739)
    )

# ------------------------------ BOT COMMANDS ------------------------------

# Commannd error catcher
@Bot.tree.error
async def on_app_commmand_error(interaction : discord.Interaction, error : app_commands.AppCommandError):
    await log_error(interaction, "on_app_commmand_error", 1, error)

# /setup_config
@Bot.tree.command(name="setup-config", description="Sets up the config for the Bot (Use `/setup_embeds` first).")
@app_commands.checks.has_permissions(administrator=True)
async def setup_config(interaction : discord.Interaction, role : discord.Role,  group_id : int, sub_group_id_one : int, sub_group_id_two : int, sub_group_id_three : int):
    await interaction.response.defer(ephemeral=True)

    await interaction.followup.send("Setting up config...", ephemeral=True)

    server_rules_ids = db.get_server_rules_ids(interaction.guild.id)
    if not server_rules_ids:
        await interaction.followup.send("Server rules ids, Invalid, Run `/setup_embeds` first.", ephemeral=True)
        return

    try:
        db.set_guild_config(interaction.guild.id, interaction.channel.id, role.id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three)

        await interaction.followup.send(
            "✅ Setup complete.", 
            ephemeral=True,
        )
    except Exception as e:
        await log_error(interaction, "setup_config", 1, e)

    

# /setup_embeds
@Bot.tree.command(name="setup-embeds", description="Sets up the Server rules embed and the verification emded (Use in #Verification).")
@app_commands.checks.has_permissions(administrator=True)
async def setup_embeds(interaction : discord.Interaction, server_rules_channel_id : str, server_rules_message_id : str | None):
    await interaction.response.defer(ephemeral=True)

    await interaction.followup.send("Setting up embeds...", ephemeral=True)

    # Validate channel
    try:
        server_rules_channel = interaction.guild.get_channel(int(server_rules_channel_id))
        if server_rules_channel is None:
            await interaction.followup.send("❌ Invalid channel ID.", ephemeral=True)
            return
    except:
        await interaction.followup.send("❌ Invalid channel ID format.", ephemeral=True)
        return

    try:
        
        msg = None

        if server_rules_message_id == None:
            # The embeds do not exist and need to be created
            
            # Send rules embed
            await server_rules_channel.send("# __**Server Rules:**__")
            msg = await server_rules_channel.send(embed=create_server_rules_embed())
            await msg.add_reaction('✅')

            # Send verification embed
            await interaction.channel.send(f"# __**Welcome to the {interaction.guild.name} Discord Server!**__")
            await interaction.channel.send(embed=create_verification_embed(),view=VerifyView())

            # Final response
            await interaction.followup.send("✅ Setup complete.", ephemeral=True)
        else:
            # The embeds do exist and the info from them only needs to be saved

            # validate server_rules_message_id
            try:
                msg = await server_rules_channel.fetch_message(int(server_rules_message_id))
            except discord.NotFound:
                await interaction.followup.send("❌ Invalid message ID.")
                return
            except discord.Forbidden:
                await log_error(interaction, "setup_embeds", 1, "Missing Read Message History permission")
                return
            except Exception as e:
                await log_error(interaction, "setup_embeds", 2, e)
                return

        if msg == None:
            return

        db.save_server_rules_ids(interaction.guild.id, server_rules_channel.id, msg.id)

    except Exception as e:
        await log_error(interaction, "setup_embeds", 3, e)
        return

# ------------------------------ MAIN ------------------------------

async def close_session():
    global http_session
    if http_session:
        await http_session.close()

def shutdown():
    asyncio.run(close_session())

db.init_database()

try:
    print("[SETUP] Starting bot...")
    Bot.run(discord_token, reconnect=True, log_handler=handler, log_level=logging.DEBUG)

except Exception as e:
    print(f"[FATAL] Bot crashed. Error Msg: {e}")

    # Prevent restart spam 
    while True:
        print("[FATAL] Sleeping to avoid rate limit...")
        time.sleep(300)  # 5 minutes
