import os, re, discord, asyncio, requests, time
from discord.ext import commands
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# 💖 Editado por Rami
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [int(x.strip()) for x in os.getenv("GUILD_IDS", "").split(",") if x.strip()]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# — Configuración de la hoja
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

# — Crear credenciales de servicio
SERVICE_ACCOUNT_FILE = "service_account.json"  # asegúrate que este archivo esté en tu Replit

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

# — Crear cliente de Sheets
sheet_service = build("sheets", "v4", credentials=creds)
sheet = sheet_service.spreadsheets()

# Funciones de Saku_Drive 
def authenticate():
    SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
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

# Funciones de Saku_RAW 
def evento_a(soup):
    contenedores = soup.select('astro-slot > div[data-hk]')
    if contenedores:
        ultimo_div = contenedores[-1]
        enlace = ultimo_div.select_one('a.link-hover')
        if enlace:
            return enlace.get_text(strip=True)
    return None

def evento_b(soup):
    b_tag = soup.select_one("div.main b")
    return b_tag.get_text(strip=True) if b_tag else None

def evento_c(soup):
    for li in soup.select('li.flex.justify-between'):
        spans = li.find_all('span')
        if len(spans) == 2:
            return spans[0].get_text(strip=True)
    return None

def evento_d(soup):
    contenedor = soup.select_one('div.all_data_list ul.fed-part-rows li a')
    return contenedor.get_text(strip=True) if contenedor else None

def evento_e(html):
    match = re.search(r'<span class="epcur epcurlast">\s*(.*?)\s*</span>', html, re.IGNORECASE)
    return match.group(1).strip() if match else None

def evento_f(soup):
    spans = soup.select('div.title-item span.text')
    texto_libres = [s.get_text(strip=True) for s in spans if "text-locked" not in s.get("class", [])]
    return texto_libres[-1] if texto_libres else None

def evento_g(soup):
    primer_li = soup.select_one("li.wp-manga-chapter a")
    if primer_li:
        texto = primer_li.get_text(strip=True)
        return texto if "Chapter" in texto else None
    return None

def evento_h(html):
    match = re.search(r'title="(Ch\.\s*\d+)"', html)
    return match.group(1) if match else None

def evento_i(html):
    match = re.search(r'<div class="latest-chapters">.*?<a[^>]*>\s*<strong[^>]*>(.*?)</strong>', html, re.DOTALL)
    return match.group(1).strip() if match else None

def evento_j(soup):
    bloques = soup.select('div.group.flex.flex-col')
    for bloque in bloques:
        sub = bloque.select_one('div.space-x-1 a.link-hover')
        if sub:
            texto = sub.get_text(strip=True)
            span = bloque.select_one('div.space-x-1 span.opacity-80')
            extra = span.get_text(strip=True) if span else ""
            return f"{texto} {extra}".strip()
    return None

