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
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urlunparse

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
SHEET_NAME2 = os.getenv("SHEET_NAME2")

# — Crear credenciales de servicio
SERVICE_ACCOUNT_FILE = "service_account.json"

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

# Lista de dominios Catharsis válidos (fácil de actualizar)
CATH_DOMAINS = [
    "catharsisworld.dig-it.info",
    "catharsisworld.vxviral.xyz"
]

def url_with_domain(url: str, new_domain: str) -> str:
    """Reemplaza el dominio de un URL manteniendo esquema y path."""
    p = urlparse(url)
    return urlunparse((p.scheme, new_domain, p.path, "", "", ""))

def check_alive(url: str, timeout=10):
    """Revisa si un URL responde correctamente sin romper el flujo."""
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200
    except:
        return False

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
            caps = "N/A"
            actual = "N/A"

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

            # 📌 tomar el último update y no el primero
            blocks = soup.select("a.group.relative.flex")
            if not blocks:
                return "❌ No se encontró ningún capítulo."

            block = blocks[-1]  # <<--- ESTE ES EL MÁS RECIENTE

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

def evento_cath(url, preestreno=False, retries=3, delay=5):
    # ---------- 1) Intento: usar el link tal como viene ----------
    if not check_alive(url):

        # ---------- 2) Intento: probar todos los dominios conocidos ----------
        dominio_actual = urlparse(url).netloc

        for dom in CATH_DOMAINS:
            if dom == dominio_actual:
                continue  # ya lo probamos
            alt_url = url_with_domain(url, dom)
            if check_alive(alt_url):
                url = alt_url
                break
        else:
            print("❌ Ningún dominio Catharsis respondió.")
            return "❌ Catharsis parece estar caído en todos los dominios."

# 3 Extraer dominio final del URL ya corregido
    try:
        dominio = url.split("/")[2]  # ejemplo: catharsisworld.vxviral.xyz
    except:
        dominio = "catharsisworld.vxviral.xyz"  # fallback seguro

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": f"https://{dominio}/"
    }

    cath_user = os.getenv("CATH_USER", "")
    cath_pass = os.getenv("CATH_PASS", "")
    cath_verif = os.getenv("CATH_VERIF", "1")

    cookies = {"Verificación_De_Edad": cath_verif}
    session = requests.Session()

    if cath_user and cath_pass:
        try:
            login_url = f"https://{dominio}/login"
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

def evento_col(url, preestreno=False, retries=3, delay=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://colorcitoscan.com/"
    }
    for intento in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            # Seleccionar todos los bloques de capítulo
            bloques = soup.select("div.w-full.grid.grid-cols-3 a")
            if not bloques:
                return "❌ No se encontraron capítulos en Colorcito."
            ultimo = bloques[0]  # tomamos el primero (el más reciente)
            cap_elem = ultimo.select_one("p.font-semibold")
            tiempo_elem = ultimo.select("p.font-montserrat")
            cap_text = cap_elem.get_text(strip=True) if cap_elem else "Desconocido"
            tiempo_text = tiempo_elem[-1].get_text(strip=True) if tiempo_elem else "Desconocido"
            # Extraer número de capítulo
            cap_match = re.search(r'Cap\.?\s*(\d+)', cap_text, re.I)
            cap = cap_match.group(1) if cap_match else cap_text
            if preestreno:
                try:
                    cap_num = int(cap)
                    if cap_num > 0:
                        cap_num -= 1
                    cap = str(cap_num)
                except:
                    pass
            # Normalizar texto de tiempo como en cath
            tiempo_text = tiempo_text.replace(" ago", "").strip()
            tiempo_text = tiempo_text.replace("hours", "horas").replace("hour", "hora")
            tiempo_text = tiempo_text.replace("days", "días").replace("day", "día")
            tiempo_text = tiempo_text.replace("minutes", "minutos").replace("minute", "minuto")
            # Función auxiliar que ya tienes
            tiempo_text = fecha_a_dias_atras(tiempo_text)
            return f"COLORCITO\n> Capítulo: {cap}\n> Actualizado: {tiempo_text}"
        except requests.exceptions.HTTPError as e:
            if response.status_code in [503, 429, 520]:
                print(f"⚠ Intento {intento}/{retries}: {response.status_code} recibido, reintentando en {delay}s...")
                time.sleep(delay)
                continue
            return f"❌ Error HTTP: {e}"
        except Exception as e:
            print(f"⚠ Intento {intento}/{retries} falló: {e}")
            time.sleep(delay)
            continue
    return "❌ No se pudo acceder a Colorcito después de varios intentos."

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

