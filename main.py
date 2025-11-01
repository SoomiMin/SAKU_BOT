# 💖 Editado por Rami/RO IZ
import sys, types, os, discord, re
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

sys.modules['audioop'] = types.ModuleType('audioop')  # evita error en audioop

# --- Cargar .env ---
load_dotenv()

# --- Variables sensibles ---
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

# --- Configuración bot ---
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
    return re.findall(r"https?://drive\.google\.com/(?:file/d|drive/(?:u/\d+/)?folders)/[a-zA-Z0-9_-]+", text)

def extract_id(link):
    clean_link = re.sub(r'/u/\d+/', '/', link)
    match = re.search(r"/(?:d|folders)/([a-zA-Z0-9_-]+)", clean_link)
    return match.group(1) if match else None

def folder_has_files(service, folder_id):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
            fields="files(id)"
        ).execute()
        return len(results.get("files", [])) > 0
    except Exception:
        return False

def traverse_folder(service, folder_id):
    try:
        items = service.files().list(q=f"'{folder_id}' in parents and trashed=false",
                                     fields="files(id,name,mimeType)").execute().get("files", [])
        caps = []
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder" and folder_has_files(service, item["id"]):
                nums = re.findall(r"\d+", item["name"])
                if nums: caps.append(int(nums[0]))
        return sorted(caps)
    except Exception:
        return None

def traverse_trad(service, folder_id):
    try:
        items = service.files().list(q=f"'{folder_id}' in parents and trashed=false",
                                     fields="files(id,name,mimeType)").execute().get("files", [])
        caps = []
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder": continue
            nums = re.findall(r"\d+", item["name"])
            if nums: caps.append(int(nums[0]))
        return sorted(caps)
    except Exception:
        return None

def join_ranges(numbers):
    if not numbers: return "0"
    numbers = sorted(numbers)
    ranges = []
    start = prev = numbers[0]
    for n in numbers[1:]:
        if n == prev + 1: prev = n
        else:
            ranges.append(f"{start}" if start==prev else f"{start} al {prev}")
            start = prev = n
    ranges.append(f"{start}" if start==prev else f"{start} al {prev}")
    return " / ".join(ranges)

# --- Eventos ---
@bot.event
async def on_ready():
    print(f"✨ Saku está en línea como {bot.user}")
    if not GUILD_IDS: print("⚠️ No se han definido GUILD_IDS en el .env")

# --- Comando revisar ---
@bot.command()
async def revisar(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado aquí")

    await ctx.send("🔍 Buscando enlaces de Drive en los mensajes fijados...")

    creds = authenticate()
    service = build("drive", "v3", credentials=creds)
    pinned_messages = await ctx.channel.pins()

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

                # --- 💖 Embed bonito con color sakura ---
                embed = discord.Embed(
                    title="🌸 Saku — Revisión de Drive",
                    description=f"**📁 Carpeta revisada:**\n{link}",
                    color=0xFFB6C1  # Rosa sakura pastel
                )
                embed.add_field(name="💫 RAW", value=join_ranges(raw_caps), inline=True)
                embed.add_field(name="💬 TRAD", value=join_ranges(trad_caps), inline=True)
                embed.add_field(name="🧼 CLEAN", value=join_ranges(clean_caps), inline=True)
                embed.add_field(name="🖋 TYPE", value=join_ranges(type_caps), inline=True)
                embed.set_footer(text="Revisión completada con éxito 🌸")

                await ctx.send(embed=embed)

            except Exception as e:
                embed_error = discord.Embed(
                    title="⚠️ Saku — Error de acceso",
                    description="No se pudo acceder a la API. Verifica permisos de Drive.\n"
                                "Debe permitir acceso a **soulferre1995@gmail.com**",
                    color=0xFFD1DC  # Rosa claro más suave
                )
                embed_error.set_footer(text=str(e))
                await ctx.send(embed=embed_error)
#    await ctx.send("✨ Revisión finalizada, todo listo 💖")
# --- Ejecutar bot ---
if not getattr(sys.modules[__name__], "_bot_started", False):
    setattr(sys.modules[__name__], "_bot_started", True)
    bot.run(TOKEN)