def detectar_evento(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return None, "Error HTTP"

        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        for letra, func in [
            ("A", lambda: evento_a(soup)),
            ("B", lambda: evento_b(soup)),
            ("C", lambda: evento_c(soup)),
            ("D", lambda: evento_d(soup)),
            ("E", lambda: evento_e(html)),
            ("F", lambda: evento_f(soup)),
            ("G", lambda: evento_g(soup)),
            ("H", lambda: evento_h(html)),
            ("I", lambda: evento_i(html)),
            ("J", lambda: evento_j(soup)),
        ]:
            resultado = func()
            if resultado:
                return resultado, letra

        return None, "No detectado"

    except Exception as e:
        return None, str(e)
    pass
    
# Funciones de Saku_Search
MESES = {
    "enero": "January", "febrero": "February", "marzo": "March", "abril": "April",
    "mayo": "May", "junio": "June", "julio": "July", "agosto": "August",
    "septiembre": "September", "octubre": "October", "noviembre": "November",
    "diciembre": "December"
}

def evento_eter(url, preestreno=False, retries=3, delay=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://eternalmangas.org/"
    }

    for intento in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            h1_blocks = soup.find_all("h1", class_="font-semibold text-medium")
            caps = "No encontrado"
            actual = "No encontrado"

            for h1 in h1_blocks:
                text = h1.get_text(strip=True)
                div = h1.find_next_sibling("div")
                if div and div.p:
                    valor = div.p.get_text(strip=True)
                    if "Capítulos" in text:
                        caps = valor
                    elif "Última actualización" in text:
                        actual = valor

            if preestreno:
                try:
                    caps_num = int(caps)
                    if caps_num > 0:
                        caps_num -= 1
                    caps = str(caps_num)
                except:
                    pass

            actual = fecha_a_dias_atras(actual)

            return f"ETERNAL\n> Capítulo: {caps}\n> Actualizado: {actual}"

        except requests.exceptions.HTTPError as e:
            if response.status_code in [520, 503, 429]:
                print(f"⚠ Intento {intento}/{retries}: {response.status_code} recibido, reintentando en {delay}s...")
                time.sleep(delay)
                continue
            return f"❌ Error HTTP: {e}"
        except Exception as e:
            print(f"⚠ Intento {intento}/{retries} falló: {e}")
            time.sleep(delay)
            continue

    return "❌ No se pudo acceder a EternalMangas después de varios intentos."
    pass

def evento_lec(url, preestreno=False, retries=3, delay=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://lectorjpg.com/"
    }

    for intento in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, "html.parser")

            block = soup.select_one("a.group.relative.flex")
            if not block:
                return "❌ No se encontró ningún capítulo."

            cap_span = block.select_one("span.truncate.text-sm")
            cap_text = cap_span.get_text(strip=True) if cap_span else "Desconocido"
            cap_match = re.search(r'capitulo\s*(\d+)', cap_text, re.I)
            cap = cap_match.group(1) if cap_match else cap_text

            if preestreno:
                try:
                    cap_num = int(cap)
                    if cap_num > 0:
                        cap_num -= 1
                    cap = str(cap_num)
                except:
                    pass

            fecha_span = block.select_one("span[class*='text-white/50'], span[class*='text-white/60']")
            fecha_text = fecha_span.get_text(strip=True) if fecha_span else "Desconocido"
            fecha_text = fecha_text.encode("latin1", "ignore").decode("utf-8", "ignore")

            fecha_text = fecha_a_dias_atras(fecha_text)

            return f"LECTORJPG\n> Capítulo: {cap}\n> Actualizado: {fecha_text}"

        except requests.exceptions.HTTPError as e:
            if response.status_code in [503, 429]:
                print(f"⚠ Intento {intento}/{retries}: {response.status_code} recibido, reintentando en {delay}s...")
                time.sleep(delay)
                continue
            return f"❌ Error HTTP: {e}"
        except Exception as e:
            print(f"⚠ Intento {intento}/{retries} falló: {e}")
            time.sleep(delay)
            continue

    return "❌ No se pudo acceder a LectorJPG después de varios intentos."
    pass