# --- Constantes / variables fijas ---
LINK_TELE = os.getenv("LINK_TELEGRAM", "https://t.me/+voe0LK-TSzA1NjUx")
LINK_DIS  = os.getenv("LINK_DISCORD", "https://discord.gg/NRdjpBFy9E")

LINK_GLOBAL_ETER = "https://eternalmangas.org/"
LINK_GLOBAL_CATH = "https://catharsisworld.com/"
LINK_GLOBAL_LEC  = "https://lectorjpg.com/"
LINK_GLOBAL_COL  = "https://colorcitoscan.com/"

# --- Helpers para Google Sheets ---
def normalize_channel_name(ch: str) -> str:
    """
    Normaliza el canal que el usuario ingresa.
    Acepta formatos:
      - "#nombre"
      - "nombre"
      - "<#1234567890>" (mención)
    Devuelve el nombre sin '#', en minusculas para comparar.
    """
    ch = ch.strip()
    # mención: <#id>
    m = re.match(r"<#(\d+)>", ch)
    if m:
        return m.group(1)  # devolvemos id en este caso, lo manejaremos separado
    # si comienza con '#'
    if ch.startswith("#"):
        return ch[1:].strip().lower()
    return ch.lower()

def get_sheet_rows() -> List[List[str]]:
    """
    Trae filas desde la hoja VARIABLES.
    Espera que la hoja tenga encabezado en fila 1 y datos desde fila 2 en adelante.
    Retorna la matriz de filas (cada fila es lista de celdas como strings).
    """
    try:
        range_name = f"{SHEET_NAME2}!A2:F"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get("values", [])
        return values
    except Exception as e:
        # Este es un punto crítico para depurar si las credenciales no están ok
        print(f"⚠️ Error leyendo Google Sheet: {e}")
        return []

def find_project_row_by_channel(channel_lookup: str) -> Optional[Dict[str, str]]:
    """
    Busca la fila cuyo valor en la columna B (index 1) coincida con channel_lookup.
    channel_lookup debe estar normalizado (sin '#', minúsculas) o puede ser channel ID como string.
    Retorna diccionario con claves: canal, titulo, sinopsis, generos, tipo
    """
    rows = get_sheet_rows()
    lookup = channel_lookup.lower()
    for row in rows:
        # row puede tener longitud variable; aseguramos índices
        col_b = row[1].strip().lower() if len(row) > 1 and row[1] else ""
        if col_b == lookup:
            return {
                "CANAL": col_b,
                "TITULO": row[2].strip() if len(row) > 2 else "",
                "SINOPSIS": row[3].strip() if len(row) > 3 else "",
                "GENEROS": row[4].strip() if len(row) > 4 else "",
                "TIPO": row[5].strip() if len(row) > 5 else ""
            }
    # no encontrado
    return None

# --- Helpers para leer pinned messages del canal ---
URL_REGEX = re.compile(r"https?://[^\s>]+")
def extract_urls_from_text(text: str) -> List[str]:
    return URL_REGEX.findall(text)

async def read_channel_pins(channel: discord.TextChannel) -> Dict[str, Optional[str]]:
    """
    Lee los mensajes fijados (pins) de un canal y busca links relacionados con:
      - catharsis
      - eternal/eternalmangas
      - lectorjpg
      - colorcitoscan
    Devuelve dict con claves LINK_CATH, LINK_ETER, LINK_LEC, LINK_COL (valor string o None)
    """
    found = {
        "LINK_CATH": None,
        "LINK_ETER": None,
        "LINK_LEC": None,
        "LINK_COL": None
    }
    try:
        pins = await channel.pins()
    except Exception as e:
#        print(f"⚠️ No pude leer pins del canal {channel}: {e}")
        return found

    for msg in pins:
        text = (msg.content or "") + "\n" + " ".join([att.url for att in msg.attachments]) if msg.attachments else (msg.content or "")
        urls = extract_urls_from_text(text)

        # si hay URLs, buscar por dominio
        for u in urls:
            lu = u.lower()
            if "catharsis" in lu and not found["LINK_CATH"]:
                found["LINK_CATH"] = u
            if "eternalmangas" in lu and not found["LINK_ETER"]:
                found["LINK_ETER"] = u
            if "lectorjpg" in lu and not found["LINK_LEC"]:
                found["LINK_LEC"] = u
            if "colorcitoscan" in lu and not found["LINK_COL"]:
                found["LINK_COL"] = u

        # Si no hay URLs, intentar detectar formatos tipo "Eternal: 00" o "Eternal: slug"
        # Buscamos líneas con prefijos conocidos
        lines = (msg.content or "").splitlines()
        for ln in lines:
            ln_stripped = ln.strip()
            # formato "Eternal: slug" -> no es URL, pero puede indicar que existe una referencia
            if ln_stripped.lower().startswith("eternal") and not found["LINK_ETER"]:
                # si hay algo después de "Eternal:" lo guardamos como texto (no ideal, pero ayuda)
                parts = ln_stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    found["LINK_ETER"] = parts[1].strip()
            if ln_stripped.lower().startswith("catharsis") and not found["LINK_CATH"]:
                parts = ln_stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    found["LINK_CATH"] = parts[1].strip()
            if ln_stripped.lower().startswith("lector") and not found["LINK_LEC"]:
                parts = ln_stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    found["LINK_LEC"] = parts[1].strip()
            if ln_stripped.lower().startswith("color") and not found["LINK_COL"]:
                parts = ln_stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    found["LINK_COL"] = parts[1].strip()

    return found

async def resolve_cath_domain(original_url: str) -> str:
    """
    Recibe un URL tomado del pin (LINK_CATH) y determina cuál dominio Catharsis funciona.
    - Primero prueba tal cual está.
    - Si no funciona, intenta reemplazar el dominio por todos los dominios de CATH_DOMAINS.
    - Si encuentra uno que responde 200, lo regresa.
    - Si ninguno funciona, devuelve el original.
    """
    if not original_url:
        return None

    # 1 — Probar el link tal cual está
    if check_alive(original_url):
        return original_url

    # 2 — Intentar con todos los dominios conocidos
    try:
        parsed = urlparse(original_url)
        original_domain = parsed.netloc.lower()
    except:
        return original_url  # si el URL no es válido, devolverlo tal cual

    for dom in CATH_DOMAINS:
        # evitar probar el mismo
        if dom == original_domain:
            continue

        test_url = url_with_domain(original_url, dom)
        if check_alive(test_url):
            return test_url

    # 3 — Si ninguno funcionó, devolver tal cual
    return original_url

# Normalizar dominio Catharsis si hace falta
def normalize_cath_link(url_or_text: str) -> str:
    if not url_or_text:
        return url_or_text
    # si es URL y contiene .dig-it.info -> reemplazar por .vxviral.xyz (ejemplo)
    corrected = url_or_text.replace(".dig-it.info", ".vxviral.xyz")
    # más reglas de normalización pueden agregarse aquí
    return corrected

