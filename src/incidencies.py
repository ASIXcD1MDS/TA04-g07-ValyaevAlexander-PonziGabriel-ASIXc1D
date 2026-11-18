#!/usr/bin/env python3
"""
incidencies.py - TA04 · Part 3: processar les dades i mostrar-les per pantalla.

Llegeix el fitxer XML d'incidències, DESCODIFICA i NETEJA els camps "raros"
(binari, octal, hexadecimal, base64, entitats HTML, \\xNN, caràcters invisibles,
text "zalgo", lletres matemàtiques, amplada completa, homoglifs ciríl·lics,
emojis...), VALIDA cada incidència (dates impossibles, valors fora de rang,
spam...) i en treu ESTADÍSTIQUES.

Només fa servir la biblioteca estàndard de Python (no cal instal·lar res).

Ús:
    python3 incidencies.py                       # informe a la consola
    python3 incidencies.py -f altres.xml         # un altre fitxer
    python3 incidencies.py --dept Docència       # filtrar per departament
    python3 incidencies.py --cerca impressora    # cerca de text lliure
    python3 incidencies.py --descartades         # llista de dades descartades i per què
    python3 incidencies.py --web                 # genera informe.html i l'obre al navegador
"""
import argparse
import base64
import binascii
import codecs
import collections
import datetime as dt
import html
import json
import os
import re
import shutil
import statistics
import sys
import unicodedata
import warnings
import webbrowser
import xml.etree.ElementTree as ET

CAMPS = [
    "marca_temporal", "data_de_la_incidencia", "usuari_afectat", "departament",
    "tipus_dequip", "ubicacio", "numero_dinventari", "categoria_de_lavaria",
    "descripcio_de_la_incidencia", "usuaris_afectats", "contacte_del_tecnic_assignat",
]
CATEGORICS = ["departament", "tipus_dequip", "categoria_de_lavaria"]

# ════════════════════════════════════════════════════════════════════════════
# 1. LECTURA ROBUSTA DE L'XML
# ════════════════════════════════════════════════════════════════════════════

# Caràcters que XML 1.0 no permet (control, surrogates...)
_XML_PROHIBITS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def llegir_xml(ruta):
    """Torna una llista de diccionaris.

    Primer intenta llegir en streaming amb iterparse (poca memòria encara que
    el fitxer sigui enorme). Si l'XML està trencat, el repara i ho torna a provar.
    """
    try:
        registres = []
        for _, elem in ET.iterparse(ruta, events=("end",)):
            if elem.tag == "incidencia":
                r = {"id": elem.get("id", str(len(registres) + 1))}
                for camp in CAMPS:
                    r[camp] = elem.findtext(camp) or ""
                registres.append(r)
                elem.clear()                       # alliberar memòria del node
        return registres
    except ET.ParseError:
        pass

    with open(ruta, "rb") as f:
        text = f.read().decode("utf-8", errors="replace")   # bytes no UTF-8 → �
    text = _XML_PROHIBITS.sub("", text)
    text = re.sub(r"&(?!#\d+;|#x[0-9a-fA-F]+;|[a-zA-Z]+;)", "&amp;", text)
    try:
        arrel = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        return llegir_xml_a_ma(text)
    registres = []
    for inc in arrel.iter("incidencia"):
        r = {"id": inc.get("id", str(len(registres) + 1))}
        for camp in CAMPS:
            r[camp] = inc.findtext(camp) or ""
        registres.append(r)
    return registres


def llegir_xml_a_ma(text):
    """Últim recurs: extreure les incidències amb expressions regulars."""
    registres = []
    for m in re.finditer(r'<incidencia(?:\s+id="([^"]*)")?>(.*?)</incidencia>', text, re.S):
        r = {"id": m.group(1) or str(len(registres) + 1)}
        for camp in CAMPS:
            c = re.search(rf"<{camp}>(.*?)</{camp}>", m.group(2), re.S)
            r[camp] = html.unescape(c.group(1)) if c else ""
        registres.append(r)
    return registres


# ════════════════════════════════════════════════════════════════════════════
# 2. DESCODIFICACIÓ I NETEJA DE TEXT
# ════════════════════════════════════════════════════════════════════════════

_RE_BIN = re.compile(r"[01]{8}(?: [01]{8})*")
_RE_OCT = re.compile(r"[0-3][0-7]{2}(?: [0-3][0-7]{2})+")
_RE_HEX = re.compile(r"[0-9a-fA-F]{2}(?: [0-9a-fA-F]{2})+")
_RE_B64 = re.compile(r"[A-Za-z0-9+/]{8,}={0,2}")
_RE_ESC = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[ntr])")
_RE_EMBOLCALL = re.compile(r'^"(.*)";\s*,\\\s*«»$', re.S)
_MORSE = dict(zip(
    ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- "
    "-..- -.-- --.. ----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----. .-.-.- --..-- -....- "
    "..--.. -.-.-- .----. -..-. ---... -.--. -.--.-".split(),
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-?!'/:()"))
_INVISIBLES = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad\ufe0e\ufe0f\u034f"))

# Lletres ciríl·liques que semblen llatines (homoglifs)
_HOMOGLIFS = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "у": "y", "х": "x", "і": "i", "І": "I", "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l",
})


def _text_llegible(t):
    """Comprova que un text descodificat té sentit (no són bytes aleatoris)."""
    if not t or "\ufffd" in t:
        return False
    imprimibles = sum(ch.isprintable() or ch in "\n\t" for ch in t)
    lletres = sum(ch.isalpha() or ch.isspace() or ch in ".,-'’:()" or ch.isdigit() for ch in t)
    return imprimibles == len(t) and lletres / len(t) > 0.8


def _bytes_a_text(nombres):
    try:
        t = bytes(nombres).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None
    return t if _text_llegible(t) else None


