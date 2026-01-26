from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import json
import os
import time
import requests
import urllib3
from dotenv import load_dotenv

# Disable insecure request warnings for macOS SSL bypass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'nexus-secret-key-123')

# Configuration
DB_FILE = 'empire_v2.db'
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN') # Need bot token to fetch roles
DISCORD_API_BASE_URL = 'https://discord.com/api/v10'
SUPPORT_SERVER_ID = '1464655628474646611'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Ensure tables exist
    conn.execute('''CREATE TABLE IF NOT EXISTS global_votes (
        user_id INTEGER PRIMARY KEY, last_vote INTEGER DEFAULT 0
    )''')
    conn.commit()
    return conn

def join_support_server(access_token, user_id):
    """Automatically adds the user to the support server using OAuth2 guilds.join scope."""
    url = f"{DISCORD_API_BASE_URL}/guilds/{SUPPORT_SERVER_ID}/members/{user_id}"
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"access_token": access_token}
    try:
        # PUT adds the user to the guild
        r = requests.put(url, headers=headers, json=data, verify=False)
        if r.status_code in [201, 204]:
            print(f"DEBUG: Successfully joined user {user_id} to support server.")
        else:
            print(f"DEBUG: Failed to join user {user_id} to support server: {r.status_code} {r.text}")
    except Exception as e:
        print(f"DEBUG: Error joining support server: {e}")

def get_bot_guilds():
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    try:
        r = requests.get(f"{DISCORD_API_BASE_URL}/users/@me/guilds", headers=headers, verify=False)
        r.raise_for_status()
        return [g['id'] for g in r.json()]
    except Exception as e:
        print(f"DEBUG: Error fetching bot guilds: {e}")
        return []

# Modern Sidebar UI Styling (UnbelievaBoat Style)
STYLE = """
<style>
    :root {
        --bg-dark: #0f0f12;
        --bg-sidebar: #15151a;
        --bg-card: #1a1a22;
        --accent: #00d2ff;
        --accent-hover: #91eae4;
        --text-main: #f0f0f0;
        --text-muted: #888;
        --border: #25252b;
    }
    body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-main); margin: 0; display: flex; height: 100vh; overflow: hidden; }
    
    /* Sidebar */
    .sidebar { width: 260px; background: var(--bg-sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 20px 0; flex-shrink: 0; }
    .sidebar-header { padding: 0 25px 30px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
    .logo { font-size: 20px; font-weight: 900; color: var(--accent); text-transform: uppercase; letter-spacing: 2px; text-decoration: none; }
    .sidebar-menu { flex-grow: 1; }
    .menu-item { padding: 12px 25px; display: flex; align-items: center; color: var(--text-muted); text-decoration: none; font-weight: 600; transition: 0.2s; border-left: 3px solid transparent; }
    .menu-item:hover { background: rgba(0, 210, 255, 0.05); color: var(--text-main); }
    .menu-item.active { background: rgba(0, 210, 255, 0.1); color: var(--accent); border-left-color: var(--accent); }
    .menu-label { margin-left: 12px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }

    /* Main Content */
    .main-content { flex-grow: 1; overflow-y: auto; padding: 40px; }
    .container { max-width: 900px; margin: 0 auto; }
    .page-title { font-size: 28px; font-weight: 800; margin-bottom: 10px; }
    .page-desc { color: var(--text-muted); margin-bottom: 40px; font-size: 16px; }

    /* Cards & Forms */
    .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 30px; margin-bottom: 30px; }
    .card-title { font-size: 18px; font-weight: 700; color: var(--accent); margin-top: 0; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; }
    .form-group { margin-bottom: 25px; }
    label { display: block; font-weight: 700; color: var(--text-muted); text-transform: uppercase; font-size: 12px; margin-bottom: 10px; }
    input, select, textarea { width: 100%; padding: 14px; background: var(--bg-dark); border: 1px solid var(--border); border-radius: 8px; color: #fff; box-sizing: border-box; font-family: inherit; font-size: 14px; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 10px rgba(0, 210, 255, 0.1); }
    
    .btn { background: var(--accent); color: #000; padding: 14px 28px; border-radius: 8px; border: none; font-weight: 800; cursor: pointer; text-decoration: none; display: inline-block; transition: 0.3s; text-transform: uppercase; font-size: 14px; letter-spacing: 1px; }
    .btn:hover { background: var(--accent-hover); transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 210, 255, 0.3); }
    
    /* List Items (Role Shop/Assets) */
    .list-item { display: flex; align-items: center; justify-content: space-between; background: var(--bg-dark); padding: 15px 20px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 10px; }
    .list-item-info { flex-grow: 1; }
    .list-item-name { font-weight: 700; font-size: 15px; }
    .list-item-price { color: var(--accent); font-size: 13px; font-weight: 600; }
    .btn-delete { color: #ff4757; background: transparent; border: none; cursor: pointer; font-size: 18px; padding: 5px; }
    .btn-delete:hover { color: #ff6b81; }

    /* Modals */
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); z-index: 1000; align-items: center; justify-content: center; }
    .modal-content { background: var(--bg-card); width: 450px; padding: 30px; border-radius: 16px; border: 1px solid var(--border); }
    .modal-actions { display: flex; gap: 10px; margin-top: 25px; }
</style>
"""