def evento_cath(url, preestreno=False, retries=3, delay=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://catharsisworld.dig-it.info/"
    }

    cath_user = os.getenv("CATH_USER", "")
    cath_pass = os.getenv("CATH_PASS", "")
    cath_verif = os.getenv("CATH_VERIF", "1")

    cookies = {"Verificación_De_Edad": cath_verif}
    session = requests.Session()

    if cath_user and cath_pass:
        try:
            login_url = "https://catharsisworld.dig-it.info/login"
            payload = {"username": cath_user, "password": cath_pass}
            resp = session.post(login_url, data=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                print("✅ Login en Catharsis exitoso (usuario real).")
            else:
                print(f"⚠️ Login fallido ({resp.status_code}), se intentará solo con cookie de verificación.")
        except Exception as e:
            print(f"⚠️ Error durante login Catharsis: {e}")

    for intento in range(1, retries + 1):
        try:
            response = session.get(url, headers=headers, cookies=cookies, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            cap_elem = soup.select_one("ul#list-chapters span.text-md")
            fecha_elem = soup.select_one("ul#list-chapters div.text-xs")

            cap_text = cap_elem.get_text(strip=True) if cap_elem else "Desconocido"
            fecha_text = fecha_elem.get_text(strip=True) if fecha_elem else "Desconocido"

            cap_match = re.search(r'cap[ií]tulo\s*(\d+)', cap_text, re.I)
            cap = cap_match.group(1) if cap_match else cap_text

            if preestreno:
                try:
                    cap_num = int(cap)
                    if cap_num > 0:
                        cap_num -= 1
                    cap = str(cap_num)
                except:
                    pass

            fecha_text = fecha_text.replace(" ago", "").strip()
            fecha_text = fecha_text.replace("hours", "horas").replace("hour", "hora")
            fecha_text = fecha_text.replace("days", "días").replace("day", "día")
            fecha_text = fecha_text.replace("minutes", "minutos").replace("minute", "minuto")

            fecha_text = fecha_a_dias_atras(fecha_text)

            if cap == "Desconocido" and fecha_text == "Desconocido":
                print("⚠️ No se pudieron detectar los selectores, HTML diferente o protección activa.")
                return "❌ No se pudo leer la información de Catharsis."

            return f"CATHARSIS\n> Capítulo: {cap}\n> Actualizado: {fecha_text}"

        except Exception as e:
            print(f"⚠ Error en evento_cath (intento {intento}): {e}")
            time.sleep(delay)
            continue

    return "❌ No se pudo acceder a Catharsis después de varios intentos."
    pass

def fecha_a_dias_atras(fecha_str):
    fecha_str = fecha_str.strip().lower()

    if fecha_str in ["ayer"]:
        return "1 día atrás"
    if fecha_str in ["anteayer"]:
        return "2 días atrás"

    try:
        fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
        delta = datetime.today() - fecha_dt
        return f"{delta.days} días atrás"
    except:
        pass

    try:
        for es, en in MESES.items():
            if fecha_str.startswith(es):
                fecha_str = fecha_str.replace(es, en, 1)
                break
        fecha_dt = datetime.strptime(fecha_str, "%B %d, %Y")
        delta = datetime.today() - fecha_dt
        return f"{delta.days} días atrás"
    except:
        pass

    horas_match = re.search(r'(\d+)\s*hora', fecha_str)
    dias_match = re.search(r'(\d+)\s*día', fecha_str)
    meses_match = re.search(r'(\d+)\s*mes', fecha_str)

    if horas_match:
        horas = int(horas_match.group(1))
        return "0 días atrás" if horas < 24 else f"{horas//24} días atrás"

    if dias_match:
        dias = int(dias_match.group(1))
        return f"{dias} días atrás"

    if meses_match:
        meses = int(meses_match.group(1))
        dias = meses * 30
        return f"{dias} días atrás"

    return fecha_str
    pass

def obtener_color(dias_str, sitio):
    try:
        dias = int(re.search(r'(\d+)', dias_str).group(1))
    except:
        dias = 0

    if sitio == "CATHARSIS":
        if dias <= 7:
            return 0x2ECC71  # Verde
        elif 8 <= dias <= 13:
            return 0xF1C40F  # Amarillo
        else:
            return 0xE74C3C  # Rojo
    else:  # ETERNAL o LECTOR
        if dias <= 45:
            return 0x2ECC71
        elif 46 <= dias <= 59:
            return 0xF1C40F
        else:
            return 0xE74C3C
    pass

# Eventos de Discord
@bot.event
async def on_ready():
    print(f"✨ Bot en línea como {bot.user}")

# Comando !drive
@bot.command()
async def drive(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")

    await ctx.send("🔍 Buscando enlaces de Drive en los mensajes fijados...")

    creds = authenticate()
    service = build("drive", "v3", credentials=creds)
    pinned_messages = await ctx.channel.pins()

    found_any = False  # 🌸 Bandera para saber si hubo enlaces

    for msg in pinned_messages:
        links = extract_drive_links(msg.content)
        if not links:
            continue

        found_any = True  # Sí hubo al menos un enlace

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
                    color=0xFFB6C1
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
                    color=0xFFD1DC
                )
                embed_error.set_footer(text=str(e))
                await ctx.send(embed=embed_error)

    # 🌸 Si no se encontró ningún enlace Drive
    if not found_any:
        embed_no_links = discord.Embed(
            title="🌸 Saku_Drive — *Sin enlaces fijados*",
            description="No encontré ningún enlace de Google Drive en los mensajes fijados.\n"
                        "Fíjalo primero y vuelve a intentarlo 💖",
            color=0xFFB6C1
        )
        embed_no_links.set_footer(text="Asegúrate de fijar el enlace DRIVE apropiadamente 💖")
        await ctx.send(embed=embed_no_links)

# Comando !raw
@bot.command()
async def raw(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")
    # Lógica completa de tu Saku_RAW aquí
    await ctx.send("🔍 Buscando enlaces de RAW en los mensajes fijados...")
    pinned = await ctx.channel.pins()

    encontrados = False

    for msg in pinned:
        urls = re.findall(r"https?://[^\s>]+", msg.content)
        for url in urls:
            if any(x in url for x in [
                "eternalmangas.org", "lectorjpg.com", "catharsisworld.dig-it.info", "drive.google.com"
            ]):
                continue

            encontrados = True

            lineas = msg.content.splitlines()
            texto_arriba = ""
            for i, linea in enumerate(lineas):
                if url in linea and i > 0:
                    posible_texto = lineas[i - 1].strip()
                    if posible_texto:
                        texto_arriba = posible_texto
                    break

            dominio = re.search(r"https?://(?:www\.)?([^/]+)/", url)
            sitio = dominio.group(1) if dominio else "Sitio desconocido"

            titulo_embed = f"{texto_arriba} ({sitio.upper()})" if texto_arriba else f"{sitio.upper()}"

            cap, evento = detectar_evento(url)

            if cap:
                embed = discord.Embed(
                    title=titulo_embed,
                    description=f"Último capítulo: {cap}",
                    color=0x6AFF7A
                )
            else:
                embed = discord.Embed(
                    title=titulo_embed,
                    description="❌ Estructura incompatible — Revisión manual requerida",
                    color=0xFF5C5C
                )

            await ctx.send(embed=embed)

    if not encontrados:
        embed = discord.Embed(
            title="🌸 Saku_RAW — *Sin enlaces válidos*",
            description="No se encontraron enlaces de raws en los mensajes fijados.\n",
            color=0xF8C8DC
        )
        embed.set_footer(text="Asegúrate de fijar mensajes con los enlaces correctos 💖")
        await ctx.send(embed=embed)  

# Comando !sitio
@bot.command()
async def sitio(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")

    await ctx.send("🔍 Buscando enlaces de proyecto en los mensajes fijados...")
    pinned = await ctx.channel.pins()
    encontrados = False
    tasks = []

    for msg in pinned:
        pre_eter = "Eternal: 00" in msg.content
        pre_lec = "Lector: 00" in msg.content
        pre_cath = "Catharsis: 00" in msg.content

        match_eter = re.search(r"https?://(?:www\.)?eternalmangas\.org/[^\s>]+", msg.content)
        match_lec = re.search(r"https?://(?:www\.)?lectorjpg\.com/series/[^\s>]+", msg.content)
        match_cath = re.search(r"https?://(?:www\.)?catharsisworld\.dig-it\.info/[^\s>]+", msg.content)

        if match_eter:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_eter, match_eter.group(0), preestreno=pre_eter))
        if match_lec:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_lec, match_lec.group(0), preestreno=pre_lec))
        if match_cath:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_cath, match_cath.group(0), preestreno=pre_cath))

    if not encontrados:
        embed = discord.Embed(
            title="🌸 Saku_Search — *Sin enlaces encontrados*",
            description="No hay enlaces válidos de Eternal, LectorJPG o Catharsis en los mensajes fijados.",
            color=0xF8C8DC
        )
        embed.set_footer(text="Asegúrate de fijar mensajes con los enlaces correctos 💖")
        return await ctx.send(embed=embed)

    resultados = await asyncio.gather(*tasks, return_exceptions=True)

    # Diccionario con todas las columnas separadas
    resultado_dict = {
        "catharsis_cap": "N/A",
        "catharsis_date": "N/A",
        "eternal_cap": "N/A",
        "eternal_date": "N/A",
        "lector_cap": "N/A",
        "lector_date": "N/A"
    }

    for res in resultados:
        if isinstance(res, Exception):
            embed = discord.Embed(
                title="⚠ Error en búsqueda",
                description=str(res),
                color=0xE74C3C
            )
            await ctx.send(embed=embed)
            continue

        cap_match = re.search(r'Capítulo: ([^\n]+)', res)
        act_match = re.search(r'Actualizado: ([^\n]+)', res)

        dias_texto = act_match.group(1) if act_match else "N/A"
        cap_texto = cap_match.group(1) if cap_match else "N/A"

        # Determinar sitio y asignar a columnas correctas
        if res.startswith("CATHARSIS"):
            resultado_dict["catharsis_cap"] = cap_texto
            resultado_dict["catharsis_date"] = dias_texto
        elif res.startswith("ETERNAL"):
            resultado_dict["eternal_cap"] = cap_texto
            resultado_dict["eternal_date"] = dias_texto
        elif res.startswith("LECTORJPG"):
            resultado_dict["lector_cap"] = cap_texto
            resultado_dict["lector_date"] = dias_texto

        # Embed para mostrar al instante
        sitio_icono = {"CATHARSIS": "💫", "ETERNAL": "🌸", "LECTORJPG": "📘"}.get(res.split()[0], "❓")
        embed = discord.Embed(
            title=f"{sitio_icono} {res.split()[0]}",
            description=f"Capítulo: {cap_texto}\nActualizado: {dias_texto}",
            color=obtener_color(dias_texto, res.split()[0])
        )
        await ctx.send(embed=embed)

    canal = ctx.channel.name
    escribir_a_hoja(canal, resultado_dict)

