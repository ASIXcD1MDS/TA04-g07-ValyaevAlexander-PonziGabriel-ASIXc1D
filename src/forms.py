#!/usr/bin/env python3
"""
omplir_formularis.py - TA04: envía respuestas ficticias a los Google Forms de incidencias.

Lee la estructura de cada formulario (preguntas, opciones, validaciones) y genera
respuestas coherentes según el título de cada pregunta. Con --caos, una parte de las
respuestas de texto libre se escriben en otros idiomas, en otras bases numéricas
(binario, hexadecimal, octal...), codificadas o con caracteres Unicode raros, para
probar la robustez del tratamiento de datos posterior.

Instalación:
    pip install requests faker

Uso:
    python omplir_formularis.py -n 250 URL1 URL2 URL3 URL4    # 250 por formulario
    python omplir_formularis.py -n 250 -f urls.txt            # una URL por línea
    python omplir_formularis.py --caos 0.5 URL                # 50 % de respuestas "raras"
    python omplir_formularis.py --caos 0 URL                  # todo normal
    python omplir_formularis.py --dry-run URL                 # ver preguntas y ejemplos, sin enviar
"""
import argparse
import base64
import http.cookiejar
import json
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta

import requests
from faker import Faker

VERD, VERMELL, GROC, BLAU, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[0m"

TIPUS = {0: "resposta curta", 1: "paràgraf", 2: "opció múltiple", 3: "desplegable",
         4: "caselles", 5: "escala", 7: "quadrícula", 9: "data", 10: "hora"}

# ---------------------------------------------------------------- dades multilingües
LOCALES = {"ca": "es_ES", "es": "es_ES", "en": "en_GB", "fr": "fr_FR", "de": "de_DE",
           "it": "it_IT", "pt": "pt_PT", "ja": "ja_JP", "zh": "zh_CN", "ru": "ru_RU",
           "ar": "ar_AA", "el": "el_GR"}
IDIOMES = list(LOCALES)
_fakers = {}


def fk(idioma="ca"):
    if idioma not in _fakers:
        _fakers[idioma] = Faker(LOCALES[idioma])
    return _fakers[idioma]


DESCRIPCIONS = {
    "ca": ["No s'encén l'equip", "La pantalla es queda en negre", "No té connexió a Internet",
           "La impressora s'encalla amb el paper", "El projector no detecta el senyal HDMI",
           "Funciona molt lent", "No reconeix el teclat", "Errors en iniciar sessió",
           "Fa un soroll estrany", "No s'escolta el so", "Pantalla blava en arrencar",
           "No imprimeix en color", "El ratolí no respon", "La Wi-Fi es desconnecta sovint"],
    "es": ["El equipo no se enciende", "La pantalla se queda en negro", "No tiene conexión a Internet",
           "La impresora se atasca con el papel", "El proyector no detecta la señal HDMI",
           "Funciona muy lento", "No reconoce el teclado", "No se oye el sonido"],
    "en": ["The computer won't turn on", "The screen stays black", "No Internet connection",
           "The printer keeps jamming", "The projector doesn't detect the HDMI signal",
           "It's running very slowly", "The keyboard isn't recognised", "There's no sound"],
    "fr": ["L'ordinateur ne s'allume pas", "L'écran reste noir", "Pas de connexion Internet",
           "L'imprimante bourre le papier", "Le projecteur ne détecte pas le signal HDMI",
           "Il fonctionne très lentement", "Le clavier n'est pas reconnu", "Il n'y a pas de son"],
    "de": ["Der Computer lässt sich nicht einschalten", "Der Bildschirm bleibt schwarz",
           "Keine Internetverbindung", "Der Drucker hat einen Papierstau",
           "Der Beamer erkennt das HDMI-Signal nicht", "Er läuft sehr langsam",
           "Die Tastatur wird nicht erkannt", "Es gibt keinen Ton"],
    "it": ["Il computer non si accende", "Lo schermo resta nero", "Nessuna connessione a Internet",
           "La stampante inceppa la carta", "Il proiettore non rileva il segnale HDMI",
           "Funziona molto lentamente", "La tastiera non viene riconosciuta", "Non si sente l'audio"],
    "pt": ["O computador não liga", "O ecrã fica preto", "Sem ligação à Internet",
           "A impressora encrava o papel", "O projetor não deteta o sinal HDMI",
           "Funciona muito devagar", "O teclado não é reconhecido", "Não há som"],
    "ja": ["パソコンの電源が入らない", "画面が真っ暗のまま", "インターネットに接続できない",
           "プリンターが紙詰まりする", "プロジェクターがHDMI信号を検出しない",
           "動作がとても遅い", "キーボードが認識されない", "音が出ない"],
    "zh": ["电脑无法开机", "屏幕一直是黑的", "无法连接互联网", "打印机卡纸",
           "投影仪检测不到HDMI信号", "运行非常慢", "无法识别键盘", "没有声音"],
    "ru": ["Компьютер не включается", "Экран остаётся чёрным", "Нет подключения к Интернету",
           "Принтер зажёвывает бумагу", "Проектор не видит сигнал HDMI",
           "Работает очень медленно", "Клавиатура не распознаётся", "Нет звука"],
    "ar": ["الحاسوب لا يعمل", "الشاشة تبقى سوداء", "لا يوجد اتصال بالإنترنت",
           "الطابعة تعلق الورق", "جهاز العرض لا يكتشف إشارة HDMI",
           "يعمل ببطء شديد", "لوحة المفاتيح غير معروفة", "لا يوجد صوت"],
    "el": ["Ο υπολογιστής δεν ανάβει", "Η οθόνη μένει μαύρη", "Δεν υπάρχει σύνδεση στο Διαδίκτυο",
           "Ο εκτυπωτής μπλοκάρει το χαρτί", "Ο προβολέας δεν ανιχνεύει σήμα HDMI",
           "Λειτουργεί πολύ αργά", "Το πληκτρολόγιο δεν αναγνωρίζεται", "Δεν ακούγεται ήχος"],
}
LLOCS = {"ca": ["Aula", "Aula", "Sala", "Despatx", "Laboratori"], "es": ["Aula", "Sala", "Despacho"],
         "en": ["Room", "Lab", "Office"], "fr": ["Salle", "Bureau"], "de": ["Raum", "Labor", "Büro"],
         "it": ["Aula", "Ufficio"], "pt": ["Sala", "Gabinete"], "ja": ["教室", "会議室"],
         "zh": ["教室", "办公室"], "ru": ["Кабинет", "Аудитория"], "ar": ["قاعة", "مكتب"],
         "el": ["Αίθουσα", "Γραφείο"]}
ALTRES = {
    "equip": ["Projector", "Pissarra digital", "Altaveus", "Tauleta", "Escàner", "Monitor", "Webcam"],
    "departament": ["Consergeria", "Orientació", "Cuina", "Comunicació"],
    "categoria": ["Alimentació elèctrica", "Configuració", "Llicències", "Cablejat"],
}
NUMS = {
    "ca": "zero u dos tres quatre cinc sis set vuit nou deu".split(),
    "es": "cero uno dos tres cuatro cinco seis siete ocho nueve diez".split(),
    "en": "zero one two three four five six seven eight nine ten".split(),
    "fr": "zéro un deux trois quatre cinq six sept huit neuf dix".split(),
    "de": "null eins zwei drei vier fünf sechs sieben acht neun zehn".split(),
    "ja": "〇 一 二 三 四 五 六 七 八 九 十".split(),
    "ru": "ноль один два три четыре пять шесть семь восемь девять десять".split(),
}


# ---------------------------------------------------------------- lectura del formulari
def carregar_formulari(sessio, url):
    r = sessio.get(url, timeout=20)
    r.raise_for_status()
    m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(.*?);\s*</script>", r.text, re.S)
    if not m:
        raise RuntimeError("No s'ha trobat l'estructura del formulari "
                           "(potser demana iniciar sessió o està tancat).")
    data = json.loads(m.group(1))
    titol_form = data[1][8] if len(data[1]) > 8 and data[1][8] else "(sense títol)"
    post_url = re.sub(r"/viewform.*$", "/formResponse", r.url.split("?")[0])

    preguntes, seccions = [], 0
    for item in data[1][1] or []:
        tipus = item[3]
        if tipus == 8:          # salt de secció
            seccions += 1
            continue
        if len(item) < 5 or not item[4]:   # títols, imatges, vídeos...
            continue
        for camp in item[4]:
            brut = camp[1] or []
            preguntes.append({
                "id": camp[0],
                "titol": item[1] or "",
                "tipus": tipus,
                "opcions": [o[0] for o in brut if o and o[0]],
                "altres": any(o and len(o) > 4 and o[4] == 1 for o in brut),
                "obligatori": bool(camp[2]) if len(camp) > 2 else False,
                "validacio": camp[4] if len(camp) > 4 else None,
            })
    return titol_form, post_url, preguntes, seccions


# ---------------------------------------------------------------- generació de respostes
def es_numeric(p):
    try:
        return p["validacio"][0][0] == 1
    except (TypeError, IndexError):
        return False


def numero_valid(p):
    lo, hi = 1, 30
    try:
        v = p["validacio"][0]
        sub, nums = v[1], [float(x) for x in (v[2] or [])]
        if sub in (1, 2) and nums:                 # > o >=
            lo = int(nums[0]) + (1 if sub == 1 else 0)
            hi = lo + 30
        elif sub in (3, 4) and nums:               # < o <=
            hi = int(nums[0]) - (1 if sub == 3 else 0)
            lo = min(1, hi)
        elif sub == 7 and len(nums) >= 2:          # entre
            lo, hi = int(nums[0]), int(nums[1])
        elif sub == 5 and nums:                    # igual a
            lo = hi = int(nums[0])
    except (TypeError, IndexError, ValueError):
        pass
    # La majoria d'incidències afecten poca gent: distribució esbiaixada
    return str(min(hi, max(lo, lo + int(random.expovariate(1 / 3)))))


def te(t, *claus):
    return any(k in t for k in claus)


def text_per_titol(titol, tipus=0, idioma="ca"):
    """Resposta coherent amb el títol (en català o en castellà) i en l'idioma indicat."""
    t = titol.lower()
    f = fk(idioma)
    if te(t, "correu", "correo", "email", "e-mail", "mail"):
        return fk("es").email()
    if te(t, "inventari", "inventario"):
        return f"INV-{random.randint(1, 99999):05d}"
    if te(t, "sèrie", "serie", "serial"):
        return f"SN-{random.getrandbits(40):010X}"
    if te(t, "ubicaci", "aula", "sala", "despatx", "despacho", "lloc", "lugar", "planta"):
        return f"{random.choice(LLOCS[idioma])} {random.randint(0, 4)}.{random.randint(1, 20):02d}"
    if re.search(r"\busuari\b|\busuario\b|\buser\b", t):     # singular: és una persona
        return f.name()
    if te(t, "afectat", "afectad", "quantitat", "cantidad", "quants", "cuántos", "cuantos",
          "número", "numero", "nº") or re.search(r"\bnombre d['e]", t):
        return str(random.randint(1, 30))
    if te(t, "telèfon", "telefon", "teléfono", "telefono", "mòbil", "móvil", "extensi"):
        return f.phone_number()
    if te(t, "descripci", "observaci", "comentari", "detall", "detalle", "motiu", "motivo",
          "problema", "explica"):
        frases = DESCRIPCIONS[idioma]
        if tipus == 1 and random.random() < 0.4:      # paràgraf: de vegades dues frases
            return ". ".join(random.sample(frases, 2)) + "."
        return random.choice(frases)
    if re.search(r"\bnom\b|\bnombre\b|usuari|usuario|t[eè]cnic|técnico|persona|responsable", t):
        return f.name()
    return f.word().capitalize()


def text_altres(titol):
    t = titol.lower()
    for clau, valors in ALTRES.items():
        if clau in t:
            return random.choice(valors)
    return fk().word().capitalize()


# ---------------------------------------------------------------- mode "caos"
def _digits(n, zero):
    s = str(abs(n))
    return ("-" if n < 0 else "") + "".join(chr(ord(zero) + int(c)) for c in s)


def _roma(n):
    if not 0 < n < 4000:
        return str(n)
    taula = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
             (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in taula:
        while n >= v:
            out, n = out + s, n - v
    return out


def numero_rar(n):
    """El mateix número escrit en una base, sistema o idioma diferent."""
    opcions = [bin(n), hex(n), oct(n), f"{n:b}", f"{n:X}", f"{n:o}", f"0x{n:04X}", f"{n:08b}",
               _roma(n), _digits(n, "٠"), _digits(n, "０"), _digits(n, "०"), f"{n:e}"]
    if 0 <= n <= 10:
        opcions += [NUMS[i][n] for i in NUMS]
    return random.choice(opcions)


def codificar(text):
    """El text codificat byte a byte (UTF-8) o amb escapes."""
    b = text.encode("utf-8")
    return random.choice([
        " ".join(f"{x:02x}" for x in b),                    # hexadecimal
        " ".join(f"{x:08b}" for x in b),                    # binari
        " ".join(f"{x:03o}" for x in b),                    # octal
        base64.b64encode(b).decode(),                       # base64
        text.encode("unicode_escape").decode("ascii"),      # \u00e9...
        "".join(f"&#{ord(c)};" for c in text),              # entitats HTML
    ])


HOMOGLIFS = str.maketrans("aeopcxiAEOPCXHBMT", "аеорсхіАЕОРСХНВМТ")   # ciríl·lics


def _offset(text, maj, minu, dig=None):
    out = []
    for c in text:
        if "A" <= c <= "Z":
            out.append(chr(maj + ord(c) - 65))
        elif "a" <= c <= "z":
            out.append(chr(minu + ord(c) - 97))
        elif dig and "0" <= c <= "9":
            out.append(chr(dig + ord(c) - 48))
        else:
            out.append(c)
    return "".join(out)


def estil_rar(text):
    """El mateix text, però amb caràcters Unicode poc habituals."""
    transformacions = [
        lambda s: "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else ("\u3000" if c == " " else c)
                          for c in s),                                   # amplada completa
        lambda s: _offset(s, 0x1D400, 0x1D41A, 0x1D7CE),                 # 𝐧𝐞𝐠𝐫𝐞𝐭𝐚
        lambda s: _offset(s, 0x1D4D0, 0x1D4EA),                          # 𝓮𝓼𝓬𝓻𝓲𝓹𝓽𝓪
        lambda s: _offset(s, 0x1D670, 0x1D68A, 0x1D7F6),                 # 𝚖𝚘𝚗𝚘
        lambda s: "".join(c + "".join(chr(random.randint(0x300, 0x36F))
                                      for _ in range(random.randint(1, 3))) for c in s),  # zalgo
        lambda s: "\u200b".join(s),                                      # espais d'amplada zero
        lambda s: s.translate(HOMOGLIFS),                                # homoglifs
        lambda s: f"{s} {''.join(random.choices('💻🖥️🖨️⚠️🔥❌✅🤔🙃📡🔌', k=random.randint(1, 3)))}",
        lambda s: "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(s)),
        lambda s: f"  {s}\t ",                                           # espais sobrants
        lambda s: f'"{s}"; ,\\ «»',                                      # trenca-CSV
        lambda s: s.upper() + "!!!",
    ]
    return random.choice(transformacions)(text)


# Fragments que trenquen parsers de llenguatges de marques / formats de dades
TRENCA_FORMAT = {
    "xml": ['<', '>', '&', '&amp;', '&nbsp;', '&#x0;', ']]>', '<![CDATA[', '<?xml version="1.0"?>',
            '</resposta>', '<a href="x">', "'\"", '<!-- ', ' -->', '<!DOCTYPE x>', '&undefined;'],
    "html": ['<b>', '</div>', '<br>', '<img src=x>', '<!--', '&lt;', '<p', '</>', '<<>>'],
    "csv": [',', ';', '"', '""', '","', '\t', '\n', '\r\n', '\r', '=1+1', '+1', '-1', '@x',
            'a,"b,c",d', '|', 'sep=;'],
    "json": ['"', '\\', '\\"', '{', '}', '[', ']', '{"a":', '":null}', '\\u0000', '\\n', 'NaN',
             'undefined', '/*', '//', ' ', ' '],
    "yaml": [': ', '- ', '# ', '---', '...', '&ancora', '*ancora', '!!python/str', '? ', '|',
             '>-', '%YAML', 'yes', 'no', 'null', '~', '@', '`'],
    "sql": ["'", "''", "';", '--', '/*', '*/', '%', '_', '\\', "O'Brien"],
    "markdown": ['|', '**', '__', '`', '```', '# ', '> ', '[x](y)', '\\*', '<!-- -->'],
    "plantilles": ['${x}', '{{x}}', '{%x%}', '#{x}', '%s', '%d', '{0}', '$1', '<%= x %>'],
    "unicode": ['﻿', '‮', '‭', '​', ' ', '\u0085', '\u000b', '\u000c',
                '\u0007', '\u001b[31m', '�', '\U0001F4A9', 'é', '퟿', '\u0000'],
}


def trencar_format(text, extrem=False):
    """Barreja el text amb caràcters/fragments problemàtics per a XML, CSV, JSON, YAML...
    Amb `extrem`, fa servir tots els formats i més fragments per format."""
    if extrem:
        fmts, rang = list(TRENCA_FORMAT), (2, 4)
    else:
        fmts, rang = random.sample(list(TRENCA_FORMAT), random.randint(1, 3)), (1, 3)
    trossos = [random.choice(TRENCA_FORMAT[f]) for f in fmts for _ in range(random.randint(*rang))]
    paraules = text.split(" ")
    for t in trossos:
        paraules.insert(random.randint(0, len(paraules)), t)
    return " ".join(paraules)


def distorsionar(valor, p, caos, marques=0.0):
    """Amb probabilitat `caos`, converteix una resposta de text en una de 'rara'.
    Amb probabilitat `marques`, hi injecta caràcters que trenquen XML/CSV/JSON/YAML..."""
    if p["validacio"]:
        return valor               # amb validació, Google rebutjaria el valor
    if marques >= 1:               # mode extrem: Unicode rar + tots els formats alhora
        return trencar_format(estil_rar(valor), extrem=True)
    if marques > 0 and random.random() < marques:
        return trencar_format(valor)
    if caos <= 0 or random.random() >= caos:
        return valor
    if re.fullmatch(r"-?\d+", valor):
        return numero_rar(int(valor))
    if p["tipus"] == 1 and random.random() < 0.2:
        valor = valor + "\n\n" + random.choice(DESCRIPCIONS[random.choice(IDIOMES)])
    return codificar(valor) if random.random() < 0.35 else estil_rar(valor)


def triar(opcions):
    # Pes decreixent: les primeres opcions surten més, així les estadístiques són més interessants
    pesos = [len(opcions) - i + 2 for i in range(len(opcions))]
    return random.choices(opcions, weights=pesos)[0]


def generar_resposta(preguntes, caos=0.3, prob_altres=0.07, marques=0.0):
    dades = {}
    # Cada resposta la "escriu" una persona: la majoria en català, algunes en altres idiomes
    idioma = random.choice(IDIOMES) if random.random() < caos else "ca"
    for p in preguntes:
        k, t = f"entry.{p['id']}", p["tipus"]
        if t in (0, 1):
            if es_numeric(p):
                dades[k] = numero_valid(p)
            else:
                dades[k] = distorsionar(text_per_titol(p["titol"], t, idioma), p, caos, marques)
        elif t in (2, 3, 5, 7):
            if t == 2 and p["altres"] and random.random() < prob_altres:
                dades[k] = "__other_option__"
                dades[k + ".other_option_response"] = distorsionar(text_altres(p["titol"]), p, caos, marques)
            elif p["opcions"]:
                dades[k] = triar(p["opcions"])     # ha de coincidir exactament amb l'opció
        elif t == 4 and p["opcions"]:
            dades[k] = random.sample(p["opcions"], random.randint(1, min(2, len(p["opcions"]))))
        elif t == 9:
            d = date.today() - timedelta(days=random.randint(0, 180))
            dades[k + "_year"], dades[k + "_month"], dades[k + "_day"] = d.year, d.month, d.day
        elif t == 10:
            dades[k + "_hour"] = f"{random.randint(8, 20):02d}"
            dades[k + "_minute"] = f"{random.choice([0, 15, 30, 45]):02d}"
    return dades


# ---------------------------------------------------------------- registre d'errors
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logform.log")


def log_error(url, missatge, dades=None):
    """Afegeix un error a logform.log (mateixa carpeta que el script)."""
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {url}\n  {missatge}\n")
        if dades is not None:
            fh.write(f"  dades: {json.dumps(dades, ensure_ascii=False, default=str)}\n")


# ---------------------------------------------------------------- enviament
def enviar(sessio, post_url, dades, seccions, intents=3):
    payload = dict(dades)
    payload["fvv"] = "1"
    payload["pageHistory"] = ",".join(str(i) for i in range(seccions + 1))
    for intent in range(intents):
        try:
            r = sessio.post(post_url, data=payload, timeout=20)
        except requests.RequestException as e:     # error de xarxa: esperar i reintentar
            if intent == intents - 1:
                return f"error de xarxa: {e}"
            time.sleep(5 * (intent + 1))
            continue
        if r.status_code == 429:          # massa peticions: esperar i reintentar
            time.sleep(10 * (intent + 1))
            continue
        return r.status_code
    return 429


def processar(sessio, url, n, retard, dry_run, caos, marques=0.0):
    print(f"\n{BLAU}{'=' * 60}\n{url}{RESET}")
    try:
        titol, post_url, preguntes, seccions = carregar_formulari(sessio, url)
    except Exception as e:
        print(f"{VERMELL}✗ {e}{RESET}")
        log_error(url, f"No s'ha pogut carregar el formulari: {e}")
        return 0, 0

    print(f"Formulari: {titol}  |  {len(preguntes)} preguntes  |  {seccions + 1} secció/ns")
    for p in preguntes:
        extra = " [nombre]" if es_numeric(p) else ""
        extra += " [validació]" if p["validacio"] and not es_numeric(p) else ""
        extra += " [+Altres]" if p["altres"] else ""
        print(f"  · {p['titol']:<30} {TIPUS.get(p['tipus'], p['tipus'])}{extra}")

    if dry_run:
        print(f"\n{GROC}Exemples de resposta (no s'envien, caos={caos}):{RESET}")
        for _ in range(3):
            print(json.dumps(generar_resposta(preguntes, caos, marques=marques), ensure_ascii=False, indent=2))
        return 0, 0

    ok = errors = 0
    for i in range(1, n + 1):
        dades = generar_resposta(preguntes, caos, marques=marques)
        codi = enviar(sessio, post_url, dades, seccions)
        if codi in (401, 403) and getattr(sessio, "recarregar", None):
            sessio.recarregar()          # el navegador pot haver renovat les cookies
            codi = enviar(sessio, post_url, dades, seccions)
        if codi == 200:
            ok += 1
        else:
            errors += 1
            log_error(url, f"Resposta {i}/{n}: {codi if isinstance(codi, str) else f'HTTP {codi}'}", dades)
            if codi in (401, 403):
                print(f"\n{VERMELL}✗ Error {codi}: el formulari exigeix iniciar sessió. "
                      f"Atura't aquí.{RESET}")
                break
        print(f"\r  {i}/{n}  {VERD}✓ {ok}{RESET}  {VERMELL}✗ {errors}{RESET}", end="", flush=True)
        time.sleep(random.uniform(*retard))
    print()
    return ok, errors


def main():
    ap = argparse.ArgumentParser(description="Omplir Google Forms amb incidències fictícies")
    ap.add_argument("urls", nargs="*", help="URLs dels formularis (forms.gle o viewform)")
    ap.add_argument("-f", "--fitxer", help="Fitxer amb una URL per línia")
    ap.add_argument("-n", type=int, default=100, help="Respostes per formulari (defecte 100)")
    ap.add_argument("--min", type=float, default=0.5, help="Retard mínim entre enviaments (s)")
    ap.add_argument("--max", type=float, default=1.5, help="Retard màxim entre enviaments (s)")
    ap.add_argument("--caos", type=float, default=0.3,
                    help="Proporció de respostes de text 'rares': altres idiomes, binari, hex, "
                         "octal, Unicode... (0 = desactivat, 1 = totes). Defecte 0.3")
    ap.add_argument("--marques", type=float, default=0.0,
                    help="Proporció de respostes de text amb caràcters que trenquen XML, CSV, JSON, "
                         "YAML, HTML, SQL, Markdown... (0 = desactivat, 1 = totes en mode extrem). Defecte 0")
    ap.add_argument("--seed", type=int, help="Llavor aleatòria per obtenir resultats repetibles")
    ap.add_argument("--dry-run", action="store_true", help="Només analitza, no envia res")
    ap.add_argument("--cookies", help="Fitxer cookies.txt (format Netscape) amb la sessió de Google "
                                      "per a formularis restringits a l'organització")
    ap.add_argument("--chromium", action="store_true",
                    help="Fes servir la sessió de Google oberta al Chromium (requereix browser_cookie3)")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)

    urls = list(args.urls)
    if args.fitxer:
        with open(args.fitxer, encoding="utf-8") as fh:
            urls += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    if not urls:
        ap.error("Cal indicar almenys una URL")

    sessio = requests.Session()
    sessio.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) TA04-ITB"
    if args.cookies:
        jar = http.cookiejar.MozillaCookieJar(args.cookies)
        jar.load(ignore_discard=True, ignore_expires=True)
        sessio.cookies = jar
    elif args.chromium:
        import browser_cookie3
        sessio.recarregar = lambda: setattr(
            sessio, "cookies", browser_cookie3.chromium(domain_name="google.com"))
        sessio.recarregar()

    total_ok = total_err = 0
    for url in urls:
        ok, err = processar(sessio, url, args.n, (args.min, args.max), args.dry_run, args.caos, args.marques)
        total_ok, total_err = total_ok + ok, total_err + err

    if not args.dry_run:
        print(f"\n{'=' * 60}\nTOTAL: {VERD}{total_ok} correctes{RESET}, "
              f"{VERMELL}{total_err} errors{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterromput.")