def get_bot_guilds():
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    try:
        r = requests.get(f"{DISCORD_API_BASE_URL}/users/@me/guilds", headers=headers, verify=False)
        r.raise_for_status()
        return [g['id'] for g in r.json()]
    except Exception as e:
        print(f"DEBUG: Error fetching bot guilds: {e}")
        return []

def get_server_roles(guild_id):
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    try:
        r = requests.get(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/roles", headers=headers, verify=False)
        if r.status_code == 404:
            print(f"DEBUG: Bot not in guild {guild_id}")
            return None # Indicate bot not in guild
        r.raise_for_status()
        return sorted(r.json(), key=lambda x: x['position'], reverse=True)
    except Exception as e:
        print(f"DEBUG: Error fetching roles for {guild_id}: {e}")
        return []

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/@vite/client')
def vite_client():
    return '', 204

@app.route('/')
def index():
    print(f"DEBUG: Client ID: {CLIENT_ID}")
    if 'access_token' in session:
        return redirect('/servers')
    
    login_url = f"{DISCORD_API_BASE_URL}/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds%20guilds.join"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Empire Nexus | Control Center</title>
        {STYLE}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    </head>
    <body style="background-color: #0a0a0c !important; color: white !important;">
        <div class="navbar">
            <div class="logo">Empire Nexus</div>
        </div>
        <div class="container" style="text-align: center; margin-top: 15vh;">
            <h1 style="font-size: 56px; margin-bottom: 10px; font-weight: 900; background: linear-gradient(to right, #00d2ff, #91eae4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">EMPIRE NEXUS</h1>
            <p style="color: #888; font-size: 20px; margin-bottom: 40px; letter-spacing: 1px;">THE ULTIMATE COMMAND CENTER FOR YOUR DISCORD KINGDOM.</p>
            <a href="{login_url}" class="btn" style="padding: 15px 40px; font-size: 18px; box-shadow: 0 4px 15px rgba(0, 210, 255, 0.3);">CONNECT WITH DISCORD</a>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/callback')
def callback():
    code = request.args.get('code')
    print(f"DEBUG: Callback received with code: {code[:5]}...")
    
    if not code:
        print("DEBUG: No code received in callback!")
        return "Error: No code received from Discord", 400

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        # Bypassing SSL for the token request too since we are on macOS
        print(f"DEBUG: Attempting token request to Discord...")
        r = requests.post(f"{DISCORD_API_BASE_URL}/oauth2/token", data=data, headers=headers, verify=False, timeout=10)
        print(f"DEBUG: Token response status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"DEBUG: Token error body: {r.text}")
            return f"Discord Token Error: {r.text}", r.status_code

        token_data = r.json()
        access_token = token_data['access_token']
        session['access_token'] = access_token
        
        # 1. Fetch user ID to join support server
        user_r = requests.get(f"{DISCORD_API_BASE_URL}/users/@me", headers={'Authorization': f"Bearer {access_token}"}, verify=False)
        if user_r.status_code == 200:
            user_data = user_r.json()
            user_id = user_data['id']
            # 2. Automatically join the support server
            join_support_server(access_token, user_id)
            
        print("DEBUG: Access token stored in session. Redirecting to /servers...")
        return redirect('/servers')
    except Exception as e:
        print(f"DEBUG: Callback exception type: {type(e).__name__}")
        print(f"DEBUG: Callback exception details: {str(e)}")
        return f"Authentication Failed: {str(e)}", 500

@app.route('/servers')
def servers():
    if 'access_token' not in session: 
        return redirect('/')
    
    try:
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        r = requests.get(f"{DISCORD_API_BASE_URL}/users/@me/guilds", headers=headers, verify=False)
        r.raise_for_status()
        guilds = r.json()
        
        bot_guilds = get_bot_guilds()
    except Exception as e:
        print(f"DEBUG: Servers error: {str(e)}")
        return f"Failed to fetch servers: {str(e)}", 500
    
    manageable = [g for g in guilds if (int(g['permissions']) & 0x20) == 0x20]
    
    server_cards = ""
    for g in manageable:
        is_bot_in = g['id'] in bot_guilds
        icon_url = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g['icon'] else "https://discord.com/assets/1f0ac53a65725674052e731c4708805.png"
        
        if is_bot_in:
            action_btn = f'<a href="/dashboard/{g["id"]}" class="btn" style="width: 100%; box-sizing: border-box; text-align: center;">Configure</a>'
            status_tag = '<span style="color: #2ecc71; font-size: 10px; font-weight: 800; text-transform: uppercase;">● Active</span>'
        else:
            # Use the precise permission bitmask (2416299008) requested by the user
            invite_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=2416299008&integration_type=0&scope=bot+applications.commands&guild_id={g['id']}&disable_guild_select=true"
            action_btn = f'<a href="{invite_url}" class="btn" style="width: 100%; box-sizing: border-box; background: #5865F2; color: white; text-align: center;">Invite Bot</a>'
            status_tag = '<span style="color: #e74c3c; font-size: 10px; font-weight: 800; text-transform: uppercase;">● Not in Server</span>'

        server_cards += f"""
        <div class="card" style="width: 250px; display: inline-block; margin: 10px; vertical-align: top; text-align: left; padding: 20px;">
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                <img src="{icon_url}" style="width: 50px; height: 50px; border-radius: 50%; border: 2px solid var(--border);">
                <div>
                    <div style="font-weight: 800; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 140px;">{g['name']}</div>
                    {status_tag}
                </div>
            </div>
            {action_btn}
        </div>
        """

    return f"""
    <html>
        <head>
            <title>Empire Nexus | Kingdoms</title>
            {STYLE}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        </head>
        <body style="display: block; overflow-y: auto;">
            <div class="sidebar">
                <div class="sidebar-header">
                    <a href="/" class="logo">Empire Nexus</a>
                </div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item active"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=2416299008&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container" style="max-width: 1200px;">
                    <h1 class="page-title">Your Kingdoms</h1>
                    <p class="page-desc">Select a server to configure or invite the bot to new lands.</p>
                    <div style="display: flex; flex-wrap: wrap; justify-content: flex-start;">
                        {server_cards}
                    </div>
                </div>
            </div>
        </body>
        <!-- Logout Confirmation Modal -->
        <div id="logoutModal" class="modal">
            <div class="modal-content">
                <h2 class="card-title" style="color: #ff4757;">🚪 Confirm Logout</h2>
                <p style="color: var(--text-muted); margin-bottom: 25px;">Are you sure you want to log out? You will need to re-authenticate with Discord to access your kingdoms again.</p>
                <div class="modal-actions" style="display: flex; gap: 15px;">
                    <a href="/logout" id="confirmLogout" class="btn" style="flex: 1; background: #ff4757; color: white; text-align: center; text-decoration: none; display: flex; align-items: center; justify-content: center;">Yes, Logout</a>
                    <button type="button" onclick="closeModal('logoutModal')" class="btn" style="flex: 1; background: #25252b; color: #fff; cursor: pointer;">Cancel</button>
                </div>
            </div>
        </div>
        <script>
            function openModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
            function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
            
            // Override default logout links to show modal
            document.querySelectorAll('a[href="/logout"]').forEach(el => {{
                el.addEventListener('click', function(e) {{
                    if (this.id === 'confirmLogout') return; // Don't intercept the actual logout button
                    e.preventDefault();
                    openModal('logoutModal');
                }});
            }});
        </script>
    </html>
    """

@app.route('/dashboard/<int:guild_id>')
def dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    
    conn = get_db()
    config = conn.execute('SELECT * FROM guild_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()
    
    prefix = config['prefix'] if config else '!'
    role_shop = json.loads(config['role_shop_json']) if config and config['role_shop_json'] else {}
    custom_assets = json.loads(config['custom_assets_json']) if config and config['custom_assets_json'] else {}
    
    roles = get_server_roles(guild_id)
    
    # Handle bot not in server
    if roles is None:
        return f"""
        <html><head>{STYLE}</head><body style="justify-content: center; align-items: center; text-align: center;">
            <div class="card">
                <h1 style="color: #e74c3c;">Bot Not Found</h1>
                <p>The bot must be in the server to fetch roles and manage settings.</p>
                <a href="/servers" class="btn">Go Back to Kingdoms</a>
            </div>
        </body></html>
        """

    # Pre-render Role Shop list
    role_items_html = ""
    for r_id, price in role_shop.items():
        role_name = next((r['name'] for r in roles if r['id'] == r_id), f"Unknown Role ({r_id})")
        role_items_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{role_name}</div>
                <div class="list-item-price">{price:,} coins</div>
            </div>
            <button onclick="deleteItem('role', '{r_id}')" class="btn-delete">×</button>
        </div>
        """
        
    # Pre-render Assets list
    asset_items_html = ""
    
    from bot import DEFAULT_ASSETS
    display_assets = {**DEFAULT_ASSETS, **custom_assets}

    for a_id, data in display_assets.items():
        asset_items_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{data['name']}</div>
                <div class="list-item-price">{data['price']:,} coins • {data['income']:,}/10min</div>
            </div>
            <button onclick="deleteItem('asset', '{a_id}')" class="btn-delete">×</button>
        </div>
        """

    success_msg = ""
    if request.args.get('success'):
        success_msg = '<div id="success-toast" style="background: #2ecc71; color: #000; padding: 15px; border-radius: 8px; font-weight: 800; margin-bottom: 20px; animation: slideIn 0.5s;">✅ DEPLOYMENT SUCCESSFUL! Changes are live.</div>'

    return f"""
    <html>
        <head>
            <title>Nexus | {guild_id}</title>
            {STYLE}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
            <style>
                @keyframes slideIn {{ from {{ transform: translateY(-20px); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}
            </style>
        </head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header">
                    <a href="/" class="logo">Empire Nexus</a>
                </div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="#" class="menu-item active"><span class="menu-label">⚙️ General Settings</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=2416299008&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>

            <div class="main-content">
                <div class="container">
                    {success_msg}
                    <h1 class="page-title">Kingdom Configuration</h1>
                    <p class="page-desc">Manage your server's prefix, shop items, and custom assets.</p>

                    <form id="mainForm" action="/save/{guild_id}" method="post" onsubmit="updateUI(false)">
                        <!-- Prefix Card -->
                        <div class="card">
                            <h2 class="card-title">General Settings</h2>
                            <div class="form-group">
                                <label>Command Prefix</label>
                                <input type="text" name="prefix" value="{prefix}" placeholder="e.g. !">
                            </div>
                        </div>

                        <!-- Role Shop Card -->
                        <div class="card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h2 class="card-title" style="margin: 0;">Role Shop</h2>
                                <button type="button" onclick="openModal('roleModal')" class="btn" style="padding: 8px 16px; font-size: 12px;">+ Add Role</button>
                            </div>
                            <div id="roleList">{role_items_html}</div>
                            <input type="hidden" name="role_shop" id="roleShopInput" value='{json.dumps(role_shop)}'>
                        </div>

                        <!-- Assets Card -->
                        <div class="card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h2 class="card-title" style="margin: 0;">Passive Income Assets</h2>
                                <button type="button" onclick="openModal('assetModal')" class="btn" style="padding: 8px 16px; font-size: 12px;">+ Add Asset</button>
                            </div>
                            <div id="assetList">{asset_items_html}</div>
                            <input type="hidden" name="custom_assets" id="assetsInput" value='{json.dumps(display_assets)}'>
                        </div>

                        <button type="submit" class="btn" style="width: 100%; padding: 20px; font-size: 16px;">DEPLOY TO KINGDOM</button>
                    </form>
                </div>
            </div>

            <!-- Role Modal -->
            <div id="roleModal" class="modal">
                <div class="modal-content">
                    <h2 class="card-title">Add Role to Shop</h2>
                    <div class="form-group">
                        <label>Select Role</label>
                        <select id="modalRoleSelect">
                            {" ".join([f'<option value="{r["id"]}">{r["name"]}</option>' for r in roles if r['name'] != '@everyone'])}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Price (Coins)</label>
                        <input type="number" id="modalRolePrice" value="1000">
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="addRole()" class="btn" style="flex: 1;">Add</button>
                        <button onclick="closeModal('roleModal')" class="btn btn-secondary" style="flex: 1; background: #25252b; color: #fff;">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Asset Modal -->
            <div id="assetModal" class="modal">
                <div class="modal-content">
                    <h2 class="card-title">Create New Asset</h2>
                    <div class="form-group">
                        <label>Asset Name</label>
                        <input type="text" id="modalAssetName" placeholder="e.g. Gold Mine">
                    </div>
                    <div class="form-group">
                        <label>Price</label>
                        <input type="number" id="modalAssetPrice" value="5000">
                    </div>
                    <div class="form-group">
                        <label>Income per 10 Minutes</label>
                        <input type="number" id="modalAssetIncome" value="50">
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="addAsset()" class="btn" style="flex: 1;">Create</button>
                        <button onclick="closeModal('assetModal')" class="btn btn-secondary" style="flex: 1; background: #25252b; color: #fff;">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Logout Confirmation Modal -->
            <div id="logoutModal" class="modal">
                <div class="modal-content">
                    <h2 class="card-title" style="color: #ff4757;">🚪 Confirm Logout</h2>
                    <p style="color: var(--text-muted); margin-bottom: 25px;">Are you sure you want to log out? You will need to re-authenticate with Discord to access your kingdoms again.</p>
                    <div class="modal-actions">
                        <a href="/logout" class="btn" id="confirmLogout" style="flex: 1; background: #ff4757; color: white; text-align: center;">Yes, Logout</a>
                        <button onclick="closeModal('logoutModal')" class="btn" style="flex: 1; background: #25252b; color: #fff;">Cancel</button>
                    </div>
                </div>
            </div>

            <script>
                const DEFAULT_ASSETS = {json.dumps(DEFAULT_ASSETS)};
                let roleShop = {json.dumps(role_shop)};
                let customAssets = {json.dumps(custom_assets)};
                
                // Initialize customAssets with defaults if it's empty to show them on first load
                // but only if the user hasn't saved anything yet (this is for visual consistency)
                let combinedAssets = {{...DEFAULT_ASSETS, ...customAssets}};

                function openModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
                function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
                
                // Override default logout links to show modal
                document.querySelectorAll('a[href="/logout"]').forEach(el => {{
                    el.addEventListener('click', function(e) {{
                        if (this.id === 'confirmLogout') return; // Don't intercept the actual logout button
                        e.preventDefault();
                        openModal('logoutModal');
                    }});
                }});

                function addRole() {{
                    const id = document.getElementById('modalRoleSelect').value;
                    const price = parseInt(document.getElementById('modalRolePrice').value);
                    roleShop[id] = price;
                    updateUI(true);
                }}

                function addAsset() {{
                    const name = document.getElementById('modalAssetName').value;
                    const price = parseInt(document.getElementById('modalAssetPrice').value);
                    const income = parseInt(document.getElementById('modalAssetIncome').value);
                    const id = name.toLowerCase().replace(/\\s+/g, '_');
                    combinedAssets[id] = {{ name, price, income }};
                    updateUI(true);
                }}

                function deleteItem(type, id) {{
                    if(type === 'role') delete roleShop[id];
                    else delete combinedAssets[id];
                    updateUI(true);
                }}

                function updateUI(submit = false) {{
                    document.getElementById('roleShopInput').value = JSON.stringify(roleShop);
                    
                    // We only want to save assets that are DIFFERENT from defaults or new
                    // But for simplicity, we save the entire combined list to the custom field
                    // so that deletions of defaults actually persist.
                    document.getElementById('assetsInput').value = JSON.stringify(combinedAssets);
                    if(submit) document.getElementById('mainForm').submit();
                }}

                // Hide toast after 5 seconds
                const toast = document.getElementById('success-toast');
                if(toast) {{
                    setTimeout(() => {{
                        toast.style.display = 'none';
                    }}, 5000);
                }}
            </script>
        </body>
    </html>
    """

@app.route('/save/<int:guild_id>', methods=['POST'])
def save(guild_id):
    prefix = request.form.get('prefix')
    role_shop = request.form.get('role_shop')
    custom_assets = request.form.get('custom_assets')
    
    # Basic validation
    try:
        json.loads(role_shop)
        json.loads(custom_assets)
    except:
        return "Invalid JSON format! Go back and fix it.", 400

    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO guild_config (guild_id, prefix, role_shop_json, custom_assets_json) VALUES (?, ?, ?, ?)', 
                 (int(guild_id), prefix, role_shop, custom_assets))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}?success=1')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/topgg/webhook', methods=['GET', 'POST'])