def descodificar(text):
    """Torna (text_net, [trucs_detectats])."""
    trucs = []
    t = (text or "").strip()

    for _ in range(4):          # pot haver-hi codificacions dins de codificacions
        anterior = t

        m = _RE_EMBOLCALL.match(t)                      # "X"; ,\ «»
        if m:
            t = m.group(1).strip(); trucs.append("cometes/brossa")

        if "&#" in t or re.search(r"&[a-z]+;", t):      # &#67;&#117;...
            nou = html.unescape(t)
            if nou != t:
                t = nou; trucs.append("entitats HTML")

        if _RE_BIN.fullmatch(t):                        # 01000001 01101100 ...
            d = _bytes_a_text(int(x, 2) for x in t.split())
            if d: t = d; trucs.append("binari")
        elif _RE_OCT.fullmatch(t):                      # 103 141 142 ...
            d = _bytes_a_text(int(x, 8) for x in t.split())
            if d: t = d; trucs.append("octal")
        elif _RE_HEX.fullmatch(t):                      # 4c 61 6c 6f ...
            d = _bytes_a_text(int(x, 16) for x in t.split())
            if d: t = d; trucs.append("hexadecimal")
        elif _RE_B64.fullmatch(t) and len(t) % 4 == 0:  # QWx0YXZldXM=
            try:
                d = _bytes_a_text(base64.b64decode(t, validate=True))
            except (binascii.Error, ValueError):
                d = None
            if d and d != t:
                t = d; trucs.append("base64")

        fitxes = t.split()                              # .- -... --- ..- -  (Morse)
        if len(fitxes) >= 3 and sum(f in _MORSE or f == "/" for f in fitxes) / len(fitxes) > 0.8:
            linies = []
            for linia in t.split("\n"):
                paraules = [w.split() for w in linia.split("/")]
                linies.append(" ".join("".join(_MORSE.get(l, l) for l in w) for w in paraules))
            t = "\n".join(linies).capitalize()
            trucs.append("Morse")

        if _RE_ESC.search(t):                           # \xe9  \u039c  \n
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    nou = codecs.decode(t.encode("latin-1", "backslashreplace"), "unicode_escape")
                if nou != t:
                    t = nou; trucs.append("seqüències d'escapament")
            except (UnicodeDecodeError, ValueError):
                pass

        if t == anterior:
            break

    # Caràcters invisibles (espais d'amplada zero, selectors de variació...)
    nou = t.translate(_INVISIBLES)
    if nou != t:
        t = nou; trucs.append("caràcters invisibles")

    # Text "zalgo": massa marques diacrítiques combinades
    nfd = unicodedata.normalize("NFD", t)
    marques = sum(1 for ch in nfd if unicodedata.combining(ch))
    bases = sum(1 for ch in nfd if not unicodedata.combining(ch) and not ch.isspace())
    if bases and marques / bases > 0.35:
        t = "".join(ch for ch in nfd if not unicodedata.combining(ch))
        trucs.append("text zalgo")

    # Lletres matemàtiques 𝓒𝓸𝓷, amplada completa Ｃｏｎ...
    nou = unicodedata.normalize("NFKC", t)
    if nou != unicodedata.normalize("NFC", t):
        trucs.append("Unicode estilitzat")
    t = nou

    # Homoglifs: només a les paraules que barregen lletres llatines i ciríl·liques
    # (així un text rus de veritat, com "Компьютер не включается", no es toca)
    def _paraula(m):
        w = m.group(0)
        if re.search(r"[A-Za-zÀ-ÿ]", w) and re.search(r"[\u0400-\u04FF]", w):
            return w.translate(_HOMOGLIFS)
        return w
    nou = re.sub(r"\w+", _paraula, t)
    # ...i paraules d'una sola lletra ("а", "О") dins d'una frase en alfabet llatí
    if len(re.findall(r"[A-Za-zÀ-ÿ]", nou)) > 2 * len(re.findall(r"[\u0400-\u04FF]", nou)):
        nou = re.sub(r"(?<!\w)[АаОоЕеСсУуІі](?!\w)", lambda m: m.group(0).translate(_HOMOGLIFS), nou)
    if nou != t:
        t = nou; trucs.append("homoglifs ciríl·lics")

    # Emojis i símbols pictogràfics
    nou = "".join(ch for ch in t if unicodedata.category(ch) not in ("So", "Cs", "Co", "Cn")
                  and (unicodedata.category(ch) != "Cc" or ch in "\n\t"))
    if nou != t:
        t = nou; trucs.append("emojis")

    # Signes repetits al final: "INV-21011!!!", "CONFIGURACIÓ!!!"
    nou = re.sub(r"\s*!{2,}$", "", t)
    if nou != t:
        t = nou; trucs.append("majúscules/signes")

    # Espais
    t = re.sub(r"[ \t\u3000]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t, trucs


# Per comparar: tot en minúscules i els homoglifs ciríl·lics passats a llatí
_HOMOGLIFS_CLAU = str.maketrans("аеорсухіјѕԁӏкмнтв", "aeopcyxijsdlkmhtb")


def clau(text):
    """Clau per comparar valors: sense accents ni majúscules, només lletres i números."""
    t = unicodedata.normalize("NFKD", text.casefold()).translate(_HOMOGLIFS_CLAU)
    return re.sub(r"[\W_]", "", "".join(ch for ch in t if not unicodedata.combining(ch)))


# ════════════════════════════════════════════════════════════════════════════
# 3. DETECCIÓ D'IDIOMA (heurística, sense llibreries)
# ════════════════════════════════════════════════════════════════════════════

_PARAULES = {
    "ca": "amb molt no s l d el la es queda encén equip ratolí teclat so escolta impressora "
          "connexió té sovint arrencar errors iniciar sessió imprimeix fa soroll estrany senyal "
          "negre blava reconeix respon encalla paper",
    "es": "con muy no se el la queda enciende equipo ratón teclado sonido oye impresora conexión "
          "tiene menudo arrancar errores iniciar sesión imprime hace ruido extraño señal negro azul "
          "reconoce responde atasca papel funciona lento",
    "en": "the is not does with no keyboard mouse screen printer sound turn on slow internet connection "
          "error errors login black blue noise strange signal paper jams recognised recognized",
    "pt": "não o a com muito teclado ecrã tela impressora som liga devagar ligação conexão "
          "reconhecido deteta sinal papel encrava",
    "fr": "ne pas le la l s allume avec très clavier écran imprimante son lent connexion "
          "reconnu détecte signal bourre papier",
    "it": "non si il la con molto tastiera schermo stampante audio sente lento connessione "
          "nessuna riconosciuta rileva segnale inceppa carta",
    "de": "der die das nicht wird mit sehr tastatur bildschirm drucker ton langsam keine "
          "verbindung erkannt signal papier",
}
_PARAULES = {k: set(v.split()) for k, v in _PARAULES.items()}
_ESCRIPTURES = [
    (r"[\u3040-\u30ff]", "ja"), (r"[\uac00-\ud7af]", "ko"), (r"[\u4e00-\u9fff]", "zh"),
    (r"[\u0400-\u04ff]", "ru"), (r"[\u0600-\u06ff]", "ar"), (r"[\u0370-\u03ff]", "el"),
    (r"[\u1200-\u137f]", "am"), (r"[\u0590-\u05ff]", "he"), (r"[\u0e00-\u0e7f]", "th"),
    (r"[\u0900-\u097f]", "hi"),
]


def detectar_idioma(text):
    primer = text.split("\n")[0]
    for patro, codi in _ESCRIPTURES:        # japonès abans que xinès (comparteixen kanji)
        if re.search(patro, primer):
            return codi
    paraules = re.findall(r"[a-zà-ÿ]+", primer.lower().replace("’", "'").replace("'", " "))
    if not paraules:
        return "?"
    punts = {codi: sum(p in conj for p in paraules) for codi, conj in _PARAULES.items()}
    millor = max(punts, key=punts.get)
    return millor if punts[millor] else "?"


IDIOMES = {"ca": "Català", "es": "Castellà", "en": "Anglès", "pt": "Portuguès", "fr": "Francès",
           "it": "Italià", "de": "Alemany", "ja": "Japonès", "zh": "Xinès", "ko": "Coreà",
           "ru": "Rus", "ar": "Àrab", "el": "Grec", "am": "Amhàric/Ge'ez", "he": "Hebreu",
           "th": "Tai", "hi": "Hindi", "?": "Desconegut"}


# ════════════════════════════════════════════════════════════════════════════
# 3b. PROBLEMES CANÒNICS: la mateixa avaria escrita en 12 idiomes
# ════════════════════════════════════════════════════════════════════════════
# Cada problema té un identificador i la frase amb què apareix en cada idioma.
# Així "No reconeix el teclat", "キーボードが認識されない" i "Die Tastatur wird nicht
# erkannt" compten com EL MATEIX problema, i podem traduir qualsevol descripció.

PROBLEMES = {
    "pantalla_blava": {"ca": "Pantalla blava en arrencar", "es": "Pantalla azul al arrancar", "en": "Blue screen on startup"},
    "teclat": {"ca": "No reconeix el teclat", "es": "No reconoce el teclado", "en": "The keyboard isn't recognised",
               "fr": "Le clavier n'est pas reconnu", "pt": "O teclado não é reconhecido", "de": "Die Tastatur wird nicht erkannt",
               "it": "La tastiera non viene riconosciuta", "el": "Το πληκτρολόγιο δεν αναγνωρίζεται", "ru": "Клавиатура не распознаётся",
               "ja": "キーボードが認識されない", "zh": "无法识别键盘", "ar": "لوحة المفاتيح غير معروفة"},
    "impressora_paper": {"ca": "La impressora s'encalla amb el paper", "es": "La impresora se atasca con el papel", "en": "The printer keeps jamming",
               "fr": "L'imprimante bourre le papier", "pt": "A impressora encrava o papel", "de": "Der Drucker hat einen Papierstau",
               "it": "La stampante inceppa la carta", "el": "Ο εκτυπωτής μπλοκάρει το χαρτί", "ru": "Принтер зажёвывает бумагу",
               "ja": "プリンターが紙詰まりする", "zh": "打印机卡纸", "ar": "الطابعة تعلق الورق"},
    "soroll": {"ca": "Fa un soroll estrany", "es": "Hace un ruido extraño", "en": "It makes a strange noise"},
    "wifi": {"ca": "La Wi-Fi es desconnecta sovint", "es": "La Wi-Fi se desconecta a menudo", "en": "The Wi-Fi keeps disconnecting"},
    "pantalla_negra": {"ca": "La pantalla es queda en negre", "es": "La pantalla se queda en negro", "en": "The screen stays black",
               "fr": "L'écran reste noir", "pt": "O ecrã fica preto", "de": "Der Bildschirm bleibt schwarz",
               "it": "Lo schermo resta nero", "el": "Η οθόνη μένει μαύρη", "ru": "Экран остаётся чёрным",
               "ja": "画面が真っ暗のまま", "zh": "屏幕一直是黑的", "ar": "الشاشة تبقى سوداء"},
    "projector": {"ca": "El projector no detecta el senyal HDMI", "es": "El proyector no detecta la señal HDMI",
               "en": "The projector doesn't detect the HDMI signal", "fr": "Le projecteur ne détecte pas le signal HDMI",
               "pt": "O projetor não deteta o sinal HDMI", "de": "Der Beamer erkennt das HDMI-Signal nicht",
               "it": "Il proiettore non rileva il segnale HDMI", "el": "Ο προβολέας δεν ανιχνεύει σήμα HDMI",
               "ru": "Проектор не видит сигнал HDMI", "ja": "プロジェクターがHDMI信号を検出しない", "zh": "投影仪检测不到HDMI信号",
               "ar": "جهاز العرض لا يكتشف إشارة HDMI"},
    "so": {"ca": "No s'escolta el so", "es": "No se oye el sonido", "en": "There's no sound", "fr": "Il n'y a pas de son",
               "pt": "Não há som", "de": "Es gibt keinen Ton", "it": "Non si sente l'audio", "el": "Δεν ακούγεται ήχος",
               "ru": "Нет звука", "ja": "音が出ない", "zh": "没有声音", "ar": "لا يوجد صوت"},
    "no_encen": {"ca": "No s'encén l'equip", "es": "El equipo no se enciende", "en": "The computer won't turn on",
               "fr": "L'ordinateur ne s'allume pas", "pt": "O computador não liga", "de": "Der Computer lässt sich nicht einschalten",
               "it": "Il computer non si accende", "el": "Ο υπολογιστής δεν ανάβει", "ru": "Компьютер не включается",
               "ja": "パソコンの電源が入らない", "zh": "电脑无法开机", "ar": "الحاسوب لا يعمل"},
    "internet": {"ca": "No té connexió a Internet", "es": "No tiene conexión a Internet", "en": "No Internet connection",
               "fr": "Pas de connexion Internet", "pt": "Sem ligação à Internet", "de": "Keine Internetverbindung",
               "it": "Nessuna connessione a Internet", "el": "Δεν υπάρχει σύνδεση στο Διαδίκτυο", "ru": "Нет подключения к Интернету",
               "ja": "インターネットに接続できない", "zh": "无法连接互联网", "ar": "لا يوجد اتصال بالإنترنت"},
    "color": {"ca": "No imprimeix en color", "es": "No imprime en color", "en": "It doesn't print in colour"},
    "ratoli": {"ca": "El ratolí no respon", "es": "El ratón no responde", "en": "The mouse doesn't respond"},
    "sessio": {"ca": "Errors en iniciar sessió", "es": "Errores al iniciar sesión", "en": "Errors when signing in"},
    "lent": {"ca": "Funciona molt lent", "es": "Funciona muy lento", "en": "It's running very slowly",
               "fr": "Il fonctionne très lentement", "pt": "Funciona muito devagar", "de": "Er läuft sehr langsam",
               "it": "Funziona molto lentamente", "el": "Λειτουργεί πολύ αργά", "ru": "Работает очень медленно",
               "ja": "動作がとても遅い", "zh": "运行非常慢", "ar": "يعمل ببطء شديد"},
}
# Índex invers: clau(frase) → (problema, idioma, frase ben escrita)
_INDEX_PROBLEMES = {}
for _pid, _variants in PROBLEMES.items():
    for _idioma, _frase in _variants.items():
        _INDEX_PROBLEMES.setdefault(clau(_frase), (_pid, _idioma, _frase))


def analitzar_descripcio(text):
    """Divideix la descripció en frases i reconeix cada problema.

    Torna (descripció ben escrita, [problemes], [idiomes], canviat?).
    Les frases que no són al diccionari es deixen tal qual i compten com a
    problema propi (text lliure).
    """
    frases, problemes, idiomes = [], [], []
    for frase in re.split(r"[.\n。]+", text):
        frase = frase.strip()
        if len(frase) < 2:
            continue
        trobat = _INDEX_PROBLEMES.get(clau(frase))
        if trobat:
            pid, idioma, neta = trobat
            frases.append(neta); problemes.append(pid); idiomes.append(idioma)
        else:
            frases.append(frase); problemes.append(frase)
            idiomes.append(detectar_idioma(frase))
    nova = ". ".join(frases) + ("." if len(frases) > 1 else "")
    original = re.sub(r"\s*[.\n。]+\s*", ". ", text).strip(" .") + ("." if len(frases) > 1 else "")
    return nova, problemes, idiomes, nova != original


# ════════════════════════════════════════════════════════════════════════════
# 4. NETEJA + VALIDACIÓ  (DADES → INFORMACIÓ)
# ════════════════════════════════════════════════════════════════════════════

def _data(text):
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}):(\d{2}))?", text.strip())
    if not m:
        return None
    try:
        nums = [int(x) if x else 0 for x in m.groups()]
        return dt.datetime(nums[2], nums[1], nums[0], nums[3], nums[4], nums[5])
    except ValueError:
        return None


