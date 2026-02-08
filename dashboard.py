from flask import Flask, request, redirect, session
import sqlite3
import json
import os
import time
import requests
import urllib3
import hashlib
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
INVITE_PERMISSIONS = (
    8 | 2 | 4 | 16 | 32 | 128 |
    1024 | 2048 | 8192 | 16384 | 32768 | 65536 | 64 | 262144 |
    1048576 | 2097152 | 4194304 | 8388608 | 16777216 |
    67108864 | 134217728 | 268435456 | 536870912 |
    2147483648
)

# Performance optimization: Use a global session and simple caching
http_session = requests.Session()
http_session.verify = False # Maintain user's preference for disabling SSL verification
CACHE = {}
CACHE_TTL = 300 # 5 minutes
LAST_CACHE_PURGE = 0

def get_cached_api(url, headers, cache_key):
    global LAST_CACHE_PURGE, CACHE
    now = time.time()
    if now - LAST_CACHE_PURGE > 86400:
        CACHE = {}
        LAST_CACHE_PURGE = now
    if cache_key in CACHE:
        data, expiry = CACHE[cache_key]
        if now < expiry:
            return data
    
    try:
        r = http_session.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        CACHE[cache_key] = (data, now + CACHE_TTL)
        return data
    except Exception as e:
        print(f"DEBUG: API Error ({url}): {e}")
        # Return stale data if available on error
        if cache_key in CACHE:
            return CACHE[cache_key][0]
        return None

def auto_cleanup_script():
    return """
    <script>
    (function(){
      try{
        var key='nexus_last_clean';
        var now=Date.now();
        var last=parseInt(localStorage.getItem(key)||'0',10);
        if(!last || (now-last)>86400000){
          localStorage.clear();
          sessionStorage.clear();
          var parts=document.cookie.split(';');
          for(var i=0;i<parts.length;i++){
            var name=parts[i].split('=')[0].trim();
            if(name){
              document.cookie=name+'=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
            }
          }
          localStorage.setItem(key,String(now));
        }
      }catch(e){}
    })();
    </script>
    """
def get_user_guilds(access_token):
    key = hashlib.sha256(access_token.encode()).hexdigest()[:16]
    cache_key = f"user_guilds_{key}"
    now = time.time()
    if cache_key in CACHE:
        data, expiry = CACHE[cache_key]
        if now < expiry:
            return data
    headers = {'Authorization': f"Bearer {access_token}"}
    url = f"{DISCORD_API_BASE_URL}/users/@me/guilds"
    try:
        r = http_session.get(url, headers=headers, timeout=10)
        if r.status_code == 429:
            retry_after = r.headers.get('Retry-After')
            try:
                wait_s = min(3, int(float(retry_after))) if retry_after else 1
            except:
                wait_s = 1
            time.sleep(wait_s)
            r = http_session.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Shorter TTL for user guilds
        CACHE[cache_key] = (data, now + 120)
        return data
    except Exception as e:
        print(f"DEBUG: User guilds fetch error: {e}")
        if cache_key in CACHE:
            return CACHE[cache_key][0]
        return None

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    # Ensure WAL mode is active for this connection
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def init_db():
    conn = get_db()
    # Ensure tables exist
    conn.execute('''CREATE TABLE IF NOT EXISTS global_votes (
        user_id INTEGER PRIMARY KEY, last_vote INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS guild_wonder (
        guild_id INTEGER PRIMARY KEY,
        level INTEGER DEFAULT 0,
        progress INTEGER DEFAULT 0,
        goal INTEGER DEFAULT 50000,
        boost_multiplier REAL DEFAULT 1.25,
        boost_until INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        prefix TEXT DEFAULT '.',
        role_shop_json TEXT DEFAULT '{}',
        custom_assets_json TEXT DEFAULT '{}',
        bank_plans_json TEXT DEFAULT '{}'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS welcome_farewell (
        guild_id INTEGER PRIMARY KEY,
        welcome_channel TEXT,
        welcome_message TEXT,
        farewell_channel TEXT,
        farewell_message TEXT,
        welcome_embed_json TEXT,
        farewell_embed_json TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS automod_words (
        word_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        word TEXT,
        punishment TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS logging_config (
        guild_id INTEGER PRIMARY KEY,
        message_log_channel TEXT,
        member_log_channel TEXT,
        mod_log_channel TEXT,
        automod_log_channel TEXT,
        server_log_channel TEXT,
        voice_log_channel TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS custom_commands (
        guild_id INTEGER,
        name TEXT,
        prefix TEXT DEFAULT '!',
        PRIMARY KEY (guild_id, name)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS mod_stats (
        user_id INTEGER,
        guild_id INTEGER,
        messages INTEGER DEFAULT 0,
        warns INTEGER DEFAULT 0,
        bans INTEGER DEFAULT 0,
        kicks INTEGER DEFAULT 0,
        timeouts INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )''')
    
    # Ensure new columns exist
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN bank_plans_json TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass # Already exists
    try:
        conn.execute("ALTER TABLE welcome_farewell ADD COLUMN welcome_embed_json TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE welcome_farewell ADD COLUMN farewell_embed_json TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE logging_config ADD COLUMN join_log_channel TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE logging_config ADD COLUMN leave_log_channel TEXT")
    except sqlite3.OperationalError:
        pass
    # New guild_config columns
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN raid_mode INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN anti_phish_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN marketplace_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN marketplace_tax INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN vassal_max_percent INTEGER DEFAULT 15")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN alliances_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    # Moderation points config
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_message_point INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_warn_point INTEGER DEFAULT 5")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_kick_point INTEGER DEFAULT 10")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_ban_point INTEGER DEFAULT 15")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_timeout_point INTEGER DEFAULT 4")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE guild_config ADD COLUMN mod_promo_threshold INTEGER DEFAULT 500")
    except sqlite3.OperationalError:
        pass
    # Promotion system tables
    conn.execute('''CREATE TABLE IF NOT EXISTS promo_config (
        guild_id INTEGER PRIMARY KEY,
        tier_trial_role_id INTEGER,
        tier_mod_role_id INTEGER,
        tier_head_mod_role_id INTEGER,
        tier_admin_role_id INTEGER,
        tier_head_admin_role_id INTEGER,
        threshold_trial_to_mod INTEGER DEFAULT 10,
        threshold_mod_to_head_mod INTEGER DEFAULT 100,
        threshold_head_mod_to_admin INTEGER DEFAULT 250,
        threshold_admin_to_head_admin INTEGER DEFAULT 500,
        allow_demotions INTEGER DEFAULT 1,
        deduction_enabled INTEGER DEFAULT 1,
        deduction_invalid_warn INTEGER DEFAULT 2,
        deduction_reversed_kick INTEGER DEFAULT 5,
        deduction_reversed_ban INTEGER DEFAULT 10,
        deduction_abuse_report INTEGER DEFAULT 20,
        check_interval_sec INTEGER DEFAULT 60
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS mod_points_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        delta INTEGER,
        reason TEXT,
        source TEXT,
        created_at INTEGER
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS promo_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        action TEXT,
        from_role_id INTEGER,
        to_role_id INTEGER,
        points_at_action INTEGER,
        note TEXT,
        created_at INTEGER
    )''')

    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

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

# Enormous UI upgrade: refined theme, responsive layout, modern cards
STYLE = """
<style>
    :root{
        --bg-dark:#0a0b10;
        --bg-sidebar:#12131a;
        --bg-card:#161826;
        --bg-card-2:#1a1d2e;
        --accent:#00d2ff;
        --accent-2:#91eae4;
        --text-main:#e9eef6;
        --text-muted:#8a8fa3;
        --border:#23273a;
        --danger:#ff4757;
        --success:#2ecc71;
        --warning:#f1c40f;
        --purple:#7d5fff;
    }
    *{box-sizing:border-box}
    body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:radial-gradient(1000px 500px at 10% -10%,rgba(14,19,39,.6),transparent),var(--bg-dark);color:var(--text-main);margin:0;display:flex;height:100vh;overflow:hidden}
    .sidebar{width:280px;background:linear-gradient(180deg,var(--bg-sidebar),#0d0e14);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:20px 0;flex-shrink:0;backdrop-filter:saturate(140%) blur(8px)}
    .sidebar-header{padding:0 25px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
    .logo{font-size:20px;font-weight:900;background:linear-gradient(90deg,var(--accent),var(--accent-2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-decoration:none;letter-spacing:2px;text-transform:uppercase}
    .sidebar-menu{flex-grow:1}
    .menu-item{padding:12px 25px;display:flex;align-items:center;color:var(--text-muted);text-decoration:none;font-weight:700;transition:.2s;border-left:3px solid transparent}
    .menu-item:hover{background:rgba(0,210,255,.06);color:#fff}
    .menu-item.active{background:linear-gradient(90deg,rgba(0,210,255,.12),rgba(145,234,228,.08));color:var(--accent);border-left-color:var(--accent)}
    .menu-label{margin-left:12px;font-size:14px;text-transform:uppercase;letter-spacing:1px}

    .main-content{flex-grow:1;overflow-y:auto;padding:40px}
    .container{max-width:1200px;margin:0 auto}
    .page-title{font-size:30px;font-weight:900;margin-bottom:10px;letter-spacing:1px}
    .page-desc{color:var(--text-muted);margin-bottom:24px}

    .card{background:linear-gradient(180deg,var(--bg-card),var(--bg-card-2));border:1px solid var(--border);border-radius:14px;padding:24px;margin-bottom:24px;box-shadow:0 18px 40px rgba(8,10,20,.35)}
    .card-title{font-size:18px;font-weight:900;margin:0 0 14px 0;color:var(--accent);text-transform:uppercase;letter-spacing:1px}

    .stat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:16px}
    .stat-item{background:#0e111b;border:1px solid var(--border);border-radius:12px;padding:14px 16px}
    .stat-label{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--text-muted);margin-bottom:6px}
    .stat-value{font-size:18px;font-weight:800;color:var(--text-main)}
    .progress-track{width:100%;height:12px;background:#0b0b10;border-radius:999px;border:1px solid var(--border);overflow:hidden}
    .progress-fill{height:100%;background:linear-gradient(90deg,#00d2ff,#91eae4)}

    .form-group{margin-bottom:18px}
    label{display:block;font-weight:700;color:var(--text-muted);text-transform:uppercase;font-size:12px;margin-bottom:8px}
    input,select,textarea{width:100%;padding:12px;background:#0e111b;border:1px solid var(--border);border-radius:10px;color:#e9eef6;font-family:inherit;font-size:14px}
    input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 10px rgba(0,210,255,.12)}
    textarea{min-height:110px}

    .btn{background:linear-gradient(90deg,var(--accent),var(--accent-2));color:#091015;padding:12px 18px;border-radius:12px;border:none;font-weight:900;cursor:pointer;text-decoration:none;display:inline-block;transition:.25s;text-transform:uppercase;font-size:14px;letter-spacing:1px;box-shadow:0 6px 20px rgba(0,210,255,.18)}
    .btn:hover{filter:brightness(1.06);transform:translateY(-1px)}

    .list-item{display:flex;align-items:center;justify-content:space-between;background:#121523;padding:15px 18px;border-radius:12px;border:1px solid var(--border);margin-bottom:10px}
    .list-item-info{flex-grow:1}
    .list-item-name{font-weight:800;font-size:15px}
    .list-item-price{color:var(--accent);font-size:13px;font-weight:700}
    .btn-delete{color:#fff;background:#252a3b;border:none;cursor:pointer;font-size:14px;padding:8px 12px;border-radius:10px}
    .btn-delete:hover{background:#ff4757}

    .modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);backdrop-filter:blur(6px);z-index:1000;align-items:center;justify-content:center}
    .modal-content{background:linear-gradient(180deg,var(--bg-card),var(--bg-card-2));width:520px;padding:24px;border-radius:16px;border:1px solid var(--border)}
    .modal-actions{display:flex;gap:10px;margin-top:18px}

    .navbar{position:fixed;top:0;left:0;right:0;height:60px;background:rgba(0,0,0,.4);border-bottom:1px solid var(--border);backdrop-filter:blur(6px);display:flex;align-items:center;padding:0 25px}
    .badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;font-size:11px;text-transform:uppercase;letter-spacing:.6px;font-weight:800;background:rgba(0,210,255,.12);color:var(--accent);border:1px solid rgba(0,210,255,.3)}
    .toast{background:#1f2335;color:#fff;padding:14px;border-radius:10px;border:1px solid var(--border);box-shadow:0 10px 30px rgba(0,0,0,.35);animation:slideIn .5s}

    @keyframes slideIn{from{transform:translateY(-6px);opacity:0}to{transform:translateY(0);opacity:1}}

    ::-webkit-scrollbar{width:10px}
    ::-webkit-scrollbar-thumb{background:#23273a;border-radius:10px}
</style>
"""