# --- Construcción del diccionario final de variables ---
async def build_variables_for_channel(ctx: commands.Context, channel_input: str) -> Dict[str, Any]:
    """
    Dado el input del usuario para canal (por ejemplo "#por-tu-destino" o "<#id>"), construye
    el diccionario con todas las variables: fijas + semifijas desde sheet + semifijas desde pins.
    """
    # 1) Normalizar input
    norm = normalize_channel_name(channel_input)
    # 2) Resolver canal: puede ser id o nombre
    target_channel = None
    if re.fullmatch(r"\d+", norm):
        # es un id
        ch_id = int(norm)
        target_channel = bot.get_channel(ch_id)
    else:
        # buscar por nombre en los guilds que tenemos
        for g in bot.guilds:
            for ch in g.text_channels:
                if ch.name.lower() == norm:
                    target_channel = ch
                    break
            if target_channel:
                break

    if not target_channel:
        raise ValueError("CANAL_NO_ENCONTRADO")

    # 3) Leer sheet usando el nombre del canal tal como aparece en la hoja (col B)
    sheet_lookup = target_channel.name.lower()
    sheet_row = find_project_row_by_channel(sheet_lookup)
    if not sheet_row:
        # intentar con "#name"
        sheet_row = find_project_row_by_channel(f"#{sheet_lookup}")

    # 4) Leer pins del canal
    pin_vars = await read_channel_pins(target_channel)

    # Normalizar cath link si existe
    if pin_vars.get("LINK_CATH"):
        pin_vars["LINK_CATH"] = normalize_cath_link(pin_vars["LINK_CATH"])

    # 5) Merge final
    final = {
        # fijas
        "LINK_TELE": LINK_TELE,
        "LINK_DIS": LINK_DIS,
        "LINK_GLOBAL_ETER": LINK_GLOBAL_ETER,
        "LINK_GLOBAL_CATH": LINK_GLOBAL_CATH,
        "LINK_GLOBAL_LEC": LINK_GLOBAL_LEC,
        "LINK_GLOBAL_COL": LINK_GLOBAL_COL,
        # semifijas desde sheet (pueden ser None)
        "TITULO": sheet_row["TITULO"] if sheet_row else None,
        "SINOPSIS": sheet_row["SINOPSIS"] if sheet_row else None,
        "GENEROS": sheet_row["GENEROS"] if sheet_row else None,
        "TIPO": sheet_row["TIPO"] if sheet_row else None,
        # semifijas desde pins
        "LINK_CATH": pin_vars.get("LINK_CATH"),
        "LINK_ETER": pin_vars.get("LINK_ETER"),
        "LINK_LEC": pin_vars.get("LINK_LEC"),
        "LINK_COL": pin_vars.get("LINK_COL"),
        # detalle del canal
        "CHANNEL_OBJ": target_channel,
        "CHANNEL_NAME": target_channel.name
    }
    return final

# --- Render de plantilla_fb ---
def render_plantilla_fb(vars_dict: Dict[str, Any], cap_text: str, caps_word: str) -> str:
    """
    Rellena la plantilla_fb usando las variables encontradas.
    Si una URL no existe, simplemente NO se imprime su línea.
    """

    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    # Links dinámicos: solo agregarlos si existen
    enlaces = []
    if safe("LINK_CATH"):  enlaces.append(f"✦ {safe('LINK_CATH')}")
    if safe("LINK_ETER"):  enlaces.append(f"✦ {safe('LINK_ETER')}")
    if safe("LINK_LEC"):   enlaces.append(f"✦ {safe('LINK_LEC')}")
    if safe("LINK_COL"): enlaces.append(f"✦ {safe('LINK_COL')}")

    enlaces_texto = "\n".join(enlaces) if enlaces else "✦ [No hay enlaces]"

    titulo  = safe("TITULO")  or "[SIN_TITULO]"
    sinop   = safe("SINOPSIS") or "[SIN_SINOPSIS]"
    generos = safe("GENEROS") or "[SIN_GENEROS]"
    tipo    = safe("TIPO")    or "[SIN_TIPO]"

    texto = (
f"🌹⋆｡°✩ ˚｡⋆ 𝓐𝓬𝓽𝓾𝓪𝓵𝓲𝔃𝓪𝓬𝓲𝓸𝓷 ⋆｡°✩ ˚｡⋆🌹\n"
f"༺📘༻ **{titulo}** ༺📘༻\n"
f"┏━━━━━━༻❁༺━━━━━━┓\n"
f"🖋 {caps_word} {cap_text}\n"
f"┗━━━━━━༻❁༺━━━━━━┛\n"
f"🌐 Lectura disponible en:\n"
f"{enlaces_texto}\n"
f"꧁─────────────✧─────────────꧂\n"
f"🗝          Sinopsis\n"
f"{sinop}\n"
f"꧁─────────────✧─────────────꧂\n\n"
f"🎀 Géneros: {generos}\n"
f"📚 Formato: {tipo}\n"
f"💬 Conéctate con nosotros en Telegram y Discord:\n"
f"➤ {safe('LINK_TELE')}\n"
f"➤ {safe('LINK_DIS')}\n"
f"✦───༺♡༻───✦\n\n"
f"#CapítuloNuevo #Manhwa #BreakScan"
    )
    return texto

