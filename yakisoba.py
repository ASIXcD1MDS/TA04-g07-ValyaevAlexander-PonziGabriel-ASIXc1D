import random
import sys
import time
from time import sleep

# region Configuració ----------
VERD, GRIS, GROC, VERMELL = "\033[92m", "\033[90m", "\033[93m", "\033[91m"
BLAU, CIAN, MAGENTA = "\033[94m", "\033[96m", "\033[95m"
NEGRETA, RESET = "\033[1m", "\033[0m"
AMAGAR_CURSOR, MOSTRAR_CURSOR = "\033[?25l", "\033[?25h"

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
AMPLADA_OLLA = 24
AMPLADA_BARRA = 25

# Temps de cocció (cada unitat = 0.5 s). Els ingredients desconeguts tenen un temps aleatori.
TEMPS_COCCIO = {
    "tallarines": 15, "fideus": 15, "pastanagues": 5, "pastanaga": 5,
    "col": 6, "ceba": 4, "pebrot": 4, "porc": 10, "pollastre": 10,
    "gambes": 6, "bolets": 5, "brots de soja": 3, "salsa yakisoba": 3,
}
INGREDIENTS_PER_DEFECTE = ["tallarines", "pastanagues", "col", "porc", "salsa yakisoba"]
# endregion


# region Funcions d'interfície ----------
def escriure(text, retard=0.02):
    """Escriu el text lletra a lletra, com una màquina d'escriure."""
    for c in text:
        print(c, end="", flush=True)
        sleep(retard)
    print()


def titol(text, color=CIAN):
    linia = "═" * (len(text) + 4)
    print(f"\n{color}{NEGRETA}╔{linia}╗")
    print(f"║  {text}  ║")
    print(f"╚{linia}╝{RESET}\n")


def barra(progres, amplada=AMPLADA_BARRA):
    plens = int(amplada * progres)
    return f"{VERD}{'█' * plens}{GRIS}{'░' * (amplada - plens)}{RESET}"


def icona_estat(i, acabat):
    return f"{VERD}✔{RESET}" if acabat else f"{GROC}{SPINNER[i % len(SPINNER)]}{RESET}"


def simular_cuinar(temps=3, etiqueta="Cuinant"):
    """Barra de progrés horitzontal d'una sola línia."""
    passos = temps * 10
    durada = temps * 0.5
    for i in range(passos + 1):
        progres = i / passos
        acabat = i == passos
        restant = durada * (1 - progres)
        print(f"\r  {icona_estat(i, acabat)} {etiqueta[:24]:<24} │{barra(progres)}│ "
              f"{progres:6.1%}  ⏱ {restant:4.1f}s", end="", flush=True)
        if not acabat:
            sleep(durada / passos)
    print()
# endregion


# region Olla animada ----------
def frame_olla(text, temperatura):
    """Retorna les línies d'un fotograma de l'olla segons la temperatura."""
    W = AMPLADA_OLLA
    intensitat = max(0.05, min(1, (temperatura - 20) / 80))

    def aleatori(caracters, prob, buit=" "):
        return "".join(random.choice(caracters) if random.random() < prob else buit
                       for _ in range(W))

    vapor = aleatori("~°'", 0.25 * intensitat)
    superficie = aleatori("oO°.", 0.5 * intensitat, "~")
    bombolles = aleatori(".o°", 0.15 * intensitat)
    foc = "".join(f"{random.choice([VERMELL, GROC])}{random.choice('()^')}"
                  if random.random() < 0.7 else " " for _ in range(W))
    sagnat = "    "

    return [
        f"{sagnat} {GRIS}{vapor}{RESET}",
        f"  {GRIS}══╗{' ' * W}╔══{RESET}",
        f"{sagnat}{GRIS}║{BLAU}{superficie}{GRIS}║{RESET}",
        f"{sagnat}{GRIS}║{GROC}{NEGRETA}{text[:W].center(W)}{RESET}{GRIS}║{RESET}",
        f"{sagnat}{GRIS}║{BLAU}{bombolles}{GRIS}║{RESET}",
        f"{sagnat}{GRIS}╚{'═' * W}╝{RESET}",
        f"{sagnat} {foc}{RESET}",
        f"{sagnat}{GRIS}{'▀' * (W + 2)}{RESET}",
    ]