def processar(registres):
    # a) Descodificar tots els camps
    for r in registres:
        r["original"] = {c: r[c] for c in CAMPS}
        r["trucs"] = {}
        for c in CAMPS:
            net, trucs = descodificar(r[c])
            r[c] = net
            if trucs:
                r["trucs"][c] = trucs

    # b) Valors canònics dels camps categòrics: els que apareixen 3+ vegades
    canonics = {}
    for c in CATEGORICS:
        per_clau = collections.defaultdict(collections.Counter)
        for r in registres:
            per_clau[clau(r[c])][r[c]] += 1
        canonics[c] = {k: cnt.most_common(1)[0][0]
                       for k, cnt in per_clau.items() if k and sum(cnt.values()) >= 3}

    # Números d'inventari: "iNv-03221", "INV 86813" → "INV-03221", "INV-86813"
    for r in registres:
        m = re.fullmatch(r"(?i)\s*inv\s*[-_ ]?\s*(\d+)\s*", r["numero_dinventari"])
        if m and r["numero_dinventari"] != f"INV-{m.group(1)}":
            r["numero_dinventari"] = f"INV-{m.group(1)}"
            r["trucs"].setdefault("numero_dinventari", []).append("majúscules/signes")

    # Ubicacions: unificar variants ("LABORATORI 0.18!!!", "aUlA 3.12" → la forma més habitual)
    variants = collections.defaultdict(collections.Counter)
    for r in registres:
        variants[clau(r["ubicacio"])][r["ubicacio"]] += 1
    paraules = collections.Counter(w for r in registres for w in r["ubicacio"].split()[:1])
    for r in registres:
        # primer les variants amb majúscules "normals", i d'aquestes la més freqüent
        forma = max(variants[clau(r["ubicacio"])].items(),
                    key=lambda kv: (not (kv[0].isupper() or re.search(r"[a-z][A-Z]", kv[0])
                                         or kv[0].endswith("!")), kv[1]))[0]
        if forma == r["ubicacio"] and (r["ubicacio"].isupper() or re.search(r"[a-z][A-Z]", r["ubicacio"])
                                       or r["ubicacio"].endswith("!")):
            # Si no hi ha cap variant neta, reconstruir-la: "Aula 3.12"
            m = re.match(r"(\w+)\W*\s+([\d.]+)", r["ubicacio"])
            if m:
                nom = max((w for w in paraules if w.casefold() == m.group(1).casefold()),
                          key=paraules.get, default=m.group(1).capitalize())
                forma = f"{nom} {m.group(2)}"
        if forma != r["ubicacio"]:
            r["trucs"].setdefault("ubicacio", []).append("majúscules/signes")
            r["ubicacio"] = forma

    # c) Validar
    vistos = {}
    for r in registres:
        errors, avisos = [], []
        for c in CATEGORICS:
            k = clau(r[c])
            if k in canonics[c]:
                if r[c] != canonics[c][k]:
                    r["trucs"].setdefault(c, []).append("majúscules/signes")
                r[c] = canonics[c][k]
            else:
                errors.append(f"{c}: valor desconegut")

        marca = _data(r["marca_temporal"])
        data = _data(r["data_de_la_incidencia"])
        r["_marca"], r["_data"] = marca, data
        if data is None:
            errors.append("data il·legible")
        elif data.year < 2000:
            errors.append(f"data impossible (any {data.year})")
        elif marca and data.date() > marca.date():
            errors.append(f"data al futur (any {data.year})")
        elif marca and (marca - data).days > 365:
            avisos.append("incidència de fa més d'un any")

        try:
            n = int(r["usuaris_afectats"])
            r["_usuaris"] = n
            if not 1 <= n <= 200:
                errors.append(f"usuaris afectats fora de rang ({n})")
        except ValueError:
            r["_usuaris"] = None
            errors.append("usuaris afectats no numèric")

        for c in CAMPS:
            limit = 1000 if c == "descripcio_de_la_incidencia" else 120
            if len(r[c]) > limit:
                errors.append(f"{c}: text massa llarg ({len(r[c])} caràcters, spam)")
        if len(re.findall(r"[^\W\d_]", r["descripcio_de_la_incidencia"])) < 4:
            errors.append("descripció buida o sense sentit")
        if re.search(r"<\s*\w+[^>]*>|alert\s*\(|<script", " ".join(r[c] for c in CAMPS), re.I):
            avisos.append("possible intent d'injecció de codi")
        if not re.fullmatch(r"INV-\d{5}", r["numero_dinventari"]):
            avisos.append("número d'inventari amb format no estàndard")

        if not errors and r["_data"]:
            clau_dup = (r["_data"].date(), r["numero_dinventari"], r["categoria_de_lavaria"],
                        clau(r["descripcio_de_la_incidencia"]))
            if clau_dup in vistos:
                errors.append(f"registre duplicat (igual que #{vistos[clau_dup]})")
            else:
                vistos[clau_dup] = r["id"]

        r["errors"], r["avisos"] = errors, avisos
        r["valida"] = not errors
        if len(r["descripcio_de_la_incidencia"]) <= 1000:
            nova, r["problemes"], idiomes, canviat = analitzar_descripcio(r["descripcio_de_la_incidencia"])
            if canviat:
                r["descripcio_de_la_incidencia"] = nova
                r["trucs"].setdefault("descripcio_de_la_incidencia", []).append("majúscules/signes")
        else:
            r["problemes"], idiomes = [], [detectar_idioma(r["descripcio_de_la_incidencia"])]
        r["idiomes"] = list(dict.fromkeys(idiomes)) or ["?"]      # sense repetits, en ordre
        r["idioma"] = r["idiomes"][0]
        r["corregida"] = bool(r["trucs"])
    return registres