def escribir_a_hoja(canal, resultados):
    try:
        range_name = f"{SHEET_NAME}!A2:H"  # <-- empieza en fila 2
        resp = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = resp.get("values", [])

        fila_existente = None
        ultimo_item = 0

        for i, row in enumerate(values, start=2):  # <-- offset de fila 2
            if len(row) > 0 and row[0].isdigit():
                ultimo_item = max(ultimo_item, int(row[0]))
            if len(row) > 1 and row[1].strip().lower() == canal.lower():
                fila_existente = i

        item_val = fila_existente - 1 if fila_existente else (ultimo_item + 1)
        fila = [
            str(item_val),
            canal,
            resultados.get("catharsis_cap", "N/A"),
            resultados.get("catharsis_date", "N/A"),
            resultados.get("eternal_cap", "N/A"),
            resultados.get("eternal_date", "N/A"),
            resultados.get("lector_cap", "N/A"),
            resultados.get("lector_date", "N/A")
        ]

        body = {"values": [fila]}

        if fila_existente:
            rango_actualizar = f"{SHEET_NAME}!A{fila_existente}:H{fila_existente}"
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=rango_actualizar,
                valueInputOption="RAW",
                body=body
            ).execute()
        else:
            sheet.values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()

    except Exception as e:
        print(f"❌ Error al escribir en la hoja: {e}")