# --- Render de plantilla_dis ---
def render_plantilla_dis(vars_dict: Dict[str, Any], cap_text: str, caps_word: str) -> str:
    """
    Rellena la plantilla_fb usando las variables encontradas.
    Si una URL no existe, simplemente NO se imprime su línea.
    """

    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    # Links dinámicos: solo agregarlos si existen
    enlaces = []
    if safe("LINK_CATH"):  enlaces.append(f"✦ {safe('LINK_CATH')}")
    if safe("LINK_ETER"):  enlaces.append(f"✦ {safe('LINK_ETER')}")
    if safe("LINK_LEC"):   enlaces.append(f"✦ {safe('LINK_LEC')}")
    if safe("LINK_COL"): enlaces.append(f"✦ {safe('LINK_COL')}")

    enlaces_texto = "\n".join(enlaces) if enlaces else "✦ [No hay enlaces]"

    titulo  = safe("TITULO")  or "[SIN_TITULO]"
    texto_dis = (
f"🌹 𝓐𝓬𝓽𝓾𝓪𝓵𝓲𝔃𝓪𝓬𝓲𝓸𝓷 🌹\n"
f"## ༺📘༻ **{titulo}** ༺📘༻\n\n"
f"🖋 {caps_word} {cap_text}\n\n"
f"🌐 Lectura disponible en:\n"
f"{enlaces_texto}\n"
f"# Muchas gracias por su apoyo 💖\n"
    )
    return texto_dis

# --- Render de plantilla_tel ---
def render_plantilla_tel(vars_dict: Dict[str, Any], cap_text: str, caps_word: str, choice: str) -> str:
    """
    Rellena la plantilla para Telegram.
    choice: '1' -> CAPÍTULO, '2' -> CAPÍTULOS (para decidir 'YA DISPONIBLE' o 'YA DISPONIBLES')
    """
    titulo = vars_dict.get("TITULO") or "[SIN_TITULO]"
    enlaces = []
    for k in ("LINK_CATH", "LINK_ETER", "LINK_LEC", "LINK_COL"):
        v = vars_dict.get(k)
        if v: enlaces.append(v)
    enlaces_texto = "\n".join(enlaces) if enlaces else "[No hay enlaces]"

    caps_word_text = caps_word
    disponible_text = "𝔂𝓪 𝓭𝓲𝓼𝓹𝓸𝓷𝓲𝓫𝓵𝓮" if choice == "1" else "𝔂𝓪 𝓭𝓲𝓼𝓹𝓸𝓷𝓲𝓫𝓵𝓮𝓼"

    texto = (
f"✨ ¡Buenas buenas, gente hermosa! ✨\n"
f"Acabamos de actualizar\n\n"
f"💛 **{titulo}** 💛\n\n"
f"📘 {caps_word_text} {cap_text} {disponible_text}\n\n"
f"📍 LÉELO AQUÍ:\n"
f"{enlaces_texto}\n\n"
f"¡Gracias por su paciencia, por leer y por todos esos comentarios que nos motivan! 💫"
    )
    return texto

# --- Render de plantilla_cath ---
def render_plantilla_cath(vars_dict: Dict[str, Any], cap_text: str) -> str:
    """
    Rellena la plantilla_cath usando las variables encontradas.
    Si falta alguna semifija, la reemplaza por un placeholder visible.
    """
    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return f"[NO_{k}]"
        return v

    texto_cath = (
f"### 📢 <@&1339346858459402353> de: Break Scan\n"
f"# 📚 {safe('TITULO')}\n"
f"- 🔹 **Capítulo(s) actualizado:** {cap_text} 💖\n"
f"- 🔸 **Ver en:** {safe('LINK_GLOBAL_CATH')}\n"
f"## ¡Muchas gracias por el apoyo, disfrútenlo!"
    )
    return texto_cath

# --- Render de plantilla_eter ---
def render_plantilla_eter(vars_dict: Dict[str, Any], cap_text: str, caps_word_text: str) -> str:
    """
    Rellena la plantilla_eter.
    Se usa solo si existe LINK_ETER en los fijados.
    """
    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return f"[NO_{k}]"
        return v

    texto_eter = (
f"@everyone\n"
f"**{caps_word_text} {cap_text}**\n"
f"## 📖✨ **{safe('TITULO')}** ✨📖\n"
f"🔗 Link: 👉 {safe('LINK_ETER')}\n\n"
f"🎀━━━━━━━━━━━━━━━━━🎀"
    )
    return texto_eter

