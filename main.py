# 💖 Editado por Rami/RO IZ
# Parche para Render + discord.py sin audio
import sys
import types
sys.modules['audioop'] = types.ModuleType('audioop')  # evita error de audioop en Render
# Bot de Discord que busca enlaces de Google Drive en mensajes fijados y devuelve el estado de capítulos

import os
import discord
from discord.ext import commands
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import re
from flask import Flask
from threading import Thread

# --- Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Saku está despierta! 🌸"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

keep_alive()

# --- Variables desde Secrets ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(x.strip()) for x in os.getenv("GUILD_IDS", "").split(",") if x.strip()]

# --- Crear client_secret.json si no existe ---
if not os.path.exists("client_secret.json"):
    client_json = os.getenv("GOOGLE_CLIENT_JSON")
    if client_json:
        with open("client_secret.json", "w", encoding="utf-8") as f:
            f.write(client_json)

# --- Crear token.json si no existe ---
if not os.path.exists("token.json"):
    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(token_json)

# --- Configuración de bot ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

# --- Autenticación Google Drive ---
def authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# --- Funciones de Drive ---
def extract_drive_links(text):
    # Detecta enlaces válidos de Drive (carpetas y archivos)
    return re.findall(r"https?://drive\.google\.com/(?:file/d|drive/(?:u/\d+/)?folders)/[a-zA-Z0-9_-]+", text)

def extract_id(link):
    # Quita /u/X/ si existe y extrae ID
    clean_link = re.sub(r'/u/\d+/', '/', link)
    match = re.search(r"/(?:d|folders)/([a-zA-Z0-9_-]+)", clean_link)
    return match.group(1) if match else None

def folder_has_files(service, folder_id):
    """Verifica si una carpeta contiene al menos un archivo (no otra carpeta)."""
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
            fields="files(id)"
        ).execute()
        return len(results.get("files", [])) > 0
    except Exception:
        return False

def traverse_folder(service, folder_id):
    """Obtiene capítulos numerados solo si las carpetas tienen archivos dentro."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        items = service.files().list(q=query, fields="files(id,name,mimeType)").execute().get("files", [])
        caps = []
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder":
                # Solo agregar si la subcarpeta tiene archivos
                if folder_has_files(service, item["id"]):
                    nums = re.findall(r"\d+", item["name"])
                    if nums:
                        caps.append(int(nums[0]))
        return sorted(caps)
    except Exception:
        return None

def traverse_trad(service, folder_id):
    """Obtiene capítulos de traducciones basados en archivos sueltos dentro de la carpeta."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        items = service.files().list(q=query, fields="files(id,name,mimeType)").execute().get("files", [])
        caps = []
        for item in items:
            # Solo archivos (ignora carpetas)
            if item["mimeType"] == "application/vnd.google-apps.folder":
                continue
            nums = re.findall(r"\d+", item["name"])
            if nums:
                caps.append(int(nums[0]))
        return sorted(caps)
    except Exception:
        return None

def join_ranges(numbers):
    """Convierte [1,2,3,5,6] → '1 al 3 / 5 al 6'"""
    if not numbers:
        return "0"
    numbers = sorted(numbers)
    ranges = []
    start = prev = numbers[0]
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}" if start == prev else f"{start} al {prev}")
            start = prev = n
    ranges.append(f"{start}" if start == prev else f"{start} al {prev}")
    return " / ".join(ranges)

# --- Eventos ---
@bot.event
async def on_ready():
    print(f"✨ Saku está en línea como {bot.user}")
    if not GUILD_IDS:
        print("⚠️ No se han definido GUILD_IDS en las variables de entorno.")
    for guild in bot.guilds:
        if guild.id in GUILD_IDS:
            print(f"🪄 Conectado al servidor: {guild.name} ({guild.id})")

# --- Comando revisar ---
@bot.command()
async def revisar(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")

    await ctx.send("🔍 Buscando enlaces de Drive en los mensajes fijados...")

    creds = authenticate()
    service = build("drive", "v3", credentials=creds)
    pinned_messages = await ctx.channel.pins()
    results = []

    for msg in pinned_messages:
        links = extract_drive_links(msg.content)
        if not links:
            continue
        for link in links:
            folder_id = extract_id(link)
            if not folder_id:
                continue
            try:
                items = service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields="files(id,name,mimeType)"
                ).execute().get("files", [])

                raw_caps = trad_caps = clean_caps = type_caps = []

                for item in items:
                    if item["mimeType"] != "application/vnd.google-apps.folder":
                        continue
                    name_lower = item["name"].lower()
                    if "raw" in name_lower:
                        raw_caps = traverse_folder(service, item["id"])
                    elif "trad" in name_lower or "traducción" in name_lower:
                        trad_caps = traverse_trad(service, item["id"])
                    elif "clean" in name_lower or "limpieza" in name_lower:
                        clean_caps = traverse_folder(service, item["id"])
                    elif "type" in name_lower or "edición" in name_lower:
                        type_caps = traverse_folder(service, item["id"])

                raw_str = join_ranges(raw_caps) if raw_caps is not None else "sin acceso"
                trad_str = join_ranges(trad_caps) if trad_caps is not None else "sin acceso"
                clean_str = join_ranges(clean_caps) if clean_caps is not None else "sin acceso"
                type_str = join_ranges(type_caps) if type_caps is not None else "sin acceso"

                results.append(
                    f"📌 Documentos encontrados:\nRAW: {raw_str}\nTRAD: {trad_str}\nCLEAN: {clean_str}\nTYPE: {type_str}"
                )
            except Exception:
                results.append("📌 API sin acceso. Permita que **soulferre1995@gmail.com** acceda al enlace solicitado e intente nuevamente.")

    if results:
        await ctx.send(f"✅ Resultados:\n\n" + "\n\n".join(results))
    else:
        await ctx.send("⚠️ No se encontraron enlaces válidos de Google Drive en los mensajes fijados.")

# --- Ejecutar bot ---
if not getattr(sys.modules[__name__], "_bot_started", False):
    setattr(sys.modules[__name__], "_bot_started", True)
    bot.run(TOKEN)