# Comando !larry
@bot.command()
async def table(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")

    await ctx.send("🔍 Analizando lista...")

    def extraer_dias(texto):
        if not texto or texto.lower() in ["n/a", "no disponible"]:
            return None
        if "mes" in texto:
            m = re.search(r"(\d+)\s*mes", texto)
            return int(m.group(1)) * 30 if m else 30
        m = re.search(r"(\d+)\s*día", texto)
        return int(m.group(1)) if m else None

    def obtener_icono(sitio, dias):
        if dias is None:
            return "⚪"
        if sitio == "CATHARSIS":
            if dias > 14:
                return "🔴"
            elif dias > 7:
                return "🟡"
            else:
                return "🟢"
        else:  # ETERNAL o LECTOR
            if dias > 60:
                return "🔴"
            elif dias > 45:
                return "🟡"
            else:
                return "🟢"

    try:
        range_name = f"{SHEET_NAME}!A2:H"
        resp = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = resp.get("values", [])

        if not values:
            return await ctx.send("❌ No hay datos registrados en la hoja.")

        proyectos = []
        for row in values:
            if len(row) < 8:
                continue
            canal_nombre = row[1]
            cath_date = row[3]
            eter_date = row[5]
            lec_date = row[7]

            urg_total = sum(
                d for d in [
                    extraer_dias(cath_date),
                    extraer_dias(eter_date),
                    extraer_dias(lec_date)
                ] if d is not None
            )

            proyectos.append({
                "canal": canal_nombre,
                "cath_cap": row[2], "cath_date": cath_date,
                "eter_cap": row[4], "eter_date": eter_date,
                "lec_cap": row[6], "lec_date": lec_date,
                "urg": urg_total
            })

        proyectos.sort(key=lambda x: x["urg"], reverse=True)

        total = len(proyectos)
        por_bloque = 15
        grupos = [proyectos[i:i+por_bloque] for i in range(0, total, por_bloque)]

        for i, grupo in enumerate(grupos, start=1):
            texto = ""
            for p in grupo:
                canal_obj = discord.utils.get(ctx.guild.channels, name=p["canal"])
                canal_mencion = f"<#{canal_obj.id}>" if canal_obj else f"#{p['canal']}"

                # convertir fechas a días
                d_cath = extraer_dias(p["cath_date"])
                d_eter = extraer_dias(p["eter_date"])
                d_lec = extraer_dias(p["lec_date"])

                # obtener iconos
                i_cath = obtener_icono("CATHARSIS", d_cath)
                i_eter = obtener_icono("ETERNAL", d_eter)
                i_lec = obtener_icono("LECTOR", d_lec)

                texto += (
                    f"**{canal_mencion}**\n"
                    f"{i_cath} **CATH**: {p['cath_cap']} - *({p['cath_date']})*\n"
                    f"{i_eter} **ETER**: {p['eter_cap']} - *({p['eter_date']})*\n"
                    f"{i_lec} **LEC**: {p['lec_cap']} - *({p['lec_date']})*\n\n"
                )

            embed = discord.Embed(
                title=f"📋 Resumen de proyectos ({min(i*por_bloque, total)}/{total})",
                description=texto,
                color=0xF8C8DC
            )
            await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error al obtener los datos: {e}")
        print(f"❌ Error en !larry: {e}")

# Comando !acceso
@bot.command()
@commands.has_role(1357527939226533920)  # Rol ADMIN
async def acceso(ctx, user: discord.Member = None):
    """Otorga acceso de editor a un usuario según la lista USUARIOS."""
    if user is None:
        embed = discord.Embed(
            title="🌸 Saku — Acceso",
            description=f"Debes mencionar a un usuario. Ejemplo: `!acceso @usuario`",
            color=0xFFB6C1
        )
        await ctx.send(embed=embed)
        return

    try:
        # Obtener enlace Drive fijado en el canal
        pinned = await ctx.channel.pins()
        drive_link = next((m.content for m in pinned if "drive.google.com" in m.content), None)

        if not drive_link:
            embed = discord.Embed(
                title="🌸 Saku — Acceso",
                description=f"⚠️ No hay enlaces de Google Drive fijados en este canal.",
                color=0xFFB6C1
            )
            await ctx.send(embed=embed)
            return

        # Extraer ID del archivo o carpeta
        match = re.search(r"/(?:folders|file)/([a-zA-Z0-9_-]+)", drive_link)
        if not match:
            embed = discord.Embed(
                title="🌸 Saku — Acceso",
                description=f"❌ No se pudo identificar el ID de archivo o carpeta de Google Drive.",
                color=0xFFB6C1
            )
            await ctx.send(embed=embed)
            return

        file_id = match.group(1)

        # Leer la hoja USUARIOS
        USERS_SHEET_NAME = os.getenv("USERS_SHEET_NAME")
        data = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{USERS_SHEET_NAME}!A2:C"
        ).execute().get("values", [])

        # Buscar usuario en la lista
        discord_id = str(user.id)
        matched = None
        for row in data:
            if len(row) >= 3 and row[1] == discord_id:
                matched = row
                break

        if not matched:
            embed = discord.Embed(
                title="🌸 Saku — Acceso",
                description=f"❌ Usuario {user.mention} no encontrado en la lista USUARIOS.",
                color=0xFFB6C1
            )
            await ctx.send(embed=embed)
            return

        email = matched[2]

        # Crear cliente de Drive
        drive_service = build("drive", "v3", credentials=creds)

        # Verificar si ya tiene acceso
        try:
            permissions = drive_service.permissions().list(fileId=file_id, fields="permissions(emailAddress,role)").execute()
            existing = [p for p in permissions.get("permissions", []) if p.get("emailAddress") == email]
            if existing:
                embed = discord.Embed(
                    title="🌸 Saku — Acceso",
                    description=f"⚠️ {user.mention} ya tenía acceso como **{existing[0]['role']}**.",
                    color=0xFFB6C1
                )
                await ctx.send(embed=embed)
                return
        except Exception:
            pass  # Si no puede listar permisos, igual intenta otorgar acceso

        # Intentar otorgar acceso de editor
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={
                    "type": "user",
                    "role": "writer",
                    "emailAddress": email
                },
                fields="id"
            ).execute()
            embed = discord.Embed(
                title="🌸 Saku — Acceso",
                description=f"✅ Acceso concedido a {user.mention}.",
                color=0xFFB6C1
            )
            await ctx.send(embed=embed)

        except Exception as e:
            err_text = str(e)

            # Caso especial: el correo no puede recibir permisos (por ser dueño u otro motivo)
            if "invalid or not applicable for the given permission type" in err_text:
                embed = discord.Embed(
                    title="🌸 Saku — Acceso",
                    description=(
                        f"⚠️ No se pudo otorgar acceso a {user.mention}.\n"
                        f"Posiblemente ya es propietario o el correo no acepta permisos directos.\n\n"
                        f"🔔 <@&1357527939226533920>, revise manualmente el acceso al Drive."
                    ),
                    color=0xFFC0CB
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="🌸 Saku — Acceso",
                    description=f"❌ API no conectada, asegúrese de que SAKU_BOT tenga acceso al Drive solicitado.",
                    color=0xFFB6C1
                )
                await ctx.send(embed=embed)

            print(f"[ERROR acceso] {e}")

    except Exception as e:
        embed = discord.Embed(
            title="🌸 Saku — Acceso",
            description=f"⚠️ Ocurrió un error inesperado al procesar el comando.",
            color=0xFFB6C1
        )
        await ctx.send(embed=embed)
        print(f"[ERROR acceso general] {e}")