# Tipus d'espai: la mateixa paraula en diferents idiomes → nom en català
_ESPAIS = {
    "Aula": "aula 教室 аудитория αίθουσα αιθουσα classroom",
    "Sala": "sala salle 会議室 قاعة raum room",
    "Despatx": "despatx кабинет 办公室 γραφείο γραφειο مكتب gabinete bureau büro ufficio despacho office",
    "Laboratori": "laboratori laboratorio labor lab",
}
_ESPAIS = {w: nom for nom, paraules in _ESPAIS.items() for w in paraules.split()}


def tipus_espai(ubicacio):
    paraula = (ubicacio.split() or ["?"])[0]
    return _ESPAIS.get(paraula.casefold(), paraula)


def filtrar(registres, dept=None, equip=None, cat=None, idioma=None, cerca=None):
    res = registres
    if dept:
        res = [r for r in res if clau(r["departament"]) == clau(dept)]
    if equip:
        res = [r for r in res if clau(r["tipus_dequip"]) == clau(equip)]
    if cat:
        res = [r for r in res if clau(r["categoria_de_lavaria"]) == clau(cat)]
    if idioma:
        res = [r for r in res if idioma in r["idiomes"]]
    if cerca:
        k = clau(cerca)
        res = [r for r in res if k in clau(" ".join(r[c] for c in CAMPS))]
    return res