def render_plantilla_lec(vars_dict: Dict[str, Any], cap_text: str, caps_word_text: str) -> str:
    """
    Rellena la plantilla_lec.
    Se usa solo si existe LINK_LEC en los fijados.
    """
    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return f"[NO_{k}]"
        return v

    texto_lec = (
f"@everyone\n"
f"**{caps_word_text} {cap_text}**\n"
f"## 📖✨ **{safe('TITULO')}** ✨📖\n"
f"🔗 Link: 👉 {safe('LINK_LEC')}\n\n"
f"🎀━━━━━━━━━━━━━━━━━🎀"
    )
    return texto_lec

# --- Render de plantilla_col ---
def render_plantilla_col(vars_dict: Dict[str, Any], cap_text: str, caps_word_text: str) -> str:
    """
    Rellena la plantilla_col.
    Se usa solo si existe LINK_col en los fijados.
    """
    def safe(k):
        v = vars_dict.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return f"[NO_{k}]"
        return v

    texto_col = (
f"@everyone\n"
f"**{caps_word_text} {cap_text}**\n"
f"## 📖✨ **{safe('TITULO')}** ✨📖\n"
f"🔗 Link: 👉 {safe('LINK_COL')}\n\n"
f"🎀━━━━━━━━━━━━━━━━━🎀"
    )
    return texto_col

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
                    elif "type" in name_lower or "edi" in name_lower:
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
                "eternalmangas.org", "lectorjpg.com", "catharsisworld", "drive.google.com"
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
        pre_col = "Colorcito: 00" in msg.content

        match_eter = re.search(r"https?://(?:www\.)?eternalmangas\.org/[^\s>]+", msg.content)
        match_lec = re.search(r"https?://(?:www\.)?lectorjpg\.com/series/[^\s>]+", msg.content)
        match_cath = re.search(r"https?://(?:www\.)?catharsisworld\.[^/]+/[^\s>]+", msg.content)
        match_col = re.search(r"https?://(?:www\.)?colorcitoscan\.com/[^\s>]+", msg.content)

        if match_eter:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_eter, match_eter.group(0), preestreno=pre_eter))
        if match_lec:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_lec, match_lec.group(0), preestreno=pre_lec))
        if match_cath:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_cath, match_cath.group(0), preestreno=pre_cath))
        if match_col:
            encontrados = True
            tasks.append(asyncio.to_thread(evento_col, match_col.group(0), preestreno=pre_col))

    if not encontrados:
        embed = discord.Embed(
            title="🌸 Saku_Search — *Sin enlaces encontrados*",
            description="No hay enlaces válidos de Eternal|LectorJPG|Catharsis|Colorcito en los mensajes fijados.",
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
        "lector_date": "N/A",
        "col_cap": "N/A",
        "col_date": "N/A"
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
        elif res.startswith("COLORCITO"):
            resultado_dict["col_cap"] = cap_texto
            resultado_dict["col_date"] = dias_texto

        # Embed para mostrar al instante
        sitio_icono = {"CATHARSIS": "❤️", "ETERNAL": "🌟", "LECTORJPG": "📚", "COLORCITO": "🖍️"}.get(res.split()[0], "❓")
        embed = discord.Embed(
            title=f"{sitio_icono} {res.split()[0]}",
            description=f"Capítulo: {cap_texto}\nActualizado: {dias_texto}",
            color=obtener_color(dias_texto, res.split()[0])
        )
        await ctx.send(embed=embed)

    canal = ctx.channel.name
    categoria = ctx.channel.category.name if ctx.channel.category else "Sin categoría"
    escribir_a_hoja(canal, categoria,resultado_dict)

def escribir_a_hoja(canal, categoria, resultados):
    try:
        range_name = f"{SHEET_NAME}!A2:K"  # <-- empieza en fila 2
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
            categoria,
            resultados.get("catharsis_cap", "N/A"),
            resultados.get("catharsis_date", "N/A"),
            resultados.get("eternal_cap", "N/A"),
            resultados.get("eternal_date", "N/A"),
            resultados.get("lector_cap", "N/A"),
            resultados.get("lector_date", "N/A"),
            resultados.get("col_cap", "N/A"),
            resultados.get("col_date", "N/A")        
        ]

        body = {"values": [fila]}

        if fila_existente:
            rango_actualizar = f"{SHEET_NAME}!A{fila_existente}:K{fila_existente}"
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
        