@bot.command()
async def gen(ctx):
    if ctx.guild.id not in GUILD_IDS:
        return await ctx.send("❌ Este comando no está autorizado en este servidor.")
    await ctx.send("🔍 Procesando, porfavor espere...")
    try:
        # 1️⃣ Leer la columna B de la hoja LISTA (canales)
        range_name = f"{SHEET_NAME}!B2:B"  # columna B desde fila 2
        resp = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        canales = [row[0].strip() for row in resp.get("values", []) if row]

        if not canales:
            return await ctx.send("❌ No se encontraron canales en la columna B.")

        # 2️⃣ Enviar mensaje de progreso inicial
        progress_msg = await ctx.send(f"🔄 Autollamado de sitios, revisando canales 0/{len(canales)}")

        # 3️⃣ Recorrer cada canal y ejecutar !sitio
        for i, canal_nombre in enumerate(canales, start=1):
            canal_obj = discord.utils.get(ctx.guild.channels, name=canal_nombre)
            if not canal_obj:
                await progress_msg.edit(content=f"⚠ Canal **{canal_nombre}** no encontrado. {i}/{len(canales)}")
                await asyncio.sleep(1)
                continue

            # Actualizar mensaje de progreso
            await progress_msg.edit(content=f"⏳ Procesando canal {i}/{len(canales)}: **{canal_nombre}**")

            # DummyCtx para invocar !sitio en el canal correcto
            class DummyMessage:
                def __init__(self, author, channel):
                    self.author = author
                    self.channel = channel
                    self.attachments = []

            class DummyCtx:
                def __init__(self, bot, channel, guild, author, send):
                    self.bot = bot
                    self.channel = channel
                    self.guild = guild
                    self.author = author
                    self.send = send
                    self.message = DummyMessage(author, channel)
                    self.view = None

            dummy_ctx = DummyCtx(
                bot=ctx.bot,
                channel=canal_obj,
                guild=ctx.guild,
                author=ctx.author,
                send=canal_obj.send  # ⚡ enviará embeds en el canal correcto
            )

            await sitio.invoke(dummy_ctx)
            await asyncio.sleep(3)  # espera de 3 segundos antes del siguiente canal

        # 4️⃣ Finalizar mensaje de progreso
        await progress_msg.edit(content=f"✅ Actualización completada: revisados {len(canales)}/{len(canales)} canales")

        # 5️⃣ Llamar !table en el canal de invocación
        await table.invoke(ctx)

    except Exception as e:
        await ctx.send(f"❌ Error durante !gen: {e}")
        print(f"❌ Error en comando !gen: {e}")

# Ejecutar bot
bot.run(TOKEN)