def topgg_webhook():
    # Handle GET requests for testing
    if request.method == 'GET':
        return '''
        <html>
            <head><title>Top.gg Webhook Test</title></head>
            <body style="font-family: Arial; padding: 20px; background: #1a1a22; color: white;">
                <h1>Top.gg Webhook Endpoint</h1>
                <p>This endpoint accepts POST requests from Top.gg</p>
                <p><strong>Status:</strong> ✅ Active</p>
                <p><strong>Expected Secret:</strong> Check your .env file (TOPGG_WEBHOOK_SECRET)</p>
                <hr>
                <h2>Test Webhook Manually:</h2>
                <form method="POST" style="margin-top: 20px;">
                    <label>User ID:</label><br>
                    <input type="text" name="user_id" placeholder="123456789" style="padding: 10px; width: 300px; margin: 10px 0;"><br>
                    <label>Type:</label><br>
                    <select name="type" style="padding: 10px; width: 300px; margin: 10px 0;">
                        <option value="test">Test</option>
                        <option value="upvote">Upvote</option>
                    </select><br>
                    <label>Authorization Header (Secret):</label><br>
                    <input type="text" name="auth" placeholder="Your webhook secret" style="padding: 10px; width: 300px; margin: 10px 0;"><br>
                    <button type="submit" style="padding: 10px 20px; background: #00d2ff; color: black; border: none; cursor: pointer; margin-top: 10px;">Test Webhook</button>
                </form>
            </body>
        </html>
        ''', 200
    
    # Log ALL incoming webhook details for debugging
    print(f"\n{'='*60}")
    print(f"DEBUG: Incoming Top.gg webhook request")
    print(f"DEBUG: Method: {request.method}")
    print(f"DEBUG: Headers: {dict(request.headers)}")
    print(f"DEBUG: Content-Type: {request.content_type}")
    
    # Handle manual form test
    if request.form:
        print(f"DEBUG: Manual test form submitted")
        user_id_str = request.form.get('user_id')
        vote_type = request.form.get('type', 'test')
        form_auth = request.form.get('auth')
        
        if not user_id_str:
            return "Missing user ID", 400
        
        data = {'type': vote_type, 'user': user_id_str}
        
        # For manual tests, check form auth instead of header
        webhook_secret = os.getenv('TOPGG_WEBHOOK_SECRET', 'nexus_default_secret')
        if form_auth != webhook_secret:
            return f"Unauthorized - Secret mismatch. Expected: {webhook_secret}", 401
        
        print(f"DEBUG: Manual test authorized")
    else:
        # Get raw data first
        try:
            if request.is_json:
                data = request.json
            else:
                data = request.get_json(force=True)
            print(f"DEBUG: JSON Data: {data}")
        except Exception as e:
            print(f"DEBUG: Error parsing JSON: {e}")
            print(f"DEBUG: Raw data: {request.data}")
            return f"Invalid JSON: {str(e)}", 400
        
        # Verify the authorization header from Top.gg (only for real webhooks)
        auth_header = request.headers.get('Authorization')
        webhook_secret = os.getenv('TOPGG_WEBHOOK_SECRET', 'nexus_default_secret')
        
        print(f"DEBUG: Auth Header Received: {auth_header}")
        print(f"DEBUG: Expected Secret: {webhook_secret}")
        
        if auth_header != webhook_secret:
            print(f"DEBUG: ❌ Webhook Unauthorized - Expected '{webhook_secret}', got '{auth_header}'")
            return "Unauthorized", 401
    
    print(f"DEBUG: ✅ Authorization passed")
    
    # Handle both 'upvote' and 'test' types
    vote_type = data.get('type') if data else None
    print(f"DEBUG: Vote Type: {vote_type}")
    
    if not data or vote_type not in ['upvote', 'test']:
        print(f"DEBUG: ❌ Invalid data type: {vote_type}")
        return f"Invalid data type: {vote_type}. Expected 'upvote' or 'test'", 400
    
    # Get user ID (can be string or int)
    user_id_str = data.get('user')
    if not user_id_str:
        print(f"DEBUG: ❌ No user ID in data")
        return "Missing user ID", 400
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        print(f"DEBUG: ❌ Invalid user ID format: {user_id_str}")
        return f"Invalid user ID: {user_id_str}", 400
    
    now = int(time.time())
    print(f"DEBUG: Processing vote for user_id: {user_id}, timestamp: {now}")
    
    # Update global_votes table (bot-wide)
    try:
        conn = get_db()
        conn.execute('''
            INSERT INTO global_votes (user_id, last_vote) 
            VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET last_vote = excluded.last_vote
        ''', (user_id, now))
        
        # Also update any existing rows in the users table for immediate effect
        conn.execute('UPDATE users SET last_vote = ? WHERE user_id = ?', (now, user_id))
        conn.commit()
        conn.close()
        
        print(f"DEBUG: ✅ Successfully processed Top.gg {vote_type} for user {user_id}")
        print(f"{'='*60}\n")
        
        if request.method == 'POST' and request.form:
            return f'''
            <html>
                <head><title>Test Result</title></head>
                <body style="font-family: Arial; padding: 20px; background: #1a1a22; color: white;">
                    <h1>✅ Webhook Test Successful!</h1>
                    <p>User ID: {user_id}</p>
                    <p>Type: {vote_type}</p>
                    <p>Timestamp: {now}</p>
                    <p><a href="/topgg/webhook" style="color: #00d2ff;">Test Again</a></p>
                </body>
            </html>
            ''', 200
        
        return "OK", 200
    except Exception as e:
        print(f"DEBUG: ❌ Database error: {e}")
        print(f"{'='*60}\n")
        return f"Database error: {str(e)}", 500

if __name__ == '__main__':
    # Bind to 0.0.0.0 so it's accessible externally on your remote server
    app.run(host='0.0.0.0', port=5001)