# ════════════════════════════════════════════════════════════════════════════
# 5. ESTADÍSTIQUES
# ════════════════════════════════════════════════════════════════════════════

MESOS = ["", "gener", "febrer", "març", "abril", "maig", "juny", "juliol",
         "agost", "setembre", "octubre", "novembre", "desembre"]
DIES = ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"]


def estadistiques(registres, valides):
    s = {}
    s["total"] = len(registres)
    s["valides"] = len(valides)
    s["descartades"] = len(registres) - len(valides)
    s["corregides"] = sum(r["corregida"] for r in registres)
    s["trucs"] = collections.Counter(t for r in registres for ts in r["trucs"].values() for t in set(ts))
    s["motius"] = collections.Counter(re.sub(r"\s*\(.*\)", "", e) for r in registres for e in r["errors"])
    s["avisos"] = collections.Counter(a for r in registres for a in r["avisos"])
    for c in CATEGORICS:
        s[c] = collections.Counter(r[c] for r in valides)
    s["mes"] = collections.Counter(r["_data"].month for r in valides)
    s["dia"] = collections.Counter(r["_data"].weekday() for r in valides)
    s["idioma"] = collections.Counter(r["idioma"] for r in valides)
    s["ubicacio"] = collections.Counter(r["ubicacio"] for r in valides)
    s["planta"] = collections.Counter(
        (re.search(r"(\d)\.\d{2}", r["ubicacio"]) or [None, "?"])[1] for r in valides)
    s["tecnic"] = collections.Counter(r["contacte_del_tecnic_assignat"] for r in valides)
    usuaris = [r["_usuaris"] for r in valides]
    s["usuaris"] = {
        "total": sum(usuaris), "mitjana": statistics.mean(usuaris) if usuaris else 0,
        "mediana": statistics.median(usuaris) if usuaris else 0, "max": max(usuaris, default=0),
    }
    s["usuaris_dept"] = collections.Counter()
    s["impacte"] = {c: collections.Counter() for c in CATEGORICS}
    for r in valides:
        s["usuaris_dept"][r["departament"]] += r["_usuaris"]
        for c in CATEGORICS:
            s["impacte"][c][r[c]] += r["_usuaris"]
    s["sense_tecnic"] = sum(1 for r in valides if not re.search(r"[^\W\d_]", r["contacte_del_tecnic_assignat"]))
    s["espai"] = collections.Counter(tipus_espai(r["ubicacio"]) for r in valides)
    # Problemes concrets: cada frase de la descripció
    s["problemes"] = collections.Counter(p for r in valides for p in r["problemes"])
    s["impacte_problema"] = collections.Counter()
    for r in valides:
        for p in set(r["problemes"]):
            s["impacte_problema"][p] += r["_usuaris"]
    s["idiomes_tots"] = collections.Counter(i for r in valides for i in r["idiomes"])
    s["multilingue"] = sum(1 for r in valides if len(r["idiomes"]) > 1)
    # Equips que fallen més d'una vegada (mateix número d'inventari)
    inv = collections.Counter(r["numero_dinventari"] for r in valides
                              if re.fullmatch(r"INV-\d{5}", r["numero_dinventari"]))
    s["reincidents"] = {k: v for k, v in inv.items() if v > 1}
    # Temps entre que passa la incidència i es notifica
    retards = [(r["_marca"] - r["_data"]).days for r in valides if r["_marca"]]
    s["retard"] = {"mitjana": statistics.mean(retards) if retards else 0,
                   "mediana": statistics.median(retards) if retards else 0}
    # Creuament departament × categoria
    s["creuat"] = collections.Counter((r["departament"], r["categoria_de_lavaria"]) for r in valides)
    return s


# ════════════════════════════════════════════════════════════════════════════
# 6. SORTIDA PER CONSOLA
# ════════════════════════════════════════════════════════════════════════════

class C:
    R = "\033[0m"; B = "\033[1m"; D = "\033[2m"
    VERM = "\033[31m"; VERD = "\033[32m"; GROC = "\033[33m"; BLAU = "\033[34m"
    MAG = "\033[35m"; CIAN = "\033[36m"; GRIS = "\033[90m"


def sense_colors():
    for k in [k for k in vars(C) if not k.startswith("_")]:
        setattr(C, k, "")


AMPLE = min(shutil.get_terminal_size((100, 30)).columns, 110)