def get_bot_guilds():
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    guilds = get_cached_api(f"{DISCORD_API_BASE_URL}/users/@me/guilds", headers, "bot_guilds")
    if guilds is None: return []
    return [g['id'] for g in guilds]

def get_server_roles(guild_id):
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    roles = get_cached_api(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/roles", headers, f"roles_{guild_id}")
    if roles is None: return None
    return sorted(roles, key=lambda x: x['position'], reverse=True)

def get_server_channels(guild_id):
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    channels = get_cached_api(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels", headers, f"channels_{guild_id}")
    if channels is None: return []
    # Filter for text channels (type 0)
    return [ch for ch in channels if ch['type'] == 0]

def get_server_emojis(guild_id):
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    emojis = get_cached_api(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/emojis", headers, f"emojis_{guild_id}")
    if emojis is None: return []
    return emojis

def get_bot_user_id():
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}"}
    data = get_cached_api(f"{DISCORD_API_BASE_URL}/users/@me", headers, "bot_user")
    if not data: return None
    return str(data['id'])
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
        {auto_cleanup_script()}
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
        guilds = get_user_guilds(session['access_token'])
        if guilds is None:
            return "Please wait a moment and refresh; Discord rate limit reached.", 429
        
        bot_guilds = get_bot_guilds()
    except Exception as e:
        print(f"DEBUG: Servers error: {str(e)}")
        return f"Failed to fetch servers: {str(e)}", 500
    
    manageable = [
        g for g in guilds 
        if ((int(g['permissions']) & 0x20) == 0x20) or ((int(g['permissions']) & 0x8) == 0x8)
    ]
    
    server_cards = ""
    for g in manageable:
        is_bot_in = g['id'] in bot_guilds
        icon_url = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g['icon'] else "https://discord.com/assets/1f0ac53a65725674052e731c4708805.png"
        
        if is_bot_in:
            action_btn = f'<a href="/dashboard/{g["id"]}" class="btn" style="width: 100%; box-sizing: border-box; text-align: center;">Configure</a>'
            status_tag = '<span style="color: #2ecc71; font-size: 10px; font-weight: 800; text-transform: uppercase;">● Active</span>'
        else:
            # Use the precise permission bitmask (2416299008) requested by the user
            invite_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands&guild_id={g['id']}&disable_guild_select=true"
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
            {auto_cleanup_script()}
        </head>
        <body style="display: block; overflow-y: auto;">
            <div class="sidebar">
                <div class="sidebar-header">
                    <a href="/" class="logo">Empire Nexus</a>
                </div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item active"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/how-to-use" class="menu-item"><span class="menu-label">📘 How To Use</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
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

@app.route('/how-to-use')
def how_to_use():
    if 'access_token' not in session:
        return redirect('/')
    html = f"""
    <html>
        <head>
            <title>Empire Nexus | How To Use</title>
            {STYLE}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
            {auto_cleanup_script()}
        </head>
        <body style="display: block; overflow-y: auto;">
            <div class="sidebar">
                <div class="sidebar-header">
                    <a href="/" class="logo">Empire Nexus</a>
                </div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/how-to-use" class="menu-item active"><span class="menu-label">📘 How To Use</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container" style="max-width: 1100px;">
                    <h1 class="page-title">📘 How To Use Empire Nexus</h1>
                    <p class="page-desc">Quick guides and examples for economy, moderation, promotion, and security.</p>
                    
                    <div class="card">
                        <h2 class="card-title">Getting Started</h2>
                        <div class="stat-grid">
                            <div class="stat-item"><div class="stat-label">Invite</div><div class="stat-value">Use “Invite Bot” in the sidebar</div></div>
                            <div class="stat-item"><div class="stat-label">Prefix</div><div class="stat-value">/showprefix • /setprefix</div></div>
                            <div class="stat-item"><div class="stat-label">Help</div><div class="stat-value">/help_nexus • categorized help UI</div></div>
                        </div>
                        <div class="list-item"><div class="list-item-info"><div class="list-item-name">Economy Basics</div><div class="list-item-price">work, crime, rob, blackjack, shop, buy, inventory, profile</div></div><a href="/servers" class="btn">Open Servers</a></div>
                    </div>

                    <div class="card">
                        <h2 class="card-title">Moderation & Promotion</h2>
                        <div class="stat-grid">
                            <div class="stat-item"><div class="stat-label">Staff Roles</div><div class="stat-value">/modsystem</div></div>
                            <div class="stat-item"><div class="stat-label">Points</div><div class="stat-value">/mod profile • /mod lb</div></div>
                            <div class="stat-item"><div class="stat-label">Promotion</div><div class="stat-value">Configure in Promotion page</div></div>
                        </div>
                        <p class="page-desc">Map roles and thresholds on the Promotion System page; enable deductions and set values.</p>
                    </div>

                    <div class="card">
                        <h2 class="card-title">Abuse Reporting</h2>
                        <p class="page-desc">Members can file a report; admins confirm or deny and points adjust automatically.</p>
                        <div class="list-item">
                            <div class="list-item-info">
                                <div class="list-item-name">Report</div>
                                <div class="list-item-price">/reportabuse accused:@User reason:\"details\" evidence:\"link (optional)\"</div>
                            </div>
                            <button class="btn" disabled>Command</button>
                        </div>
                        <div class="list-item">
                            <div class="list-item-info">
                                <div class="list-item-name">Resolve</div>
                                <div class="list-item-price">/resolveabuse report_id:123 decision:confirm|deny</div>
                            </div>
                            <button class="btn" disabled>Admin</button>
                        </div>
                        <p class="page-desc">Deduction uses “Abuse Report Confirmed” from Promotion settings.</p>
                    </div>

                    <div class="card">
                        <h2 class="card-title">Security</h2>
                        <div class="stat-grid">
                            <div class="stat-item"><div class="stat-label">Raid Mode</div><div class="stat-value">/raidmode on|off</div></div>
                            <div class="stat-item"><div class="stat-label">Anti‑Phishing</div><div class="stat-value">/antiphish on|off</div></div>
                            <div class="stat-item"><div class="stat-label">Logs</div><div class="stat-value">Set channels in Logging page</div></div>
                        </div>
                    </div>

                    <div class="card">
                        <h2 class="card-title">Sync & Troubleshooting</h2>
                        <div class="list-item"><div class="list-item-info"><div class="list-item-name">Force Sync</div><div class="list-item-price">/sync • /syncall</div></div><button class="btn" disabled>Admin</button></div>
                        <div class="list-item"><div class="list-item-info"><div class="list-item-name">Diagnostics</div><div class="list-item-price">/diagnose — shows global/local command counts and current prefix</div></div><button class="btn" disabled>Admin</button></div>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
    return html
@app.route('/dashboard/<int:guild_id>')
def dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    
    conn = get_db()
    config = conn.execute('SELECT * FROM guild_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    wonder = conn.execute('SELECT * FROM guild_wonder WHERE guild_id = ?', (int(guild_id),)).fetchone()
    if not wonder:
        conn.execute('INSERT INTO guild_wonder (guild_id) VALUES (?)', (int(guild_id),))
        conn.commit()
        wonder = conn.execute('SELECT * FROM guild_wonder WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()
    
    prefix = config['prefix'] if config else '!'
    try:
        role_shop = json.loads(config['role_shop_json']) if config and config['role_shop_json'] else {}
    except Exception:
        role_shop = {}
    try:
        custom_assets = json.loads(config['custom_assets_json']) if config and config['custom_assets_json'] else {}
    except Exception:
        custom_assets = {}
    try:
        bank_plans = json.loads(config['bank_plans_json']) if config and config['bank_plans_json'] else {}
    except Exception:
        bank_plans = {}
    wonder_level = wonder['level']
    wonder_progress = wonder['progress']
    wonder_goal = wonder['goal']
    wonder_boost_multiplier = wonder['boost_multiplier']
    wonder_boost_until = wonder['boost_until']
    now = int(time.time())
    wonder_progress_pct = int((wonder_progress / wonder_goal) * 100) if wonder_goal else 0
    if wonder_boost_until > now:
        remaining = wonder_boost_until - now
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        wonder_boost_status = f"Active • {wonder_boost_multiplier:.2f}x • {hours}h {minutes}m left"
    else:
        wonder_boost_status = "Inactive"
    wonder_next_multiplier = min(2.0, 1.25 + ((wonder_level + 1) * 0.05))
    
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
        role_name = next((r['name'] for r in roles if r['id'] == r_id), f"Unknown Role ({r_id})") if roles else f"Unknown Role ({r_id})"
        role_items_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{role_name}</div>
                <div class="list-item-price">{price:,} coins</div>
            </div>
            <div style="display: flex; gap: 6px;">
                <button onclick="editItem('role', '{r_id}')" class="btn-delete" style="background: #2980b9;">✎</button>
                <button onclick="deleteItem('role', '{r_id}')" class="btn-delete">×</button>
            </div>
        </div>
        """
        
    # Pre-render Assets list
    asset_items_html = ""
    
    from bot import DEFAULT_ASSETS
    display_assets = {**DEFAULT_ASSETS, **custom_assets}

    bank_items_html = ""
    if not bank_plans:
        from bot import DEFAULT_BANK_PLANS
        bank_plans = DEFAULT_BANK_PLANS
    for b_id, data in bank_plans.items():
        rate_min = float(data.get("min", 0.01)) * 100
        rate_max = float(data.get("max", 0.02)) * 100
        bank_items_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{data.get('name', b_id)}</div>
                <div class="list-item-price">{rate_min:.2f}%–{rate_max:.2f}%/h • Cost: {int(data.get('price', 0)):,} • Min Lvl: {int(data.get('min_level', 0))}</div>
            </div>
            <div style="display: flex; gap: 6px;">
                <button onclick="editItem('bank', '{b_id}')" class="btn-delete" style="background: #2980b9;">✎</button>
                <button onclick="deleteItem('bank', '{b_id}')" class="btn-delete">×</button>
            </div>
        </div>
        """

    for a_id, data in display_assets.items():
        asset_items_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{data['name']}</div>
                <div class="list-item-price">{data['price']:,} coins • {data['income']:,}/10min</div>
            </div>
            <div style="display: flex; gap: 6px;">
                <button onclick="editItem('asset', '{a_id}')" class="btn-delete" style="background: #2980b9;">✎</button>
                <button onclick="deleteItem('asset', '{a_id}')" class="btn-delete">×</button>
            </div>
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
                    <a href="/dashboard/{guild_id}" class="menu-item {'active' if request.path == f'/dashboard/{guild_id}' else ''}"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item {'active' if '/welcome' in request.path else ''}"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/moderation" class="menu-item {'active' if '/moderation' in request.path else ''}"><span class="menu-label">🛡️ Moderation</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item {'active' if '/security' in request.path else ''}"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item {'active' if '/systems' in request.path else ''}"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item {'active' if '/promotion' in request.path else ''}"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item {'active' if '/logging' in request.path else ''}"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item {'active' if '/custom-commands' in request.path else ''}"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
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

                        <div class="card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
                                <h2 class="card-title" style="margin: 0;">Bank Plans</h2>
                                <button type="button" onclick="openModal('bankModal')" class="btn" style="padding: 8px 16px; font-size: 12px;">+ Add Plan</button>
                            </div>
                            <div id="bankList">{bank_items_html}</div>
                            <input type="hidden" name="bank_plans" id="bankPlansInput" value='{json.dumps(bank_plans)}'>
                        </div>

                        <div class="card">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
                                <h2 class="card-title" style="margin: 0;">Wonder Project</h2>
                                <span class="badge">{wonder_boost_status}</span>
                            </div>
                            <div class="stat-grid">
                                <div class="stat-item">
                                    <div class="stat-label">Wonder Level</div>
                                    <div class="stat-value">{wonder_level}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Progress</div>
                                    <div class="stat-value">{wonder_progress:,} / {wonder_goal:,}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Next Boost</div>
                                    <div class="stat-value">{wonder_next_multiplier:.2f}x</div>
                                </div>
                            </div>
                            <div class="progress-track">
                                <div class="progress-fill" style="width: {wonder_progress_pct}%;"></div>
                            </div>
                            <div class="hint">Players can fund the Wonder with /contribute &lt;amount&gt; to unlock a server-wide income boost for 6 hours.</div>
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
                    <h2 class="card-title" id="roleModalTitle">Add Role to Shop</h2>
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
                    <h2 class="card-title" id="assetModalTitle">Create New Asset</h2>
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

            <div id="bankModal" class="modal">
                <div class="modal-content">
                    <h2 class="card-title" id="bankModalTitle">Create Bank Plan</h2>
                    <div class="form-group">
                        <label>Plan ID</label>
                        <input type="text" id="modalBankId" placeholder="e.g. royal_vault">
                    </div>
                    <div class="form-group">
                        <label>Display Name</label>
                        <input type="text" id="modalBankName" placeholder="e.g. Royal Vault">
                    </div>
                    <div class="form-group">
                        <label>Min Interest %/h</label>
                        <input type="number" id="modalBankMin" value="1">
                    </div>
                    <div class="form-group">
                        <label>Max Interest %/h</label>
                        <input type="number" id="modalBankMax" value="2">
                    </div>
                    <div class="form-group">
                        <label>Price</label>
                        <input type="number" id="modalBankPrice" value="0">
                    </div>
                    <div class="form-group">
                        <label>Minimum Level</label>
                        <input type="number" id="modalBankMinLevel" value="0">
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="addBank()" class="btn" style="flex: 1;">Save</button>
                        <button onclick="closeModal('bankModal')" class="btn btn-secondary" style="flex: 1; background: #25252b; color: #fff;">Cancel</button>
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
                let bankPlans = {json.dumps(bank_plans)};
                let editingRoleId = null;
                let editingAssetId = null;
                let editingBankId = null;
                
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
                    if(!id || isNaN(price) || price <= 0) return;
                    roleShop[id] = price;
                    editingRoleId = null;
                    updateUI(true);
                }}

                function addAsset() {{
                    const name = document.getElementById('modalAssetName').value;
                    const price = parseInt(document.getElementById('modalAssetPrice').value);
                    const income = parseInt(document.getElementById('modalAssetIncome').value);
                    if(!name || isNaN(price) || price <= 0 || isNaN(income) || income < 0) return;
                    const maxIncome = price * 20;
                    if(income > maxIncome) {{
                        alert('Income cannot be more than price × 20.');
                        return;
                    }}
                    let id = editingAssetId;
                    if(!id) id = name.toLowerCase().replace(/\\s+/g, '_');
                    combinedAssets[id] = {{ name, price, income }};
                    editingAssetId = null;
                    updateUI(true);
                }}

                function deleteItem(type, id) {{
                    if(type === 'role') delete roleShop[id];
                    else if(type === 'asset') delete combinedAssets[id];
                    else if(type === 'bank') delete bankPlans[id];
                    updateUI(true);
                }}

                function addBank() {{
                    const rawId = document.getElementById('modalBankId').value.toLowerCase().replace(/\\s+/g, '_');
                    const name = document.getElementById('modalBankName').value;
                    const minPercent = parseFloat(document.getElementById('modalBankMin').value);
                    const maxPercent = parseFloat(document.getElementById('modalBankMax').value);
                    const price = parseInt(document.getElementById('modalBankPrice').value);
                    const minLevel = parseInt(document.getElementById('modalBankMinLevel').value);
                    if(!rawId || !name || isNaN(minPercent) || isNaN(maxPercent) || minPercent <= 0 || maxPercent <= 0 || maxPercent < minPercent || isNaN(price) || price < 0 || isNaN(minLevel) || minLevel < 0) {{
                        alert('Invalid bank plan values.');
                        return;
                    }}
                    const steps = Math.floor(price / 50000);
                    const allowedMinPct = 1 + steps * 1;
                    const allowedMaxPct = 2 + steps * 2;
                    if(minPercent > allowedMinPct || maxPercent > allowedMaxPct) {{
                        alert("For this price, max allowed interest is " + allowedMinPct.toFixed(2) + "% min / " + allowedMaxPct.toFixed(2) + "% max.");
                        return;
                    }}
                    const min = minPercent / 100.0;
                    const max = maxPercent / 100.0;
                    let id = editingBankId || rawId;
                    bankPlans[id] = {{ name, min, max, price, min_level: minLevel }};
                    editingBankId = null;
                    updateUI(true);
                }}

                function editItem(type, id) {{
                    if(type === 'role') {{
                        editingRoleId = id;
                        const select = document.getElementById('modalRoleSelect');
                        const priceInput = document.getElementById('modalRolePrice');
                        document.getElementById('roleModalTitle').textContent = 'Edit Role in Shop';
                        if(select) select.value = id;
                        if(priceInput) priceInput.value = roleShop[id] || 0;
                        openModal('roleModal');
                    }} else if(type === 'asset') {{
                        editingAssetId = id;
                        const data = combinedAssets[id];
                        if(!data) return;
                        document.getElementById('assetModalTitle').textContent = 'Edit Asset';
                        document.getElementById('modalAssetName').value = data.name;
                        document.getElementById('modalAssetPrice').value = data.price;
                        document.getElementById('modalAssetIncome').value = data.income;
                        openModal('assetModal');
                    }} else if(type === 'bank') {{
                        editingBankId = id;
                        const data = bankPlans[id];
                        if(!data) return;
                        document.getElementById('bankModalTitle').textContent = 'Edit Bank Plan';
                        document.getElementById('modalBankId').value = id;
                        document.getElementById('modalBankName').value = data.name || id;
                        document.getElementById('modalBankMin').value = (parseFloat(data.min || 0.01) * 100).toFixed(2);
                        document.getElementById('modalBankMax').value = (parseFloat(data.max || 0.02) * 100).toFixed(2);
                        document.getElementById('modalBankPrice').value = data.price || 0;
                        document.getElementById('modalBankMinLevel').value = data.min_level || 0;
                        openModal('bankModal');
                    }}
                }}

                function updateUI(submit = false) {{
                    document.getElementById('roleShopInput').value = JSON.stringify(roleShop);
                    
                    // We only want to save assets that are DIFFERENT from defaults or new
                    // But for simplicity, we save the entire combined list to the custom field
                    // so that deletions of defaults actually persist.
                    document.getElementById('assetsInput').value = JSON.stringify(combinedAssets);
                    document.getElementById('bankPlansInput').value = JSON.stringify(bankPlans);
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
    bank_plans = request.form.get('bank_plans')
    
    try:
        json.loads(role_shop)
        json.loads(custom_assets)
        json.loads(bank_plans)
    except:
        return "Invalid JSON format! Go back and fix it.", 400

    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO guild_config (guild_id, prefix, role_shop_json, custom_assets_json, bank_plans_json) VALUES (?, ?, ?, ?, ?)', 
                 (int(guild_id), prefix, role_shop, custom_assets, bank_plans))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}?success=1')

@app.route('/dashboard/<int:guild_id>/moderation')
def moderation_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    conn = get_db()
    automod_words = conn.execute('SELECT * FROM automod_words WHERE guild_id = ?', (int(guild_id),)).fetchall()
    conn.close()

    roles = get_server_roles(guild_id)
    channels = get_server_channels(guild_id)
    if roles is None or channels is None: return redirect('/servers')

    channel_options = '<option value="">Select a channel...</option>'
    for ch in channels:
        channel_options += f'<option value="{ch["id"]}">{ch["name"]}</option>'

    def get_selected_channel_options(selected_id):
        opts = '<option value="">None</option>'
        for ch in channels:
            sel = 'selected' if str(ch['id']) == str(selected_id) else ''
            opts += f'<option value="{ch["id"]}" {sel}>#{ch["name"]}</option>'
        return opts

    automod_html = ""
    for word_row in automod_words:
        automod_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{word_row['word']}</div>
                <div class="list-item-price">Punishment: {word_row['punishment']}</div>
            </div>
            <button onclick="location.href='/delete-automod/{guild_id}/{word_row['word_id']}'" class="btn-delete">×</button>
        </div>
        """

    return f"""
    <html>
        <head><title>Moderation | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/moderation" class="menu-item active"><span class="menu-label">🛡️ Moderation</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">🛡️ Moderation & AutoMod</h1>
                    <p class="page-desc">Protect your kingdom with automated filters and moderation tools.</p>
                    
                    <div class="card">
                        <h2 class="card-title">AutoMod Filter</h2>
                        <form action="/add-automod/{guild_id}" method="post">
                            <div style="display: flex; gap: 15px;">
                                <div style="flex: 2;">
                                    <label>Forbidden Word/Phrase</label>
                                    <input type="text" name="word" placeholder="e.g. badword" required>
                                </div>
                                <div style="flex: 1;">
                                    <label>Punishment</label>
                                    <select name="punishment">
                                        <option value="delete">Delete Only</option>
                                        <option value="warn">Warn & Delete</option>
                                        <option value="kick">Kick User</option>
                                        <option value="ban">Ban User</option>
                                    </select>
                                </div>
                                <div style="display: flex; align-items: flex-end;">
                                    <button type="submit" class="btn">Add Rule</button>
                                </div>
                            </div>
                        </form>
                        <div style="margin-top: 25px;">
                            <h3 style="font-size: 14px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 15px;">Active Rules</h3>
                            {automod_html}
                        </div>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/dashboard/<int:guild_id>/welcome')
def welcome_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    conn = get_db()
    cfg = conn.execute('SELECT * FROM welcome_farewell WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()

    channels = get_server_channels(guild_id)
    emojis = get_server_emojis(guild_id)
    if channels is None: return redirect('/servers')

    def get_selected_channel_options(selected_id):
        opts = '<option value="">None</option>'
        for ch in channels:
            sel = 'selected' if str(ch['id']) == str(selected_id) else ''
            opts += f'<option value="{ch["id"]}" {sel}>#{ch["name"]}</option>'
        return opts

    farewell_msg = (cfg['farewell_message'] if cfg and cfg['farewell_message'] else '{user} just left the server.')
    welcome_json = (cfg['welcome_embed_json'] if cfg and cfg['welcome_embed_json'] else '{ "title": "👋 Welcome {username}", "description": "Glad to have you in {server}!", "color": 11849216, "thumbnail": {"url": "{avatar}"} }')
    farewell_json = (cfg['farewell_embed_json'] if cfg and cfg['farewell_embed_json'] else '{ "title": "📤 Goodbye {username}", "description": "We hope to see you again in {server}.", "color": 15158332 }')
    try:
        wobj = json.loads(welcome_json)
    except Exception:
        wobj = {"title": "👋 Welcome {username}", "description": "Glad to have you in {server}!", "color": 11849216, "thumbnail": {"url": "{avatar}"}}
    w_title = wobj.get("title", "")
    w_desc = wobj.get("description", "")
    w_color = wobj.get("color", 11849216)
    w_footer = (wobj.get("footer", {}) or {}).get("text", "")
    try:
        fobj = json.loads(farewell_json)
    except Exception:
        fobj = {"title": "📤 Goodbye {username}", "description": "We hope to see you again in {server}.", "color": 15158332}
    f_title = fobj.get("title", "")
    f_desc = fobj.get("description", "")
    f_color = fobj.get("color", 15158332)
    f_footer = (fobj.get("footer", {}) or {}).get("text", "")

    channel_select_options = ''.join([f'<option value="{c["name"]}">#{c["name"]}</option>' for c in channels])
    emoji_select_options = ''.join([f'<option value="{e["name"]}">:{e["name"]}:</option>' for e in emojis])

    return f"""
    <html>
        <head><title>Welcome & Farewell | {guild_id}</title>{STYLE}
            <style>
                .embed {{ background:#0b1220; border-radius:8px; padding:12px; position:relative; }}
                .embed::before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--embed-color,#00d2ff); border-radius:8px 0 0 8px; }}
                .embed-title {{ font-weight:700; margin-bottom:6px; color:#e5e7eb; }}
                .embed-desc {{ white-space:pre-wrap; color:#cbd5e1; }}
                .embed-footer {{ margin-top:8px; font-size:12px; color:#9ca3af; }}
                .mention-chip {{ display:inline-block; padding:2px 8px; border-radius:6px; background:#2f3136; color:#b9bbbe; border:1px solid #5865F2; }}
                .emoji-img {{ height:1em; width:1em; vertical-align:-0.15em; }}
                .embed-thumb {{ position:absolute; right:12px; top:12px; width:40px; height:40px; border-radius:50%; background:#111827; overflow:hidden; }}
                .embed-thumb img {{ width:40px; height:40px; object-fit:cover; }}
            </style>
        </head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item active"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/moderation" class="menu-item"><span class="menu-label">🛡️ Moderation</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">👋 Welcome & Farewell</h1>
                    <p class="page-desc">Configure messages with live preview. Template variables: {{user}}, {{username}}, {{server}}, {{member_count}}, {{join_date}}, {{avatar}}</p>
                    <form action="/save-welcome/{guild_id}" method="post">
                        <div class="card">
                            <h2 class="card-title">Welcome Settings</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Welcome Channel</label>
                                    <select name="welcome_channel">{get_selected_channel_options(cfg['welcome_channel'] if cfg else '')}</select>
                                </div>
                                <div class="form-group">
                                    <label>Embed Title</label>
                                    <input type="text" name="welcome_title" value="{w_title}" placeholder="e.g., 👋 Welcome {{username}}">
                                </div>
                                <div class="form-group">
                                    <label>Embed Description</label>
                                    <textarea name="welcome_description" rows="4">{w_desc}</textarea>
                                </div>
                                <div class="form-group">
                                    <label>Embed Color</label>
                                    <input type="text" name="welcome_color" value="{('#%06x' % int(w_color))}" placeholder="#00d2ff">
                                    <div class="hint">Use hex (e.g. #00d2ff). Avatar thumbnail is shown automatically.</div>
                                </div>
                                <div class="form-group">
                                    <label>Footer Text</label>
                                    <input type="text" name="welcome_footer" value="{w_footer}" placeholder="e.g., Enjoy your stay!">
                                </div>
                            </div>
                            <div id="welcomePreview" class="preview"></div>
                            <div class="toolbar">
                                <button type="button" class="btn" onclick="insertVar('welcome_description','{{user}}')">@user</button>
                                <button type="button" class="btn" onclick="insertVar('welcome_description','{{server}}')">server</button>
                                <button type="button" class="btn" onclick="wrapSelection('welcome_description','**')">Bold</button>
                                <button type="button" class="btn" onclick="wrapSelection('welcome_description','*')">Italic</button>
                                <select id="channelPick" style="margin-left:10px;">
                                    <option value="">Insert channel…</option>
                                    {channel_select_options}
                                </select>
                                <button type="button" class="btn" onclick="insertPickedChannel('welcome_description')">Insert</button>
                                <select id="emojiPick" style="margin-left:10px;">
                                    <option value="">Insert emoji…</option>
                                    {emoji_select_options}
                                </select>
                                <button type="button" class="btn" onclick="insertPickedEmoji('welcome_description')">Insert</button>
                            </div>
                            <div id="welcomeSuggest" style="margin-top:6px;"></div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Farewell Settings</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Farewell Channel</label>
                                    <select name="farewell_channel">{get_selected_channel_options(cfg['farewell_channel'] if cfg else '')}</select>
                                </div>
                                <div class="form-group">
                                    <label>Farewell Message (text)</label>
                                    <textarea name="farewell_message" rows="3">{farewell_msg}</textarea>
                                    <div class="hint">Placeholders: {{user}}, {{username}}, {{server}}</div>
                                </div>
                                <div class="form-group">
                                    <label>Embed Title</label>
                                    <input type="text" name="farewell_title" value="{f_title}" placeholder="📤 Goodbye {{username}}">
                                </div>
                                <div class="form-group">
                                    <label>Embed Description</label>
                                    <textarea name="farewell_description" rows="4">{f_desc}</textarea>
                                </div>
                                <div class="form-group">
                                    <label>Embed Color</label>
                                    <input type="text" name="farewell_color" value="{('#%06x' % int(f_color))}" placeholder="#ff4757">
                                </div>
                                <div class="form-group">
                                    <label>Footer Text</label>
                                    <input type="text" name="farewell_footer" value="{f_footer}" placeholder="e.g., Safe travels!">
                                </div>
                            </div>
                            <div id="farewellPreview" class="preview"></div>
                            <div class="toolbar">
                                <button type="button" class="btn" onclick="insertVar('farewell_description','{{user}}')">@user</button>
                                <button type="button" class="btn" onclick="insertVar('farewell_description','{{server}}')">server</button>
                                <button type="button" class="btn" onclick="wrapSelection('farewell_description','**')">Bold</button>
                                <button type="button" class="btn" onclick="wrapSelection('farewell_description','*')">Italic</button>
                                <select id="channelPick2" style="margin-left:10px;">
                                    <option value="">Insert channel…</option>
                                    {channel_select_options}
                                </select>
                                <button type="button" class="btn" onclick="insertPickedChannel('farewell_description', true)">Insert</button>
                                <select id="emojiPick2" style="margin-left:10px;">
                                    <option value="">Insert emoji…</option>
                                    {emoji_select_options}
                                </select>
                                <button type="button" class="btn" onclick="insertPickedEmoji('farewell_description', true)">Insert</button>
                            </div>
                            <div id="farewellSuggest" style="margin-top:6px;"></div>
                        </div>
                        <button type="submit" class="btn">Save Welcome/Farewell</button>
                    </form>
                    <script>
                        const channelsData = {json.dumps([{'name': c['name']} for c in channels])};
                        const emojisData = {json.dumps([{'name': e['name'], 'id': e['id'], 'animated': bool(e.get('animated'))} for e in emojis])};
                        function hexToInt(hex) {{
                            try {{ return parseInt(hex.replace('#',''), 16); }} catch(e) {{ return 0x00d2ff; }}
                        }}
                        function substitute(str) {{
                            const sample = {{
                                '{{user}}': '@ExampleUser',
                                '{{username}}': 'ExampleUser',
                                '{{server}}': 'ExampleServer',
                                '{{member_count}}': '1234',
                                '{{join_date}}': 'Jan 01, 2026',
                                '{{avatar}}': 'https://cdn.example/avatar.png'
                            }};
                            for (const k in sample) str = str.replaceAll(k, sample[k]);
                            try {{
                                // Allow optional spaces after '#' to mimic Discord typing
                                str = str.replace(/#\\s*([A-Za-z0-9_\\-]+)/g, function(m, p) {{
                                    const c = channelsData.find(x => x.name === p);
                                    return c ? '<span class=\"mention-chip\"># ' + p + '</span>' : m;
                                }});
                                str = str.replace(/:([A-Za-z0-9_\\-]+):/g, function(m, p) {{
                                    const e = emojisData.find(x => x.name === p);
                                    if (!e) return m;
                                    const ext = e.animated ? 'gif' : 'png';
                                    const url = 'https://cdn.discordapp.com/emojis/' + e.id + '.' + ext + '?size=24&quality=lossless';
                                    return '<img class=\"emoji-img\" src=\"' + url + '\" alt=\":' + p + ':\" />';
                                }});
                            }} catch(e) {{}}
                            return str;
                        }}
                        function renderPreview(prefix) {{
                            const title = document.querySelector('input[name=\"' + prefix + '_title\"]').value;
                            const desc = document.querySelector('textarea[name=\"' + prefix + '_description\"]').value;
                            const color = document.querySelector('input[name=\"' + prefix + '_color\"]').value;
                            const footer = document.querySelector('input[name=\"' + prefix + '_footer\"]').value;
                            const thumb = '<div class=\"embed-thumb\"><img src=\"' + substitute('{{avatar}}') + '\" /></div>';
                            const html = '<div class=\"embed\" style=\"--embed-color:' + color + ';\">' +
                                         thumb +
                                         '<div class=\"embed-title\">' + substitute(title) + '</div>' +
                                         '<div class=\"embed-desc\">' + substitute(desc) + '</div>' +
                                         (footer ? '<div class=\"embed-footer\">' + substitute(footer) + '</div>' : '') +
                                         '</div>';
                            document.getElementById(prefix+'Preview').innerHTML = html;
                        }}
                        function insertVar(field, token) {{
                            const el = document.querySelector('textarea[name=\"' + field + '\"]');
                            const start = el.selectionStart, end = el.selectionEnd;
                            el.value = el.value.slice(0,start) + token + el.value.slice(end);
                            el.dispatchEvent(new Event('input'));
                        }}
                        function wrapSelection(field, marker) {{
                            const el = document.querySelector('textarea[name=\"' + field + '\"]');
                            const start = el.selectionStart, end = el.selectionEnd;
                            const sel = el.value.slice(start,end);
                            el.value = el.value.slice(0,start) + marker + sel + marker + el.value.slice(end);
                            el.dispatchEvent(new Event('input'));
                        }}
                        function insertPickedChannel(field, second) {{
                            const sel = document.getElementById(second ? 'channelPick2' : 'channelPick');
                            const name = sel.value;
                            if (!name) return;
                            insertVar(field, '#' + name);
                            sel.selectedIndex = 0;
                        }}
                        function insertPickedEmoji(field, second) {{
                            const sel = document.getElementById(second ? 'emojiPick2' : 'emojiPick');
                            const name = sel.value;
                            if (!name) return;
                            insertVar(field, ':' + name + ':');
                            sel.selectedIndex = 0;
                        }}
                        function showSuggest(containerId, items, type, insertCb) {{
                            const box = document.getElementById(containerId);
                            if (!items.length) {{ box.innerHTML = ''; return; }}
                            let html = '<div style=\"background:#111827;border:1px solid #1f2937;border-radius:6px;padding:6px;display:inline-block;max-width:100%;\">';
                            items.slice(0,8).forEach(function(it) {{
                                const label = type === 'channel' ? ('#' + it.name) : (':' + it.name + ':');
                                html += '<button type=\"button\" style=\"margin:3px;padding:4px 8px;background:#1f2937;color:#e5e7eb;border:0;border-radius:4px;cursor:pointer;\" data-name=\"' + it.name + '\">' + label + '</button>';
                            }});
                            html += '</div>';
                            box.innerHTML = html;
                            box.querySelectorAll('button').forEach(function(btn) {{
                                btn.addEventListener('click', function() {{
                                    insertCb(btn.getAttribute('data-name'));
                                    box.innerHTML = '';
                                }});
                            }});
                        }}
                        function caretToken(el) {{
                            const val = el.value;
                            const pos = el.selectionStart;
                            const hash = val.lastIndexOf('#', pos-1);
                            const colon = val.lastIndexOf(':', pos-1);
                            let type = null, start = -1;
                            if (hash >= 0 && (pos - hash) <= 32) {{ type = 'channel'; start = hash; }}
                            if (colon >= 0 && (pos - colon) <= 32) {{ type = 'emoji'; start = colon; }}
                            if (type === null) return null;
                            const end = pos;
                            const raw = val.slice(start, end);
                            // Trim leading space after '#' and any trailing ':' while typing emojis
                            const name = raw.replace(/^#\\s*/, '').replace(/^:/,'').replace(/:$/,'').trim();
                            return {{ type, name }};
                        }}
                        function attachSuggest(field, containerId) {{
                            const el = document.querySelector('textarea[name=\"' + field + '\"]');
                            let currentList = [], currentType = null, selected = 0;
                            function updateList() {{
                                const tok = caretToken(el);
                                if (!tok) {{ document.getElementById(containerId).innerHTML=''; currentList=[]; return; }}
                                currentType = tok.type;
                                if (tok.type === 'channel') {{
                                    const q = (tok.name || '').toLowerCase();
                                    currentList = (q ? channelsData.filter(x => x.name.toLowerCase().startsWith(q)) : channelsData.slice(0, 12));
                                    showSuggest(containerId, currentList, 'channel', function(name) {{ insertVar(field, '#' + name); }});
                                }} else {{
                                    const q = (tok.name || '').toLowerCase();
                                    currentList = (q ? emojisData.filter(x => x.name.toLowerCase().startsWith(q)) : emojisData.slice(0, 12));
                                    showSuggest(containerId, currentList, 'emoji', function(name) {{ insertVar(field, ':' + name + ':'); }});
                                }}
                                selected = 0;
                            }}
                            el.addEventListener('input', function() {{ updateList(); }});
                            el.addEventListener('keydown', function(ev) {{
                                if (!currentList.length) return;
                                if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {{
                                    ev.preventDefault();
                                    selected = Math.max(0, Math.min(currentList.length-1, selected + (ev.key==='ArrowDown'?1:-1)));
                                }} else if (ev.key === 'Enter') {{
                                    ev.preventDefault();
                                    const name = currentList[selected].name;
                                    if (currentType === 'channel') insertVar(field, '#' + name);
                                    else insertVar(field, ':' + name + ':');
                                    document.getElementById(containerId).innerHTML='';
                                    currentList = [];
                                }}
                            }});
                        }}
                        ['welcome','farewell'].forEach(function(p) {{
                            document.querySelectorAll('[name^=\"' + p + '_\"]').forEach(function(el) {{
                                el.addEventListener('input', function() {{ renderPreview(p); }});
                            }});
                            renderPreview(p);
                        }});
                        attachSuggest('welcome_description', 'welcomeSuggest');
                        attachSuggest('farewell_description', 'farewellSuggest');
                    </script>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/save-welcome/<int:guild_id>', methods=['POST'])
def save_welcome(guild_id):
    welcome_channel = request.form.get('welcome_channel')
    w_title = request.form.get('welcome_title', '👋 Welcome {username}')
    w_desc = request.form.get('welcome_description', 'Glad to have you in {server}!')
    w_color_hex = request.form.get('welcome_color', '#00d2ff').lstrip('#')
    try:
        w_color_int = int(w_color_hex, 16)
    except Exception:
        w_color_int = 0x00d2ff
    w_footer = request.form.get('welcome_footer', '')
    welcome_embed = {
        "title": w_title,
        "description": w_desc,
        "color": w_color_int,
        "thumbnail": {"url": "{avatar}"},
    }
    if w_footer:
        welcome_embed["footer"] = {"text": w_footer}
    welcome_embed_json = json.dumps(welcome_embed)
    farewell_channel = request.form.get('farewell_channel')
    farewell_message = request.form.get('farewell_message')
    f_title = request.form.get('farewell_title', '📤 Goodbye {username}')
    f_desc = request.form.get('farewell_description', 'We hope to see you again in {server}.')
    f_color_hex = request.form.get('farewell_color', '#ff4757').lstrip('#')
    try:
        f_color_int = int(f_color_hex, 16)
    except Exception:
        f_color_int = 0xff4757
    f_footer = request.form.get('farewell_footer', '')
    farewell_embed = {
        "title": f_title,
        "description": f_desc,
        "color": f_color_int
    }
    if f_footer:
        farewell_embed["footer"] = {"text": f_footer}
    farewell_embed_json = json.dumps(farewell_embed)

    conn = get_db()
    conn.execute('''
        INSERT INTO welcome_farewell (guild_id, welcome_channel, welcome_message, farewell_channel, farewell_message, welcome_embed_json, farewell_embed_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            welcome_channel = excluded.welcome_channel,
            welcome_message = excluded.welcome_message,
            farewell_channel = excluded.farewell_channel,
            farewell_message = excluded.farewell_message,
            welcome_embed_json = excluded.welcome_embed_json,
            farewell_embed_json = excluded.farewell_embed_json
    ''', (int(guild_id), welcome_channel, "", farewell_channel, farewell_message, welcome_embed_json, farewell_embed_json))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/welcome?success=1')

@app.route('/dashboard/<int:guild_id>/logging')
def logging_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    conn = get_db()
    log_config = conn.execute('SELECT * FROM logging_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()

    channels = get_server_channels(guild_id)
    if channels is None: return redirect('/servers')

    def get_selected_channel_options(selected_id):
        opts = '<option value="">None</option>'
        for ch in channels:
            sel = 'selected' if str(ch['id']) == str(selected_id) else ''
            opts += f'<option value="{ch["id"]}" {sel}>#{ch["name"]}</option>'
        return opts

    return f"""
    <html>
        <head><title>Logging | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item active"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">📝 Logging Configuration</h1>
                    <p class="page-desc">Configure granular logging channels for various server events.</p>
                    <form action="/save-logging/{guild_id}" method="post">
                        <div class="card">
                            <h2 class="card-title">Log Channels</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Message Logs</label>
                                    <select name="message_log">
                                        {get_selected_channel_options(log_config['message_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Member Logs</label>
                                    <select name="member_log">
                                        {get_selected_channel_options(log_config['member_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Mod Logs</label>
                                    <select name="mod_log">
                                        {get_selected_channel_options(log_config['mod_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>AutoMod Logs</label>
                                    <select name="automod_log">
                                        {get_selected_channel_options(log_config['automod_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Server Logs</label>
                                    <select name="server_log">
                                        {get_selected_channel_options(log_config['server_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Voice Logs</label>
                                    <select name="voice_log">
                                        {get_selected_channel_options(log_config['voice_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Join Logs</label>
                                    <select name="join_log">
                                        {get_selected_channel_options(log_config['join_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Leave Logs</label>
                                    <select name="leave_log">
                                        {get_selected_channel_options(log_config['leave_log_channel'] if log_config else '')}
                                    </select>
                                </div>
                            </div>
                        </div>
                        <button type="submit" class="btn">Save Logging</button>
                    </form>
                    <form action="/setup-logging/{guild_id}" method="post" style="display:inline-block; margin-top: 15px;">
                        <button type="submit" class="btn">Setup Private Log Channels</button>
                    </form>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/dashboard/<int:guild_id>/security')
def security_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    conn = get_db()
    cfg = conn.execute('SELECT raid_mode, anti_phish_enabled FROM guild_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()
    raid_mode = int(cfg['raid_mode'] if cfg and cfg['raid_mode'] is not None else 0)
    anti_phish = int(cfg['anti_phish_enabled'] if cfg and cfg['anti_phish_enabled'] is not None else 1)
    return f"""
    <html>
        <head><title>Security | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item active"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">🛡️ Security</h1>
                    <p class="page-desc">Toggle raid mode and anti‑phishing filters.</p>
                    <form action="/save-security/{guild_id}" method="post">
                        <div class="card">
                            <h2 class="card-title">Protection</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Raid Mode</label>
                                    <select name="raid_mode">
                                        <option value="0" {"selected" if raid_mode==0 else ""}>Off</option>
                                        <option value="1" {"selected" if raid_mode==1 else ""}>On</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Anti‑Phishing</label>
                                    <select name="anti_phish">
                                        <option value="0" {"selected" if anti_phish==0 else ""}>Off</option>
                                        <option value="1" {"selected" if anti_phish==1 else ""}>On</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        <button type="submit" class="btn">Save Security</button>
                    </form>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/dashboard/<int:guild_id>/promotion')
def promotion_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    conn = get_db()
    cfg = conn.execute('SELECT * FROM promo_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    top_mods = conn.execute('SELECT user_id, points FROM mod_stats WHERE guild_id = ? ORDER BY points DESC LIMIT 10', (int(guild_id),)).fetchall()
    conn.close()
    roles = get_server_roles(guild_id) or []
    def role_options(selected_id):
        opts = '<option value="">None</option>'
        for r in roles:
            sel = 'selected' if str(r['id']) == str(selected_id) else ''
            opts += f'<option value="{r["id"]}" {sel}>{r["name"]}</option>'
        return opts
    def val(key, default):
        if not cfg:
            return default
        try:
            v = cfg[key]
        except Exception:
            return default
        return int(v) if v is not None else default
    trial = val('tier_trial_role_id', '')
    mod = val('tier_mod_role_id', '')
    head_mod = val('tier_head_mod_role_id', '')
    admin = val('tier_admin_role_id', '')
    head_admin = val('tier_head_admin_role_id', '')
    th_t2m = val('threshold_trial_to_mod', 10)
    th_m2hm = val('threshold_mod_to_head_mod', 100)
    th_hm2a = val('threshold_head_mod_to_admin', 250)
    th_a2ha = val('threshold_admin_to_head_admin', 500)
    allow_demotions = val('allow_demotions', 1)
    deduction_enabled = val('deduction_enabled', 1)
    ded_warn = val('deduction_invalid_warn', 2)
    ded_kick = val('deduction_reversed_kick', 5)
    ded_ban = val('deduction_reversed_ban', 10)
    ded_abuse = val('deduction_abuse_report', 20)
    interval = val('check_interval_sec', 60)
    top_list_html = ""
    next_threshold = th_t2m
    for row in top_mods:
        pts = int(row['points'] or 0)
        pct = 100 if next_threshold == 0 else min(100, int(pts * 100 / next_threshold))
        top_list_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">@{row['user_id']}</div>
                <div class="list-item-price">{pts} points</div>
            </div>
            <div class="progress-track"><div class="progress-fill" style="width:{pct}%;"></div></div>
        </div>"""
    return f"""
    <html>
        <head><title>Promotion System | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/moderation" class="menu-item"><span class="menu-label">🛡️ Moderation</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item active"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">📈 Auto‑Promotion System</h1>
                    <p class="page-desc">Configure role mappings, thresholds, and deduction rules.</p>
                    <form action="/save-promotion/{guild_id}" method="post">
                        <div class="card">
                            <h2 class="card-title">Role Mapping</h2>
                            <div class="stat-grid">
                                <div class="form-group"><label>Trial Mod</label><select name="tier_trial_role_id">{role_options(trial)}</select></div>
                                <div class="form-group"><label>Mod</label><select name="tier_mod_role_id">{role_options(mod)}</select></div>
                                <div class="form-group"><label>Head Mod</label><select name="tier_head_mod_role_id">{role_options(head_mod)}</select></div>
                                <div class="form-group"><label>Admin</label><select name="tier_admin_role_id">{role_options(admin)}</select></div>
                                <div class="form-group"><label>Head Admin</label><select name="tier_head_admin_role_id">{role_options(head_admin)}</select></div>
                            </div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Promotion Thresholds</h2>
                            <div class="stat-grid">
                                <div class="form-group"><label>Trial → Mod</label><input type="number" name="threshold_trial_to_mod" min="1" value="{th_t2m}"></div>
                                <div class="form-group"><label>Mod → Head Mod</label><input type="number" name="threshold_mod_to_head_mod" min="1" value="{th_m2hm}"></div>
                                <div class="form-group"><label>Head Mod → Admin</label><input type="number" name="threshold_head_mod_to_admin" min="1" value="{th_hm2a}"></div>
                                <div class="form-group"><label>Admin → Head Admin</label><input type="number" name="threshold_admin_to_head_admin" min="1" value="{th_a2ha}"></div>
                                <div class="form-group"><label>Check Interval (sec)</label><input type="number" name="check_interval_sec" min="30" max="600" value="{interval}"></div>
                                <div class="form-group"><label>Allow Demotions</label>
                                    <select name="allow_demotions"><option value="1" {'selected' if allow_demotions==1 else ''}>Yes</option><option value="0" {'selected' if allow_demotions==0 else ''}>No</option></select>
                                </div>
                            </div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Deduction Rules</h2>
                            <div class="stat-grid">
                                <div class="form-group"><label>Enable Deductions</label>
                                    <select name="deduction_enabled"><option value="1" {'selected' if deduction_enabled==1 else ''}>Yes</option><option value="0" {'selected' if deduction_enabled==0 else ''}>No</option></select>
                                </div>
                                <div class="form-group"><label>Invalid Warn</label><input type="number" name="deduction_invalid_warn" min="0" value="{ded_warn}"></div>
                                <div class="form-group"><label>Reversed Kick</label><input type="number" name="deduction_reversed_kick" min="0" value="{ded_kick}"></div>
                                <div class="form-group"><label>Reversed Ban</label><input type="number" name="deduction_reversed_ban" min="0" value="{ded_ban}"></div>
                                <div class="form-group"><label>Abuse Report Confirmed</label><input type="number" name="deduction_abuse_report" min="0" value="{ded_abuse}"></div>
                            </div>
                        </div>
                        <button type="submit" class="btn">Save Promotion Settings</button>
                    </form>
                    <div class="card" style="margin-top:20px;">
                        <h2 class="card-title">Top Moderators</h2>
                        <div id="topMods">{top_list_html or '<div class=\"hint\">No moderator points yet.</div>'}</div>
                    </div>
                    <div style="display:flex; gap:10px; margin-top:10px;">
                        <form action="/adjust-points/{guild_id}" method="post" style="display:flex; gap:10px;">
                            <input type="number" name="user_id" placeholder="User ID" required>
                            <input type="number" name="delta" placeholder="+/- Points" required>
                            <input type="text" name="reason" placeholder="Reason" required>
                            <button type="submit" class="btn">Adjust Points</button>
                        </form>
                        <form action="/reset-points/{guild_id}" method="post" style="display:flex; gap:10px;">
                            <input type="number" name="user_id" placeholder="User ID" required>
                            <button type="submit" class="btn" style="background:#EF4444;">Reset Points</button>
                        </form>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/save-promotion/<int:guild_id>', methods=['POST'])
def save_promotion(guild_id):
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    fields = [
        'tier_trial_role_id','tier_mod_role_id','tier_head_mod_role_id','tier_admin_role_id','tier_head_admin_role_id',
        'threshold_trial_to_mod','threshold_mod_to_head_mod','threshold_head_mod_to_admin','threshold_admin_to_head_admin',
        'allow_demotions','deduction_enabled','deduction_invalid_warn','deduction_reversed_kick','deduction_reversed_ban','deduction_abuse_report','check_interval_sec'
    ]
    data = {}
    for f in fields:
        v = request.form.get(f, None)
        if v is None: continue
        if f.startswith('tier_'):
            data[f] = int(v) if v else None
        else:
            data[f] = int(v)
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO promo_config (guild_id) VALUES (?)', (int(guild_id),))
    sets = ', '.join([f"{k} = ?" for k in data.keys()])
    vals = list(data.values()) + [int(guild_id)]
    conn.execute(f'UPDATE promo_config SET {sets} WHERE guild_id = ?', vals)
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/promotion?success=1')

@app.route('/adjust-points/<int:guild_id>', methods=['POST'])
def adjust_points(guild_id):
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    user_id = int(request.form.get('user_id'))
    delta = int(request.form.get('delta'))
    reason = request.form.get('reason','Manual adjust')
    now = int(time.time())
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO mod_stats (user_id, guild_id, messages, warns, bans, kicks, timeouts, points) VALUES (?, ?, 0, 0, 0, 0, 0, 0)', (user_id, int(guild_id)))
    conn.execute('UPDATE mod_stats SET points = points + ? WHERE user_id = ? AND guild_id = ?', (delta, user_id, int(guild_id)))
    conn.execute('INSERT INTO mod_points_history (guild_id, user_id, delta, reason, source, created_at) VALUES (?, ?, ?, ?, ?, ?)', (int(guild_id), user_id, delta, reason, 'dashboard', now))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/promotion?success=1')

@app.route('/reset-points/<int:guild_id>', methods=['POST'])
def reset_points(guild_id):
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    user_id = int(request.form.get('user_id'))
    now = int(time.time())
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO mod_stats (user_id, guild_id, messages, warns, bans, kicks, timeouts, points) VALUES (?, ?, 0, 0, 0, 0, 0, 0)', (user_id, int(guild_id)))
    # Read current points for audit trail
    cur = conn.execute('SELECT points FROM mod_stats WHERE user_id = ? AND guild_id = ?', (user_id, int(guild_id))).fetchone()
    old_pts = int(cur['points'] if cur and cur['points'] is not None else 0)
    conn.execute('UPDATE mod_stats SET points = 0 WHERE user_id = ? AND guild_id = ?', (user_id, int(guild_id)))
    conn.execute('INSERT INTO mod_points_history (guild_id, user_id, delta, reason, source, created_at) VALUES (?, ?, ?, ?, ?, ?)', (int(guild_id), user_id, -old_pts, 'Reset to zero', 'dashboard', now))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/promotion?success=1')
@app.route('/save-security/<int:guild_id>', methods=['POST'])
def save_security(guild_id):
    raid_mode = int(request.form.get('raid_mode', '0'))
    anti_phish = int(request.form.get('anti_phish', '1'))
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)', (int(guild_id),))
    conn.execute('UPDATE guild_config SET raid_mode = ?, anti_phish_enabled = ? WHERE guild_id = ?', (raid_mode, anti_phish, int(guild_id)))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/security?success=1')

@app.route('/dashboard/<int:guild_id>/systems')
def systems_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    try:
        if int(guild_id) != 1465437620245889237:
            return redirect('/servers')
    except:
        return redirect('/servers')
    conn = get_db()
    cfg = conn.execute('SELECT marketplace_enabled, marketplace_tax, vassal_max_percent, alliances_enabled, mod_message_point, mod_warn_point, mod_kick_point, mod_ban_point, mod_timeout_point, mod_promo_threshold FROM guild_config WHERE guild_id = ?', (int(guild_id),)).fetchone()
    conn.close()
    marketplace_enabled = int(cfg['marketplace_enabled'] if cfg and cfg['marketplace_enabled'] is not None else 1)
    marketplace_tax = int(cfg['marketplace_tax'] if cfg and cfg['marketplace_tax'] is not None else 0)
    vassal_max_percent = int(cfg['vassal_max_percent'] if cfg and cfg['vassal_max_percent'] is not None else 15)
    alliances_enabled = int(cfg['alliances_enabled'] if cfg and cfg['alliances_enabled'] is not None else 1)
    mod_message_point = int(cfg['mod_message_point'] if cfg and cfg['mod_message_point'] is not None else 1)
    mod_warn_point = int(cfg['mod_warn_point'] if cfg and cfg['mod_warn_point'] is not None else 5)
    mod_kick_point = int(cfg['mod_kick_point'] if cfg and cfg['mod_kick_point'] is not None else 10)
    mod_ban_point = int(cfg['mod_ban_point'] if cfg and cfg['mod_ban_point'] is not None else 15)
    mod_timeout_point = int(cfg['mod_timeout_point'] if cfg and cfg['mod_timeout_point'] is not None else 4)
    mod_promo_threshold = int(cfg['mod_promo_threshold'] if cfg and cfg['mod_promo_threshold'] is not None else 500)
    return f"""
    <html>
        <head><title>Systems | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item active"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">🏗️ Systems</h1>
                    <p class="page-desc">Configure marketplace, vassals, and alliances.</p>
                    <form action="/save-systems/{guild_id}" method="post">
                        <div class="card">
                            <h2 class="card-title">Marketplace</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Enabled</label>
                                    <select name="marketplace_enabled">
                                        <option value="1" {"selected" if marketplace_enabled==1 else ""}>On</option>
                                        <option value="0" {"selected" if marketplace_enabled==0 else ""}>Off</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Tax (%)</label>
                                    <input type="number" name="marketplace_tax" min="0" max="25" value="{marketplace_tax}">
                                </div>
                            </div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Vassals</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Max Percent</label>
                                    <input type="number" name="vassal_max_percent" min="1" max="25" value="{vassal_max_percent}">
                                </div>
                            </div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Alliances</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Enabled</label>
                                    <select name="alliances_enabled">
                                        <option value="1" {"selected" if alliances_enabled==1 else ""}>On</option>
                                        <option value="0" {"selected" if alliances_enabled==0 else ""}>Off</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        <div class="card">
                            <h2 class="card-title">Moderation Points & Promotions</h2>
                            <div class="stat-grid">
                                <div class="form-group">
                                    <label>Message Point</label>
                                    <input type="number" name="mod_message_point" min="0" max="10" value="{mod_message_point}">
                                </div>
                                <div class="form-group">
                                    <label>Warn Point</label>
                                    <input type="number" name="mod_warn_point" min="0" max="50" value="{mod_warn_point}">
                                </div>
                                <div class="form-group">
                                    <label>Kick Point</label>
                                    <input type="number" name="mod_kick_point" min="0" max="100" value="{mod_kick_point}">
                                </div>
                                <div class="form-group">
                                    <label>Ban Point</label>
                                    <input type="number" name="mod_ban_point" min="0" max="150" value="{mod_ban_point}">
                                </div>
                                <div class="form-group">
                                    <label>Timeout Point</label>
                                    <input type="number" name="mod_timeout_point" min="0" max="50" value="{mod_timeout_point}">
                                </div>
                                <div class="form-group">
                                    <label>Promo Threshold (points)</label>
                                    <input type="number" name="mod_promo_threshold" min="0" max="10000" value="{mod_promo_threshold}">
                                </div>
                            </div>
                        </div>
                        <button type="submit" class="btn">Save Systems</button>
                    </form>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/save-systems/<int:guild_id>', methods=['POST'])
def save_systems(guild_id):
    marketplace_enabled = int(request.form.get('marketplace_enabled', '1'))
    marketplace_tax = int(request.form.get('marketplace_tax', '0'))
    vassal_max_percent = int(request.form.get('vassal_max_percent', '15'))
    alliances_enabled = int(request.form.get('alliances_enabled', '1'))
    mod_message_point = int(request.form.get('mod_message_point', '1'))
    mod_warn_point = int(request.form.get('mod_warn_point', '5'))
    mod_kick_point = int(request.form.get('mod_kick_point', '10'))
    mod_ban_point = int(request.form.get('mod_ban_point', '15'))
    mod_timeout_point = int(request.form.get('mod_timeout_point', '4'))
    mod_promo_threshold = int(request.form.get('mod_promo_threshold', '500'))
    marketplace_tax = max(0, min(25, marketplace_tax))
    vassal_max_percent = max(1, min(25, vassal_max_percent))
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)', (int(guild_id),))
    conn.execute('UPDATE guild_config SET marketplace_enabled = ?, marketplace_tax = ?, vassal_max_percent = ?, alliances_enabled = ?, mod_message_point = ?, mod_warn_point = ?, mod_kick_point = ?, mod_ban_point = ?, mod_timeout_point = ?, mod_promo_threshold = ? WHERE guild_id = ?', 
                 (marketplace_enabled, marketplace_tax, vassal_max_percent, alliances_enabled, mod_message_point, mod_warn_point, mod_kick_point, mod_ban_point, mod_timeout_point, mod_promo_threshold, int(guild_id)))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/systems?success=1')

 

 

 

@app.route('/dashboard/<int:guild_id>/custom-commands')
def custom_commands_dashboard(guild_id):
    if 'access_token' not in session: return redirect('/')
    conn = get_db()
    custom_cmds = conn.execute('SELECT * FROM custom_commands WHERE guild_id = ?', (int(guild_id),)).fetchall()
    conn.close()

    cmds_html = ""
    for cmd in custom_cmds:
        cmds_html += f"""
        <div class="list-item">
            <div class="list-item-info">
                <div class="list-item-name">{cmd['name']}</div>
                <div class="list-item-price">Prefix: {cmd['prefix']}</div>
            </div>
            <button onclick="location.href='/delete-custom-command/{guild_id}/{cmd['name']}'" class="btn-delete">×</button>
        </div>
        """

    return f"""
    <html>
        <head><title>Custom Commands | {guild_id}</title>{STYLE}</head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header"><a href="/" class="logo">Empire Nexus</a></div>
                <div class="sidebar-menu">
                    <a href="/servers" class="menu-item"><span class="menu-label">🏠 Kingdoms</span></a>
                    <a href="/dashboard/{guild_id}" class="menu-item"><span class="menu-label">⚙️ General</span></a>
                    <a href="/dashboard/{guild_id}/welcome" class="menu-item"><span class="menu-label">👋 Welcome</span></a>
                    <a href="/dashboard/{guild_id}/moderation" class="menu-item"><span class="menu-label">🛡️ Moderation</span></a>
                    <a href="/dashboard/{guild_id}/security" class="menu-item"><span class="menu-label">🛡️ Security</span></a>
                    <a href="/dashboard/{guild_id}/logging" class="menu-item"><span class="menu-label">📝 Logging</span></a>
                    <a href="/dashboard/{guild_id}/systems" class="menu-item"><span class="menu-label">🏗️ Systems</span></a>
                    <a href="/dashboard/{guild_id}/promotion" class="menu-item"><span class="menu-label">📈 Promotion System</span></a>
                    <a href="/dashboard/{guild_id}/custom-commands" class="menu-item active"><span class="menu-label">💻 Custom Commands</span></a>
                    <a href="https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions={INVITE_PERMISSIONS}&integration_type=0&scope=bot+applications.commands" target="_blank" class="menu-item"><span class="menu-label">➕ Invite Bot</span></a>
                    <a href="https://discord.gg/zsqWFX2gBV" target="_blank" class="menu-item"><span class="menu-label">🛠️ Support Server</span></a>
                    <a href="/logout" class="menu-item" style="margin-top: auto;"><span class="menu-label">🚪 Logout</span></a>
                </div>
            </div>
            <div class="main-content">
                <div class="container">
                    <h1 class="page-title">💻 Custom Commands</h1>
                    <p class="page-desc">Create server-specific commands with restricted Python execution.</p>
                    
                    <div class="card">
                        <h2 class="card-title">Create New Command</h2>
                        <form action="/save-custom-command/{guild_id}" method="post">
                            <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                                <div style="flex: 1;">
                                    <label>Name</label>
                                    <input type="text" name="name" placeholder="e.g. hello" required>
                                </div>
                                <div style="flex: 1;">
                                    <label>Prefix (optional)</label>
                                    <input type="text" name="prefix" placeholder="." value=".">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Python Code (Sandboxed)</label>
                                <textarea name="code" rows="10" placeholder="await message.channel.send('Hello!')" required style="font-family: monospace;"></textarea>
                            </div>
                            <button type="submit" class="btn">Create Command</button>
                        </form>
                    </div>

                    <div class="card" style="margin-top: 30px;">
                        <h2 class="card-title">Existing Commands</h2>
                        {cmds_html}
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/save-moderation/<int:guild_id>', methods=['POST'])
def save_moderation(guild_id):
    welcome_ch = request.form.get('welcome_channel')
    welcome_msg = request.form.get('welcome_message')
    farewell_ch = request.form.get('farewell_channel')
    farewell_msg = request.form.get('farewell_message')
    
    conn = get_db()
    conn.execute('''
        INSERT INTO welcome_farewell (guild_id, welcome_channel, welcome_message, farewell_channel, farewell_message)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            welcome_channel = excluded.welcome_channel,
            welcome_message = excluded.welcome_message,
            farewell_channel = excluded.farewell_channel,
            farewell_message = excluded.farewell_message
    ''', (guild_id, welcome_ch, welcome_msg, farewell_ch, farewell_msg))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/moderation?success=1')

@app.route('/add-automod/<int:guild_id>', methods=['POST'])
def add_automod(guild_id):
    word = request.form.get('word')
    punishment = request.form.get('punishment')
    conn = get_db()
    conn.execute('INSERT INTO automod_words (guild_id, word, punishment) VALUES (?, ?, ?)', (guild_id, word, punishment))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/moderation')

@app.route('/delete-automod/<int:guild_id>/<int:word_id>')
def delete_automod(guild_id, word_id):
    conn = get_db()
    conn.execute('DELETE FROM automod_words WHERE word_id = ? AND guild_id = ?', (word_id, guild_id))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/moderation')

@app.route('/save-logging/<int:guild_id>', methods=['POST'])
def save_logging(guild_id):
    msg_ch = request.form.get('message_log')
    mem_ch = request.form.get('member_log')
    mod_ch = request.form.get('mod_log')
    auto_ch = request.form.get('automod_log')
    srv_ch = request.form.get('server_log')
    v_ch = request.form.get('voice_log')
    join_ch = request.form.get('join_log')
    leave_ch = request.form.get('leave_log')

    conn = get_db()
    conn.execute('''
        INSERT INTO logging_config (guild_id, message_log_channel, member_log_channel, mod_log_channel, automod_log_channel, server_log_channel, voice_log_channel, join_log_channel, leave_log_channel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            message_log_channel = excluded.message_log_channel,
            member_log_channel = excluded.member_log_channel,
            mod_log_channel = excluded.mod_log_channel,
            automod_log_channel = excluded.automod_log_channel,
            server_log_channel = excluded.server_log_channel,
            voice_log_channel = excluded.voice_log_channel,
            join_log_channel = excluded.join_log_channel,
            leave_log_channel = excluded.leave_log_channel
    ''', (guild_id, msg_ch, mem_ch, mod_ch, auto_ch, srv_ch, v_ch, join_ch, leave_ch))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/logging?success=1')

@app.route('/setup-logging/<int:guild_id>', methods=['POST'])
def setup_logging(guild_id):
    if not DISCORD_TOKEN:
        return "Missing bot token", 500
    headers = {'Authorization': f"Bot {DISCORD_TOKEN}", 'Content-Type': 'application/json'}
    bot_id = get_bot_user_id()
    if bot_id is None:
        return "Unable to fetch bot user", 500
    try:
        r = http_session.get(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels", headers=headers, timeout=10)
        r.raise_for_status()
        all_channels = r.json()
    except Exception as e:
        return f"Failed to fetch channels: {str(e)}", 500
    category = None
    for c in all_channels:
        if str(c.get('type')) == '4' and str(c.get('name')).lower() in ['logs', 'empire-logs']:
            category = c
            break
    if not category:
        payload = {
            "name": "empire-logs",
            "type": 4,
            "permission_overwrites": [
                {"id": str(guild_id), "type": 0, "deny": str(1024)},
                {"id": str(bot_id), "type": 1, "allow": str(3072)}
            ]
        }
        cr = http_session.post(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels", headers=headers, json=payload, timeout=10)
        if cr.status_code >= 400:
            return f"Failed to create category: {cr.text}", 500
        category = cr.json()
    parent_id = str(category['id'])
    desired = {
        "message-logs": "message_log_channel",
        "member-logs": "member_log_channel",
        "mod-logs": "mod_log_channel",
        "automod-logs": "automod_log_channel",
        "server-logs": "server_log_channel",
        "voice-logs": "voice_log_channel",
        "join-logs": "join_log_channel",
        "leave-logs": "leave_log_channel"
    }
    created_ids = {}
    existing = {}
    for c in all_channels:
        if str(c.get('type')) == '0' and str(c.get('parent_id')) == parent_id:
            existing[c.get('name')] = c
    for name, col in desired.items():
        ch = existing.get(name)
        if not ch:
            payload = {"name": name, "type": 0, "parent_id": parent_id}
            pr = http_session.post(f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/channels", headers=headers, json=payload, timeout=10)
            if pr.status_code >= 400:
                return f"Failed to create {name}: {pr.text}", 500
            ch = pr.json()
        created_ids[col] = str(ch['id'])
    conn = get_db()
    conn.execute('''
        INSERT INTO logging_config (guild_id, message_log_channel, member_log_channel, mod_log_channel, automod_log_channel, server_log_channel, voice_log_channel, join_log_channel, leave_log_channel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            message_log_channel = excluded.message_log_channel,
            member_log_channel = excluded.member_log_channel,
            mod_log_channel = excluded.mod_log_channel,
            automod_log_channel = excluded.automod_log_channel,
            server_log_channel = excluded.server_log_channel,
            voice_log_channel = excluded.voice_log_channel,
            join_log_channel = excluded.join_log_channel,
            leave_log_channel = excluded.leave_log_channel
    ''', (int(guild_id),
          created_ids.get('message_log_channel'),
          created_ids.get('member_log_channel'),
          created_ids.get('mod_log_channel'),
          created_ids.get('automod_log_channel'),
          created_ids.get('server_log_channel'),
          created_ids.get('voice_log_channel'),
          created_ids.get('join_log_channel'),
          created_ids.get('leave_log_channel')))
    conn.commit()
    conn.close()
    CACHE.pop(f"channels_{guild_id}", None)
    return redirect(f'/dashboard/{guild_id}/logging?setup=1')
@app.route('/save-custom-command/<int:guild_id>', methods=['POST'])
def save_custom_command(guild_id):
    name = request.form.get('name')
    prefix = request.form.get('prefix', '.')
    code = request.form.get('code')

    conn = get_db()
    conn.execute('''
        INSERT INTO custom_commands (guild_id, name, prefix, code)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, name) DO UPDATE SET
            prefix = excluded.prefix,
            code = excluded.code
    ''', (guild_id, name, prefix, code))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/custom-commands?success=1')

@app.route('/delete-custom-command/<int:guild_id>/<name>')
def delete_custom_command(guild_id, name):
    conn = get_db()
    conn.execute('DELETE FROM custom_commands WHERE guild_id = ? AND name = ?', (guild_id, name))
    conn.commit()
    conn.close()
    return redirect(f'/dashboard/{guild_id}/custom-commands')

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
            # Log the first few chars of the expected secret for debugging without leaking it all
            expected_preview = (webhook_secret[:3] + "...") if webhook_secret else "None"
            got_preview = (auth_header[:3] + "...") if auth_header else "None"
            return f"Unauthorized - Secret mismatch (Expected: {expected_preview}, Got: {got_preview})", 401
    
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
        # Adding 25,000 coins as a voting reward
        conn.execute('UPDATE users SET last_vote = ?, balance = balance + 25000 WHERE user_id = ?', (now, user_id))
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

