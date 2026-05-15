import os
import requests
import eventlet
from datetime import datetime
from flask import Flask, render_template, redirect, request, session, url_for, flash
from dotenv import load_dotenv
from pymongo import MongoClient

# Wichtig für Eventlet: Optimiert die Hintergrundprozesse
eventlet.monkey_patch()

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

app = Flask(__name__)
# Lädt den Secret Key aus der .env oder generiert einen zufälligen als Fallback
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24)) 

# ==========================================
# DISCORD OAUTH2 KONFIGURATION (aus .env)
# ==========================================
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID')

# Discord API Endpunkte
OAUTH_URL = 'https://discord.com/api/oauth2/authorize'
TOKEN_URL = 'https://discord.com/api/oauth2/token'
API_BASE_URL = 'https://discord.com/api/v10'

# ==========================================
# MONGODB KONFIGURATION (aus .env)
# ==========================================
MONGO_URI = os.getenv('MONGO_URI')
# Verbindung zur Datenbank herstellen
mongo_client = MongoClient(MONGO_URI)
# Wir erstellen/nutzen eine Datenbank namens "eifellog_db"
db = mongo_client['eifellog_db']
# Tabelle (Collection) für die Benutzer
users_collection = db['users']

# ==========================================
# EIFEL LOG ROLLEN IDs
# ==========================================
ROLE_FAHRER = '1473721587101339681'
ROLE_PROJEKTLEITUNG = '1473721587122438321'
ROLE_GESCHAEFTSLEITUNG = '1473721587122438322'
ROLE_FUHRPARKMANAGEMENT = '1473758338465398899'
ROLE_BUCHHALTUNG = '1473730533593845951'

# Alle Rollen, die den Hub betreten dürfen
ALLOWED_HUB_ROLES = [
    ROLE_FAHRER, 
    ROLE_PROJEKTLEITUNG, 
    ROLE_GESCHAEFTSLEITUNG, 
    ROLE_FUHRPARKMANAGEMENT, 
    ROLE_BUCHHALTUNG
]


# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')


# --- AUTHENTIFIZIERUNG ---

@app.route('/login')
def login():
    # Leitet den Nutzer zu Discord weiter. Wir fragen Profil ('identify') und Serverliste ('guilds') ab.
    auth_url = f"{OAUTH_URL}?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        flash("Login abgebrochen.", "error")
        return redirect(url_for('home'))

    # Code gegen ein Access Token eintauschen
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(TOKEN_URL, data=data, headers=headers)
    
    if r.status_code != 200:
        flash("Fehler bei der Discord-Kommunikation. Bitte Client ID/Secret prüfen.", "error")
        return redirect(url_for('home'))
        
    token = r.json()['access_token']
    auth_headers = {'Authorization': f'Bearer {token}'}

    # 1. Basis-Benutzerdaten holen (ID, Name, Profilbild)
    user_r = requests.get(f"{API_BASE_URL}/users/@me", headers=auth_headers)
    user_data = user_r.json()

    # 2. Server-spezifische Daten holen (Rollen des Nutzers auf dem Eifel LOG Server)
    member_r = requests.get(f"{API_BASE_URL}/users/@me/guilds/{DISCORD_GUILD_ID}/member", headers=auth_headers)
    
    if member_r.status_code == 404:
        flash("Du musst Mitglied auf dem Eifel LOG Discord Server sein!", "error")
        return redirect(url_for('home'))
        
    member_data = member_r.json()
    user_roles = member_data.get('roles', [])

    # 3. Datenbasis für MongoDB vorbereiten
    discord_id = user_data['id']
    username = user_data['username']
    avatar = user_data.get('avatar')

    # Dokument für die Datenbank erstellen
    db_user_data = {
        'discord_id': discord_id,
        'username': username,
        'avatar': avatar,
        'roles': user_roles,
        'last_login': datetime.utcnow()
    }

    # In MongoDB speichern oder aktualisieren (upsert=True bedeutet: Wenn er nicht existiert -> erstellen, sonst -> updaten)
    users_collection.update_one(
        {'discord_id': discord_id},
        {'$set': db_user_data},
        upsert=True
    )

    # 4. Session für den Browser speichern
    session['user'] = {
        'id': discord_id,
        'username': username,
        'avatar': avatar,
        'roles': user_roles
    }

    flash("Erfolgreich eingeloggt!", "success")
    return redirect(url_for('hub'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Erfolgreich abgemeldet.", "success")
    return redirect(url_for('home'))


# --- DRIVER HUB ---

@app.route('/hub')
def hub():
    # 1. Prüfen ob der Nutzer überhaupt eingeloggt ist
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user = session['user']
    user_roles = user.get('roles', [])
    
    # 2. Prüfen ob der Nutzer eine der erlaubten Rollen hat
    has_permission = any(role in user_roles for role in ALLOWED_HUB_ROLES)
    
    if not has_permission:
        flash("Zugriff verweigert! Du benötigst die Rolle 'Fahrer' oder eine Team-Rolle, um den Hub zu betreten.", "error")
        return redirect(url_for('home'))

    # Optional: Aktuelle Daten aus der DB laden (falls sich Ränge während der Session geändert haben)
    # db_user = users_collection.find_one({'discord_id': user['id']})

    # Wenn alles passt: Hub anzeigen und Nutzerdaten ans Template übergeben
    return render_template('hub.html', current_user=user)


if __name__ == '__main__':
    print("Starte Eifel LOG Server mit MongoDB und Eventlet auf Port 5005...")
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5005)), app) 