def amplada_visual(text):
    """Els caràcters xinesos/japonesos ocupen 2 columnes al terminal."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def ajustar(text, n, dreta=False):
    """Retalla o omple un text fins a n columnes visuals."""
    text = str(text).replace("\n", " ")
    if amplada_visual(text) <= n:
        farciment = " " * (n - amplada_visual(text))
        return farciment + text if dreta else text + farciment
    sortida, w = "", 0
    for ch in text:
        cw = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if w + cw > n - 1:
            break
        sortida += ch; w += cw
    return sortida + "…" + " " * (n - w - 1)


def titol(text):
    print()
    print(f"{C.B}{C.CIAN}▸ {text}{C.R}")
    print(f"{C.D}{'─' * AMPLE}{C.R}")


def barra(valor, maxim, ample, color):
    if maxim <= 0:
        return " " * ample
    plens = valor / maxim * ample
    enters = int(plens)
    mig = "▌" if plens - enters >= 0.5 and enters < ample else ""
    return f"{color}{'█' * enters}{mig}{C.GRIS}{'░' * (ample - enters - len(mig))}{C.R}"


def taula(comptador, total=None, top=None, color=None, etiquetes=None, ample_etiqueta=26,
          per_clau=False, impacte=None, capcalera="Element"):
    """Taula amb columnes: element · incidències · % · gràfic · (usuaris afectats · mitjana)."""
    color = color or C.BLAU
    items = sorted(comptador.items()) if per_clau else comptador.most_common(top)
    if not items:
        print(f"  {C.D}(sense dades){C.R}"); return
    total = total or sum(comptador.values())
    maxim = max(v for _, v in items)
    extra = 20 if impacte is not None else 0
    ample_barra = max(10, AMPLE - ample_etiqueta - 22 - extra)
    cap = f"  {C.D}{ajustar(capcalera, ample_etiqueta)} {'Incid.':>6} {'%':>6}  {ajustar('Gràfic', ample_barra)}"
    if impacte is not None:
        cap += f" {'Afectats':>9} {'Mitj.':>6}"
    print(cap + C.R)
    for k, v in items:
        nom = etiquetes(k) if etiquetes else str(k)
        pct = v / total * 100 if total else 0
        linia = (f"  {ajustar(nom, ample_etiqueta)} {C.B}{v:>6}{C.R} {pct:>5.1f}%  "
                 f"{barra(v, maxim, ample_barra, color)}")
        if impacte is not None:
            linia += f" {impacte[k]:>9} {impacte[k] / v:>6.2f}"
        print(linia)


# ─── Seccions de l'informe (es fan servir a l'informe complet i al menú) ───

def sec_qualitat(registres, s, mostrar_descartades=False):
    titol("De dades a informació: qualitat de les dades")
    pct = s["valides"] / s["total"] * 100 if s["total"] else 0
    print(f"  Registres llegits de l'XML ........... {C.B}{s['total']}{C.R}")
    print(f"  Registres que s'han hagut de corregir  {C.GROC}{C.B}{s['corregides']}{C.R}"
          f" {C.D}(codificats o amb caràcters estranys){C.R}")
    print(f"  Registres descartats (dades errònies)  {C.VERM}{C.B}{s['descartades']}{C.R}")
    print(f"  Registres vàlids per a l'anàlisi ..... {C.VERD}{C.B}{s['valides']} ({pct:.1f}%){C.R}")
    titol("Codificacions i trucs detectats (i corregits)")
    taula(s["trucs"], total=s["total"], color=C.GROC, capcalera="Truc")
    titol("Motius per descartar registres")
    taula(s["motius"], total=max(1, s["descartades"]), color=C.VERM, ample_etiqueta=46, capcalera="Motiu")
    if s["avisos"]:
        titol("Avisos (el registre es manté, però es marca)")
        taula(s["avisos"], total=s["total"], color=C.MAG, ample_etiqueta=46, capcalera="Avís")
    descartats = [r for r in registres if not r["valida"]]
    if descartats:
        print(f"\n  {C.D}Mostra de registres descartats:{C.R}")
        for r in descartats[: None if mostrar_descartades else 5]:
            print(f"  {C.VERM}#{r['id']:>5}{C.R}  {C.D}data '{ajustar(r['original']['data_de_la_incidencia'], 12).strip()}'{C.R}"
                  f"  {'; '.join(r['errors'])[:AMPLE - 30]}")
        if not mostrar_descartades and len(descartats) > 5:
            print(f"  {C.D}… i {len(descartats) - 5} més (opció «Llistar descartades» o --descartades){C.R}")


def sec_impacte(s):
    titol("Impacte global en els usuaris")
    u = s["usuaris"]
    print(f"  Total usuaris afectats  {C.B}{u['total']}{C.R}")
    print(f"  Per incidència          mitjana {C.B}{u['mitjana']:.2f}{C.R}  ·  mediana {C.B}{u['mediana']}{C.R}"
          f"  ·  màxim {C.B}{u['max']}{C.R}")
    print(f"  Retard en notificar     mitjana {C.B}{s['retard']['mitjana']:.1f}{C.R} dies"
          f"  ·  mediana {C.B}{s['retard']['mediana']}{C.R} dies")


def sec_distribucio(s):
    titol("Incidències per categoria d'avaria")
    taula(s["categoria_de_lavaria"], color=C.VERD, impacte=s["impacte"]["categoria_de_lavaria"], capcalera="Categoria")
    titol("Incidències per tipus d'equip")
    taula(s["tipus_dequip"], color=C.CIAN, impacte=s["impacte"]["tipus_dequip"], capcalera="Equip")
    titol("Incidències per departament")
    taula(s["departament"], color=C.MAG, impacte=s["impacte"]["departament"], capcalera="Departament")
    titol("Departament × categoria (10 combinacions més freqüents)")
    for (d, c), v in s["creuat"].most_common(10):
        print(f"  {ajustar(d, 18)} {ajustar(c, 24)} {C.B}{v:>4}{C.R}")


def sec_temporal(s):
    titol("Evolució per mes (data de la incidència)")
    taula(s["mes"], etiquetes=lambda m: MESOS[m], per_clau=True, capcalera="Mes")
    titol("Per dia de la setmana")
    taula(s["dia"], etiquetes=lambda d: DIES[d], color=C.MAG, per_clau=True, capcalera="Dia")


def sec_llocs(s, valides):
    titol("Incidències per planta de l'edifici")
    taula(s["planta"], etiquetes=lambda p: f"Planta {p}" if p != "?" else "Sense planta", per_clau=True, capcalera="Planta")
    titol("Per tipus d'espai (Aula, Sala, Despatx, Laboratori en qualsevol idioma)")
    taula(s["espai"], top=10, color=C.MAG, capcalera="Espai")
    titol("Ubicacions amb més incidències (top 10)")
    taula(s["ubicacio"], top=10, color=C.GROC, capcalera="Ubicació")
    titol("Equips que han fallat més d'una vegada (mateix núm. d'inventari)")
    if s["reincidents"]:
        for k, v in sorted(s["reincidents"].items(), key=lambda kv: -kv[1]):
            equips = sorted({r["tipus_dequip"] for r in valides if r["numero_dinventari"] == k})
            print(f"  {C.B}{k}{C.R}  {C.VERM}{v} incidències{C.R}  {C.D}({', '.join(equips)}){C.R}")
        print(f"  {C.D}Si un mateix número surt amb tipus d'equip diferents, el número d'inventari "
              f"probablement s'ha escrit malament.{C.R}")
    else:
        print(f"  {C.D}Cap{C.R}")
    titol("Càrrega de feina per tècnic")
    t = s["tecnic"]
    if t and max(t.values()) > 1:
        taula(t, top=10, color=C.MAG, ample_etiqueta=34, capcalera="Tècnic")
    else:
        print(f"  {C.B}{len(t)}{C.R} tècnics diferents i cap no té més d'una incidència assignada.")
        print(f"  {C.D}→ Aquesta dada no aporta informació: el camp sembla omplert a l'atzar.{C.R}")
    print(f"  Incidències sense tècnic assignat: {C.B}{s['sense_tecnic']}{C.R}")


def sec_contingut(s):
    titol("Problemes més repetits (unificats entre idiomes)")
    taula(s["problemes"], top=15, color=C.VERD, ample_etiqueta=40, capcalera="Problema",
          etiquetes=lambda p: PROBLEMES[p]["ca"] if p in PROBLEMES else p, impacte=s["impacte_problema"])
    total = sum(s["problemes"].values())
    coneguts = sum(v for p, v in s["problemes"].items() if p in PROBLEMES)
    print(f"  {C.D}{len(PROBLEMES)} problemes tipus expliquen el {coneguts / total * 100 if total else 0:.1f}% "
          f"de les {total} frases; la resta és text lliure.{C.R}")
    titol("Idiomes de les descripcions")
    taula(s["idiomes_tots"], etiquetes=lambda k: IDIOMES.get(k, k), color=C.CIAN, capcalera="Idioma")
    print(f"  {C.D}{s['multilingue']} descripcions barregen més d'un idioma.{C.R}")


def capcalera_informe():
    print(f"\n{C.B}{'═' * AMPLE}{C.R}")
    print(f"{C.B}  INFORME D'INCIDÈNCIES INFORMÀTIQUES{C.R}")
    print(f"{C.B}{'═' * AMPLE}{C.R}")


def informe_consola(registres, valides, s, mostrar_descartades=False):
    capcalera_informe()
    sec_qualitat(registres, s, mostrar_descartades)
    if not valides:
        print(f"\n{C.VERM}No hi ha cap incidència vàlida amb aquests filtres.{C.R}\n"); return
    sec_impacte(s)
    sec_distribucio(s)
    sec_temporal(s)
    sec_llocs(s, valides)
    sec_contingut(s)
    print()


def mostrar_incidencia(r):
    estat = f"{C.VERD}vàlida{C.R}" if r["valida"] else f"{C.VERM}descartada{C.R}"
    titol(f"Incidència #{r['id']} ({estat}{C.B}{C.CIAN})")
    for c in CAMPS:
        print(f"  {C.D}{ajustar(c, 30)}{C.R} {r[c][:AMPLE - 34].replace(chr(10), ' / ')}")
        if c in r["trucs"]:
            print(f"  {' ' * 30} {C.GROC}↳ {', '.join(r['trucs'][c])}{C.R}  "
                  f"{C.GRIS}original: {ajustar(r['original'][c], max(10, AMPLE - 60)).rstrip()}{C.R}")
    print(f"  {C.D}{ajustar('idioma detectat', 30)}{C.R} {', '.join(IDIOMES.get(i, i) for i in r['idiomes'])}")
    if any(i != "ca" for i in r["idiomes"]) and r["problemes"]:
        trad = ". ".join(PROBLEMES[p]["ca"] if p in PROBLEMES else p for p in r["problemes"])
        print(f"  {C.D}{ajustar('traducció al català', 30)}{C.R} {C.VERD}{trad}{C.R}")
    for e in r["errors"]:
        print(f"  {C.VERM}✗ {e}{C.R}")
    for a in r["avisos"]:
        print(f"  {C.GROC}! {a}{C.R}")


# ════════════════════════════════════════════════════════════════════════════
# 7. EXPORTACIONS
# ════════════════════════════════════════════════════════════════════════════

def exportar_csv(registres, ruta):
    import csv
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel ho obre bé
        w = csv.writer(f)
        w.writerow(["id", "valida"] + CAMPS + ["idioma", "errors", "correccions"])
        for r in registres:
            w.writerow([r["id"], "sí" if r["valida"] else "no"] + [r[c] for c in CAMPS] +
                       [r["idioma"], "; ".join(r["errors"]),
                        "; ".join(f"{c}: {', '.join(t)}" for c, t in r["trucs"].items())])
    return ruta


def _per_json(r):
    return {
        "id": r["id"], "valida": r["valida"], "errors": r["errors"], "avisos": r["avisos"],
        "trucs": r["trucs"], "idioma": r["idioma"], "idiomes": r["idiomes"], "problemes": r["problemes"],
        "data": r["_data"].strftime("%Y-%m-%d") if r["_data"] else "",
        "marca": r["_marca"].strftime("%Y-%m-%d %H:%M") if r["_marca"] else "",
        "usuaris": r["_usuaris"], "espai": tipus_espai(r["ubicacio"]),
        **{c: r[c] for c in CAMPS},
        "original": r["original"],
    }


def exportar_json(registres, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump([_per_json(r) for r in registres], f, ensure_ascii=False, indent=1)
    return ruta


def exportar_web(registres, ruta_html):
    # Escapar "</" perquè cap dada pugui tancar l'etiqueta <script>
    blob = json.dumps([_per_json(r) for r in registres], ensure_ascii=False).replace("</", "<\\/")
    plantilla_ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "plantilla.html")
    if not os.path.exists(plantilla_ruta):
        sys.exit("Falta plantilla.html: ha d'estar a la mateixa carpeta que incidencies.py.")
    with open(plantilla_ruta, encoding="utf-8") as f:
        plantilla = f.read()
    with open(ruta_html, "w", encoding="utf-8") as f:
        noms = {pid: {k: v[k] for k in ("ca", "es", "en")} for pid, v in PROBLEMES.items()}
        f.write(plantilla.replace("/*__DADES__*/[]", blob)
                .replace("/*__PROBLEMES__*/{}", json.dumps(noms, ensure_ascii=False)))
    return ruta_html


def obrir_web(registres):
    ruta = os.path.abspath(exportar_web(registres, "web/informe.html"))
    print(f"{C.VERD}Panell web generat:{C.R} {ruta}")
    try:
        webbrowser.open("file://" + ruta)
    except webbrowser.Error:
        print("Obre'l manualment amb el navegador.")


# ════════════════════════════════════════════════════════════════════════════
# 8. MENÚ INTERACTIU PER TERMINAL
# ════════════════════════════════════════════════════════════════════════════

def preguntar(text):
    try:
        return input(f"{C.B}{text}{C.R} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def triar(titol_llista, opcions):
    """Mostra una llista numerada i torna l'opció triada ('' = cap)."""
    print(f"\n{C.B}{titol_llista}{C.R}")
    for i, o in enumerate(opcions, 1):
        print(f"  {C.CIAN}{i:>2}{C.R}. {o}")
    r = preguntar("Número (Intro = sense filtre):")
    if r and r.isdigit() and 1 <= int(r) <= len(opcions):
        return opcions[int(r) - 1]
    return ""