def animar_olla(textos, temps, etiqueta, temp_inicial=100, temp_final=100):
    """Dibuixa l'olla animada amb una barra de progrés i la temperatura a sota."""
    passos = temps * 10
    durada = temps * 0.5
    for i in range(passos + 1):
        progres = i / passos
        acabat = i == passos
        temperatura = temp_inicial + (temp_final - temp_inicial) * progres
        if temp_inicial == temp_final:
            temperatura += random.uniform(-1.0, 1.0)   # el foc no és perfecte
        text = textos[(i // 10) % len(textos)]
        restant = durada * (1 - progres)

        linies = frame_olla(text, temperatura)
        linies.append(f"  {icona_estat(i, acabat)} {etiqueta[:22]:<22} │{barra(progres)}│ "
                      f"{progres:6.1%} {VERMELL}{temperatura:5.1f}°C{RESET} ⏱ {restant:4.1f}s")

        if i > 0:
            print(f"\033[{len(linies)}A", end="")   # torna amunt per redibuixar
        for linia in linies:
            print(f"\033[2K{linia}")
        sys.stdout.flush()

        if not acabat:
            sleep(durada / passos)
# endregion


# region Passos de la recepta ----------
def demanar_ingredients():
    titol("Llista d'ingredients", MAGENTA)
    print(f"  {GRIS}Escriu els ingredients un a un (o separats per comes).")
    print(f"  Prem Enter sense escriure res per acabar.{RESET}\n")

    ingredients = []
    while True:
        resposta = input(f"  {MAGENTA}➜ Ingredient {len(ingredients) + 1}: {RESET}").strip().lower()
        if not resposta:
            break
        for nom in resposta.split(","):
            nom = nom.strip()
            if not nom:
                continue
            if nom in ingredients:
                print(f"    {GROC}⚠ '{nom}' ja és a la llista{RESET}")
            else:
                ingredients.append(nom)
                print(f"    {VERD}✔ Afegit: {nom}{RESET}")

    if not ingredients:
        print(f"\n  {GROC}No has afegit res: faré servir la recepta clàssica.{RESET}")
        ingredients = INGREDIENTS_PER_DEFECTE.copy()
    return ingredients


def mostrar_recepta(recepta):
    print(f"\n  {NEGRETA}{'Ingredient':<22} {'Cocció':>7}{RESET}")
    print(f"  {GRIS}{'─' * 22} {'─' * 7}{RESET}")
    for nom, temps in recepta.items():
        print(f"  {nom:<22} {temps * 0.5:>6.1f}s")


def recopilar_ingredients(recepta):
    titol("PAS 1 · Comprar al supermercat")
    for nom in recepta:
        print(f"  {GRIS}…{RESET} Agafant {nom}", end="", flush=True)
        sleep(0.4)
        print(f"\r  {VERD}✔{RESET} Agafant {nom}")
    escriure(f"  {CIAN}Disposant-los sobre el marbre...{RESET}")
    sleep(0.5)


def preparar_ingredients(recepta):
    titol("PAS 2 · Preparar els ingredients")
    for nom in recepta:
        verb = "Preparant" if "salsa" in nom else "Tallant"
        simular_cuinar(4, f"{verb} {nom}")


def cuinar_a_lolla(recepta):
    titol("PAS 3 · A l'olla")
    animar_olla(["Aigua"], 8, "Escalfant l'aigua", 20, 100)
    print(f"  {VERD}✔ L'aigua ja bull!{RESET}\n")

    for nom, temps in recepta.items():
        if "salsa" in nom:
            continue   # la salsa es reserva per al final
        print(f"  {CIAN}➜ Afegint {nom} a l'olla...{RESET}")
        animar_olla([nom], temps, f"Bullint {nom}")
        print(f"  {VERD}✔ {nom.capitalize()} a punt!{RESET}\n")


def ensamblar(recepta):
    titol("PAS 4 · Ensamblar-ho tot")
    escriure("  Escorrent l'aigua i passant-ho tot al wok...")
    simular_cuinar(4, "Escorrent")
    print()

    hi_ha_salsa = any("salsa" in nom for nom in recepta)
    etiqueta = "Saltejant amb la salsa" if hi_ha_salsa else "Saltejant-ho tot"
    animar_olla(list(recepta) + ["SALTEJANT!"], 12, etiqueta, 100, 180)
    print(f"  {VERD}✔ Tot ben barrejat!{RESET}")


def servir(recepta, inici):
    titol("PAS 5 · Emplatar", VERD)
    plat = [
        f"{GRIS}             (   )  (",
        f"{GRIS}              ) (    )",
        f"{GROC}          .-{'~' * 14}-.",
        f"{GROC}        .'  {'≈' * 14}  '.",
        f"{GROC}       (   {NEGRETA}Y A K I S O B A{RESET}{GROC}    )",
        f"{GROC}        '.{' ' * 18}.'",
        f"{GROC}          '-{'.' * 14}-'",
    ]
    for linia in plat:
        print(linia + RESET)
        sleep(0.15)

    temps_total = time.perf_counter() - inici
    print(f"\n  {NEGRETA}Ingredients:{RESET} {', '.join(recepta)}")
    print(f"  {NEGRETA}Temps total:{RESET} {temps_total:.1f} s\n")
    escriure(f"  {VERD}{NEGRETA}✔ El yakisoba ja està llest! Bon profit! 🍜{RESET}", 0.04)
    print()
# endregion


# region INICI: Preparar fideus Yakisoba ----------
def main():
    try:
        titol("YAKISOBA SIMULATOR 3000", MAGENTA)
        ingredients = demanar_ingredients()
        recepta = {nom: TEMPS_COCCIO.get(nom, random.randint(3, 8)) for nom in ingredients}
        mostrar_recepta(recepta)
        input(f"\n  {GRIS}Prem Enter per començar a cuinar...{RESET}")

        print(AMAGAR_CURSOR, end="")
        inici = time.perf_counter()
        recopilar_ingredients(recepta)
        preparar_ingredients(recepta)
        cuinar_a_lolla(recepta)
        ensamblar(recepta)
        servir(recepta, inici)
    except KeyboardInterrupt:
        print(f"\n\n  {VERMELL}✖ Cuina interrompuda. Apaga el foc!{RESET}\n")
    finally:
        print(MOSTRAR_CURSOR, end="")


main()
# endregion