# Comando !table
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
        range_name = f"{SHEET_NAME}!A2:K"
        resp = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = resp.get("values", [])

        if not values:
            return await ctx.send("❌ No hay datos registrados en la hoja.")

        proyectos = []
        for row in values:
            if len(row) < 10:
                continue
            canal_nombre = row[1]
            categoria = row[2] if len(row) > 2 else "Sin categoría"
            cath_date = row[4]
            eter_date = row[6]
            lec_date = row[8]
            col_date = row[10]

            urg_total = sum(
                d for d in [
                    extraer_dias(cath_date),
                    extraer_dias(eter_date),
                    extraer_dias(lec_date),
                    extraer_dias(col_date)
                ] if d is not None
            )

            proyectos.append({
                "canal": canal_nombre,
                "categoria": categoria,
                "cath_cap": row[3], "cath_date": cath_date,
                "eter_cap": row[5], "eter_date": eter_date,
                "lec_cap": row[7], "lec_date": lec_date,
                "col_cap": row[9], "col_date": col_date,
                "urg": urg_total
            })

        proyectos.sort(key=lambda x: x["urg"], reverse=True)

        total = len(proyectos)
        por_bloque = 10
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
                d_col = extraer_dias(p["col_date"])

                # obtener iconos
                i_cath = obtener_icono("CATHARSIS", d_cath)
                i_eter = obtener_icono("ETERNAL", d_eter)
                i_lec = obtener_icono("LECTOR", d_lec)
                i_col = obtener_icono("COLOR", d_col)

                texto += (
                    f"**{canal_mencion} — {p['categoria']}**\n"
                    f"{i_cath} **CATHARSIS**: {p['cath_cap']} - *({p['cath_date']})*\n"
                    f"{i_eter} **ETERNAL**: {p['eter_cap']} - *({p['eter_date']})*\n"
                    f"{i_lec} **LECTORJPG**: {p['lec_cap']} - *({p['lec_date']})*\n"
                    f"{i_col} **COLORCITO**: {p['col_cap']} - *({p['col_date']})*\n\n"
                )

            embed = discord.Embed(
                title=f"📋 Resumen de proyectos ({min(i*por_bloque, total)}/{total})",
                description=texto,
                color=0xF8C8DC
            )
            await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error al obtener los datos: {e}")
        print(f"❌ Error en !table: {e}")

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

# Comando !gen
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