def pausa():
    preguntar(f"{C.D}Prem Intro per tornar al menú…{C.R}")


def menu(registres):
    filtres = {"dept": None, "equip": None, "cat": None, "idioma": None, "cerca": None}
    valides_totes = [r for r in registres if r["valida"]]
    opcions = [
        ("1", "Resum i qualitat de les dades (dades → informació)"),
        ("2", "Impacte en els usuaris"),
        ("3", "Distribució per categoria, equip i departament"),
        ("4", "Evolució temporal (mesos i dies)"),
        ("5", "Ubicacions, plantes, equips reincidents i tècnics"),
        ("6", "Problemes més repetits i idiomes"),
        ("7", "Informe complet"),
        ("8", "Filtrar (departament, equip, categoria, idioma)"),
        ("9", "Cercar text"),
        ("10", "Veure una incidència pel seu número"),
        ("11", "Llistar els registres descartats"),
        ("12", "Exportar dades netes (CSV i JSON)"),
        ("13", "Generar i obrir el panell web"),
        ("0", "Sortir"),
    ]
    while True:
        sel = filtrar(registres, **filtres)
        valides = [r for r in sel if r["valida"]]
        s = estadistiques(sel, valides)
        print(f"\n{C.B}{C.CIAN}{'═' * AMPLE}{C.R}")
        print(f"{C.B}  INCIDÈNCIES · menú{C.R}   {C.D}{len(registres)} registres · {len(valides_totes)} vàlids{C.R}")
        actius = {k: v for k, v in filtres.items() if v}
        if actius:
            print(f"  {C.GROC}Filtre actiu: {', '.join(f'{k}={v}' for k, v in actius.items())}"
                  f" → {len(sel)} registres{C.R}")
        print(f"{C.CIAN}{'═' * AMPLE}{C.R}")
        for k, text in opcions:
            print(f"  {C.CIAN}{k:>2}{C.R}  {text}")
        op = preguntar("\nOpció:")
        if op is None or op == "0":
            print("Fins aviat!"); return

        if op == "1":
            sec_qualitat(sel, s); pausa()
        elif op == "2":
            sec_impacte(s); pausa()
        elif op == "3":
            sec_distribucio(s); pausa()
        elif op == "4":
            sec_temporal(s); pausa()
        elif op == "5":
            sec_llocs(s, valides); pausa()
        elif op == "6":
            sec_contingut(s); pausa()
        elif op == "7":
            informe_consola(sel, valides, s); pausa()
        elif op == "8":
            def valors(c):
                return [k for k, _ in collections.Counter(r[c] for r in valides_totes).most_common()]
            filtres["dept"] = triar("Departament", valors("departament")) or None
            filtres["equip"] = triar("Tipus d'equip", valors("tipus_dequip")) or None
            filtres["cat"] = triar("Categoria d'avaria", valors("categoria_de_lavaria")) or None
            idiomes = [k for k, _ in collections.Counter(r["idioma"] for r in valides_totes).most_common()]
            tria = triar("Idioma de la descripció", [f"{k} · {IDIOMES.get(k, k)}" for k in idiomes])
            filtres["idioma"] = tria.split(" · ")[0] if tria else None
        elif op == "9":
            filtres["cerca"] = preguntar("Text a cercar (Intro = treure la cerca):") or None
            if filtres["cerca"]:
                trobats = filtrar(registres, cerca=filtres["cerca"])
                print(f"  {C.B}{len(trobats)}{C.R} coincidències. Primeres 15:")
                for r in trobats[:15]:
                    print(f"  {C.CIAN}#{r['id']:>5}{C.R} {ajustar(r['departament'], 14)} "
                          f"{ajustar(r['tipus_dequip'], 11)} {ajustar(r['descripcio_de_la_incidencia'], AMPLE - 40)}")
                print(f"  {C.D}El filtre de cerca queda actiu per a la resta d'opcions.{C.R}")
                pausa()
        elif op == "10":
            num = preguntar("Número d'incidència:")
            r = next((r for r in registres if r["id"] == num), None)
            mostrar_incidencia(r) if r else print(f"  {C.VERM}No existeix la incidència #{num}.{C.R}")
            pausa()
        elif op == "11":
            titol("Registres descartats")
            for r in sel:
                if not r["valida"]:
                    print(f"  {C.VERM}#{r['id']:>5}{C.R}  {'; '.join(r['errors'])}")
            pausa()
        elif op == "12":
            a = exportar_csv(sel, "data/incidencies_netes.csv")
            b = exportar_json(sel, "data/incidencies_netes.json")
            print(f"  {C.VERD}Exportat:{C.R} {os.path.abspath(a)}\n  {C.VERD}Exportat:{C.R} {os.path.abspath(b)}")
            pausa()
        elif op == "13":
            obrir_web(registres)
        else:
            print(f"  {C.VERM}Opció no vàlida.{C.R}")


