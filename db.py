'''

Controls and holds all functions of the sql database 

Function list:
.init_database()
.set_guild_config(guild_id, channel_id, role_id, group_id, sub_group_id_one, sub_group_id_two, sub_group_id_three)
.get_guild_config(guild_id)
.save_pending(discord_id, roblox_id, code, created_at)
.get_pending(discord_id)
.delete_pending(discord_id)
.save_verify(discord_id, roblox_id)
.get_roblox_id(discord_id)
.save_server_rules_ids(guild_id, channel_id, message_id)
.get_server_rules_ids(guild_id)
.save_accepted_rules(guild_id, user_id)
.has_accepted_rules(guild_id, user_id)

'''

import sqlite3

# Sql file setup
DB_FILE = 'main_storage.db'

# ------------------------------ INIT ------------------------------

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
        code TEXT,
        created_at INTEGER
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

    c.execute("""
    CREATE TABLE IF NOT EXISTS accepted_rules (
        guild_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (guild_id, user_id)
    )
    """)

    conn.commit()
    conn.close()

# ------------------------------ FUNCTIONS ------------------------------

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
def save_pending(discord_id, roblox_id, code, created_at):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO pending_verifications VALUES (?, ?, ?, ?)", 
        (discord_id, roblox_id, code, created_at)
    )
    conn.commit()
    conn.close()

# Get pending verification with the discord id
def get_pending(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT roblox_id, code, created_at FROM pending_verifications WHERE discord_id = ?", 
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

def get_roblox_id(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT roblox_id FROM verified WHERE discord_id = ?", 
        (discord_id,)
    )
    data = c.fetchone()
    conn.close()
    return data

def save_server_rules_ids(guild_id, channel_id, message_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO server_rules_ids VALUES (?, ?, ?)", 
        (guild_id, channel_id, message_id)
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
    conn.close()
    return data

def save_accepted_rules(guild_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO accepted_rules VALUES (?, ?)",
        (guild_id, user_id)
    )
    conn.commit()
    conn.close()

def has_accepted_rules(guild_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM accepted_rules WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    data = c.fetchone()
    conn.close()
    return data is not None