# Comando !update
@bot.command(name="update")
@commands.has_guild_permissions(send_messages=True)
async def update_cmd(ctx: commands.Context):
    """
    Flujo conversacional simple:
     1) Pedir canal (#name o mención)
     2) Preguntar si es CAPÍTULO o CAPÍTULOS
     3) Pedir texto del capítulo o rango
     4) Construir variables (sheet + pins)
     5) Renderizar plantilla_fb (preview)
    """
    author = ctx.author
    timeout = 120  # segundos para que responda en cada paso

    try:
        # 1) pedir canal
        await ctx.send("Menciona el canal del que deseas plantilla de actualización con #")
        msg1 = await bot.wait_for("message", timeout=timeout, check=lambda m: m.author == author and m.channel == ctx.channel)
        channel_input = msg1.content.strip()

        # 2) pedir singular/plural
        await ctx.send("`1` para **CAPÍTULO**\n`2` para **CAPÍTULOS**.")
        msg2 = await bot.wait_for("message", timeout=timeout, check=lambda m: m.author == author and m.channel == ctx.channel)
        choice = msg2.content.strip()
        if choice not in ("1", "2"):
            await ctx.send("Entrada no válida. Se asumirá *CAPÍTULO* (singular).")
            choice = "1"

        if choice == "1":
            palabra_caps = "𝓒𝓪𝓹𝓲𝓽𝓾𝓵𝓸"
        else:
            palabra_caps = "𝓒𝓪𝓹𝓲𝓽𝓾𝓵𝓸𝓼"

        # 3) pedir el texto del capítulo/rango
        await ctx.send("Escribe el número o texto del capítulo (ej: `23`, `10 al 15`, `Especial 1`, `12 y 13`):")
        msg3 = await bot.wait_for("message", timeout=timeout, check=lambda m: m.author == author and m.channel == ctx.channel)
        cap_text = msg3.content.strip()

        # 4) construir variables
        await ctx.send("🔎 Buscando datos en la hoja y pins del canal...")
        try:
            vars_dict = await build_variables_for_channel(ctx, channel_input)
        except ValueError as e:
            if str(e) == "CANAL_NO_ENCONTRADO":
                await ctx.send("❌ No fue posible encontrar el canal indicado en los servidores del bot. Revisa que el canal exista y que esté en el mismo servidor.")
                return
            else:
                await ctx.send(f"❌ Error inesperado localizando el canal: {e}")
                return

        # 4.1 — Resolver link Catharsis con dominios alternativos si el fijado falla
        if vars_dict.get("LINK_CATH"):
            resolved_cath = await resolve_cath_domain(vars_dict["LINK_CATH"])
            vars_dict["LINK_CATH"] = resolved_cath

        # 5) render de plantillas
        texto = render_plantilla_fb(vars_dict, cap_text, palabra_caps)
        texto_dis = render_plantilla_dis(vars_dict, cap_text, palabra_caps)
        texto_tel = render_plantilla_tel(vars_dict, cap_text, palabra_caps, choice)
        texto_cath = render_plantilla_cath(vars_dict, cap_text)
        texto_eter = render_plantilla_eter(vars_dict, cap_text, palabra_caps)
        texto_lec = render_plantilla_lec(vars_dict, cap_text, palabra_caps)
        texto_col = render_plantilla_col(vars_dict, cap_text, palabra_caps)

        # 6) reportar estado de variables clave para depuración
        status_lines = []
        status_lines.append(f"Canal detectado: `{vars_dict.get('CHANNEL_NAME')}`")
        # sheet presence
        if vars_dict.get("TITULO") and vars_dict.get("SINOPSIS"):
            status_lines.append("✅ Datos encontrados en Google Sheets (TÍTULO y SINOPSIS).")
        else:
            status_lines.append("⚠ Datos incompletos en Google Sheets (TÍTULO/SINOPSIS faltantes).")

        # pins presence
        pins_info = []
        for k in ("LINK_CATH", "LINK_ETER", "LINK_LEC", "LINK_COL"):
            pins_info.append(f"{k}: {vars_dict.get(k) if vars_dict.get(k) else '[NO]'}")
            
        status_text = "\n".join(status_lines + ["Pins encontrados:"] + pins_info)

        canal_real = vars_dict.get("CHANNEL")  # este es el canal real ya encontrado
        pins = await read_channel_pins(canal_real)
        LINK_CATH = pins.get("LINK_CATH")

        if LINK_CATH:
            LINK_CATH = await resolve_cath_domain(LINK_CATH)
        
        # 7) enviar preview y status
        await ctx.send("👇 **Previsualización FACEBOOK**\n\n" + "```" + texto + "```") #siempre
        await ctx.send("👇 **Previsualización TELEGRAM**\n\n" + "```" + texto_tel + "```") #siempre
#        await ctx.send("👇 **Previsualización DISCORD**\n\n" + "```" + texto_dis + "```") #siempre
        if vars_dict.get("LINK_CATH"):
            await ctx.send("👇 **Previsualización CATHARSIS**\n\n" + "```" + texto_cath + "```") #esta sólo es cuando existe un link de catharsis
        if vars_dict.get("LINK_ETER"):
            await ctx.send("👇 **Previsualización ETERNAL**\n\n" + "```" + texto_eter + "```") #esta sólo es cuando existe un link de eternal
        if vars_dict.get("LINK_LEC"):
            await ctx.send("👇 **Previsualización LECTOR**\n\n" + "```" + texto_lec + "```") #esta sólo es cuando existe un link de lector
        if vars_dict.get("LINK_COL"):
            await ctx.send("👇 **Previsualización COLORCITOS**\n\n" + "```" + texto_col + "```") #esta sólo es cuando existe un link de colorcitos

    except asyncio.TimeoutError:
        await ctx.send(f"{author.mention} — tiempo excedido. Si quieres intentamos de nuevo con `!update`.")
    except Exception as e:
        print("Error en comando !update:", e)
        await ctx.send(f"❌ Ocurrió un error inesperado: {e}")

# Ejecutar bot
bot.run(TOKEN)