# ════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Analitza les incidències del fitxer XML. Sense opcions obre el menú interactiu.")
    ap.add_argument("fitxer_pos", nargs="?", help=argparse.SUPPRESS)
    ap.add_argument("-f", "--fitxer", help="fitxer XML (per defecte incidencies.xml)")
    ap.add_argument("-i", "--informe", action="store_true", help="mostrar l'informe complet i sortir")
    ap.add_argument("--dept", help="filtrar per departament")
    ap.add_argument("--equip", help="filtrar per tipus d'equip")
    ap.add_argument("--cat", help="filtrar per categoria d'avaria")
    ap.add_argument("--idioma", help="filtrar per idioma de la descripció (ca, es, en, ja, zh, ru...)")
    ap.add_argument("--cerca", help="cerca de text lliure a tots els camps")
    ap.add_argument("--id", help="mostrar una sola incidència")
    ap.add_argument("--descartades", action="store_true", help="llistar tots els registres descartats i el motiu")
    ap.add_argument("--csv", metavar="FITXER", help="exportar les dades netes a CSV")
    ap.add_argument("--json", metavar="FITXER", help="exportar les dades netes a JSON")
    ap.add_argument("--web", action="store_true", help="generar el panell web informe.html i obrir-lo")
    ap.add_argument("--sense-colors", action="store_true", help="sortida sense colors ANSI")
    args = ap.parse_args()

    if args.sense_colors or not sys.stdout.isatty():
        sense_colors()
    if os.name == "nt":
        os.system("")            # activa els colors ANSI a la consola de Windows

    ruta = args.fitxer or args.fitxer_pos or ("data/incidencies.xml" if os.path.exists("data/incidencies.xml") else "data/Incidencies.xml")
    if not os.path.exists(ruta):
        sys.exit(f"No trobo el fitxer {ruta}. Indica'l amb -f RUTA.")

    if sys.stdout.isatty():
        print(f"{C.D}Llegint i netejant {ruta}…{C.R}", end="\r", flush=True)
    registres = processar(llegir_xml(ruta))
    if sys.stdout.isatty():
        print(" " * 60, end="\r")

    filtres = any([args.dept, args.equip, args.cat, args.idioma, args.cerca])
    seleccio = filtrar(registres, args.dept, args.equip, args.cat, args.idioma, args.cerca)

    if args.csv:
        print(f"Exportat: {exportar_csv(seleccio, args.csv)}")
    if args.json:
        print(f"Exportat: {exportar_json(seleccio, args.json)}")
    if args.web:
        obrir_web(registres)
    if args.id:
        r = next((r for r in registres if r["id"] == args.id), None)
        mostrar_incidencia(r) if r else print(f"No existeix la incidència #{args.id}.")
    if args.csv or args.json or args.web or args.id:
        return

    # Sense cap opció i en un terminal: menú interactiu
    if not (args.informe or filtres or args.descartades) and sys.stdin.isatty() and sys.stdout.isatty():
        menu(registres)
        return

    valides = [r for r in seleccio if r["valida"]]
    s = estadistiques(seleccio, valides)
    if filtres:
        print(f"{C.GROC}Filtre aplicat: {len(seleccio)} de {len(registres)} registres{C.R}")
    informe_consola(seleccio, valides, s, args.descartades)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:          # p. ex. «python3 incidencies.py -i | head»
        sys.stderr.close()