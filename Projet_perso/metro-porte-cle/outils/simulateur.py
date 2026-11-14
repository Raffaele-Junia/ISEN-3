"""Applique sur PC les règles du firmware au flux réel des perturbations ilévia.

Sert à vérifier ce que le porte-clé afficherait, sans le matériel :

    python simulateur.py           # état actuel des lignes
    python simulateur.py --test    # cas d'essai des règles (aucun accès réseau)

Les fonctions reprennent une à une celles de firmware/MetroPorteCle/analyse.cpp et
ville_lille.cpp : toute modification des règles doit être faite des deux côtés.
"""
import json
import sys
import unicodedata
import urllib.request
from datetime import datetime, timedelta

URL = ("https://data.lillemetropole.fr/geoserver/ogc/features/v1/collections/"
       "dsp_ilevia%3Aperturbations/items?f=application%2Fjson&limit=200")
MARGE_FIN_S = 10 * 60
SANS_ESTIMATION_S = 2 * 3600
EPINGLEES = {"ME1": "M1", "ME2": "M2", "71": "TRAM"}
GRAVITE = ["NORMAL", "INFO", "PERTURBE", "PARTIEL", "INTERROMPU"]
EPOQUE = datetime(1970, 1, 1)

REMPLACEMENTS = {"œ": "oe", "Œ": "OE", "’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"',
                 "–": "-", "—": "-", "…": "...", "►": ">", "▶": ">", "→": ">", "•": ">",
                 " ": " ", " ": " ", " ": " ", "°": "o", "€": "EUR",
                 "​": "", "‍": "", "﻿": "", "️": ""}


def murale(iso):
    """« 2026-11-14T10:59:27.098Z » -> secondes murales (chiffres lus tels quels), -1 si illisible."""
    try:
        return int((datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S") - EPOQUE).total_seconds())
    except (TypeError, ValueError):
        return -1


def vers_ascii(texte):
    sortie = []
    for c in texte or "":
        if c in REMPLACEMENTS:
            sortie.append(REMPLACEMENTS[c])
        elif ord(c) < 0x20:
            sortie.append(" ")
        elif ord(c) < 0x80:
            sortie.append(c)
        else:
            base = unicodedata.normalize("NFD", c)[0]
            sortie.append(base if ord(base) < 0x80 else "?")
    return " ".join("".join(sortie).split())


def heure_apres(p):
    """Cherche « 11h15 », « 08h 05 », « 18 h » dans les 48 caractères qui suivent."""
    i = 0
    while i < min(48, len(p)):
        if not p[i].isdigit():
            i += 1
            continue
        j = i
        while j < len(p) and p[j].isdigit():
            j += 1
        if j - i <= 2:
            h, k = int(p[i:j]), j
            while k < len(p) and p[k] == " ":
                k += 1
            if k < len(p) and p[k] in "hH:":
                k += 1
                while k < len(p) and p[k] == " ":
                    k += 1
                m = k
                while m < len(p) and p[m].isdigit() and m - k < 2:
                    m += 1
                minutes = int(p[k:m]) if m > k else 0
                if h < 24 and minutes < 60:
                    return h, minutes
        i = j
    return None


def analyser(msg, publie, fin_validite, maintenant):
    """Renvoie (état, heure murale de reprise estimée ou 0)."""
    bas = msg.lower()
    if any(m in bas for m in ("a repris", "ont repris", "reprend", "retabli", "trafic normal",
                              "circule a nouveau", "circulent a nouveau", "fin de perturbation")):
        return "NORMAL", 0
    if fin_validite > 0 and maintenant > fin_validite:
        return "NORMAL", 0
    jusqua = 0
    pos = bas.find("jusqu")
    heure = heure_apres(bas[pos:]) if pos >= 0 else None
    if heure:
        jusqua = publie - publie % 86400 + heure[0] * 3600 + heure[1] * 60
        if jusqua < publie - 300:
            jusqua += 86400
        actif = maintenant <= jusqua + MARGE_FIN_S
    elif pos >= 0:
        actif = True
    else:
        actif = maintenant - publie <= SANS_ESTIMATION_S
    if not actif:
        return "NORMAL", 0
    if any(m in bas for m in ("interrompu", "ne circule", "a l'arret")):
        troncon = any(m in bas for m in ("entre les stations", "entre la station", "entre les arrets"))
        return ("PARTIEL" if troncon else "INTERROMPU"), jusqua
    return "PERTURBE", jusqua


def heure_de_paris(utc):
    """UTC -> heure légale française (règle européenne : été du dernier dimanche de mars
    au dernier dimanche d'octobre, bascule à 01:00 UTC). Évite de dépendre de tzdata."""
    def dernier_dimanche(mois):
        jour = datetime(utc.year, mois, 31, 1)
        return jour - timedelta(days=(jour.weekday() + 1) % 7)
    ete = dernier_dimanche(3) <= utc < dernier_dimanche(10)
    return utc + timedelta(hours=2 if ete else 1)


def etat_reseau(donnees):
    utc = datetime.strptime(donnees["timeStamp"][:19], "%Y-%m-%dT%H:%M:%S")
    maintenant = murale(heure_de_paris(utc).strftime("%Y-%m-%dT%H:%M:%S"))
    candidats = {code: {} for code in EPINGLEES}
    for f in donnees["features"]:
        p = f["properties"]
        cible, publie = p.get("cible") or "", murale(p.get("date_modification"))
        if "LineRef::" not in cible or publie < 0:
            continue
        code = cible.split("LineRef::")[1].split(":")[0]
        genre = "pert" if p.get("type_perturbation") == "Perturbation" else "info"
        c = candidats.setdefault(code, {})
        if genre not in c or publie > c[genre][0]:
            c[genre] = (publie, p)
    lignes = []
    for code, c in candidats.items():
        ligne = {"code": code, "nom": EPINGLEES.get(code, code), "etat": "NORMAL", "jusqua": 0,
                 "publie": 0, "message": "", "actif": False}
        if "pert" in c:
            publie, p = c["pert"]
            ligne["message"] = vers_ascii(p.get("message"))
            ligne["etat"], ligne["jusqua"] = analyser(ligne["message"], publie,
                                                      murale(p.get("heure_fin_prevue")), maintenant)
            ligne["publie"], ligne["actif"] = publie, ligne["etat"] != "NORMAL"
        if ligne["etat"] == "NORMAL" and "info" in c:
            publie, p = c["info"]
            fin = murale(p.get("heure_fin_prevue"))
            if fin < 0 or maintenant <= fin:
                ligne.update(etat="INFO", jusqua=0, publie=publie, actif=True,
                             message=vers_ascii(p.get("message")))
        if code in EPINGLEES or ligne["etat"] != "NORMAL":
            lignes.append(ligne)
    ordre = list(EPINGLEES)
    lignes.sort(key=lambda l: (0, ordre.index(l["code"]), "") if l["code"] in EPINGLEES
                else (1, -GRAVITE.index(l["etat"]), l["code"]))
    return maintenant, lignes


def hhmm(t):
    return f"{t % 86400 // 3600:02d}h{t % 3600 // 60:02d}"


def afficher():
    requete = urllib.request.Request(URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(requete, timeout=20) as reponse:
        donnees = json.load(reponse)
    maintenant, lignes = etat_reseau(donnees)
    print(f"LILLE  {hhmm(maintenant)}  ({len(donnees['features'])} enregistrements)")
    for l in lignes:
        if l["etat"] == "NORMAL":
            aujourdhui = l["message"] and l["publie"] // 86400 == maintenant // 86400
            note = f"dernier incident {hhmm(l['publie'])}" if aujourdhui else "aucune alerte"
        elif l["etat"] == "INFO":
            note = "toucher pour lire"
        elif l["jusqua"]:
            note = f"jusqu'a {hhmm(l['jusqua'])} environ"
        else:
            note = f"depuis {hhmm(l['publie'])}"
        print(f"  [{l['nom']:>4}] {l['etat']:<11} {note}")
        if l["actif"]:
            print(f"         {l['message'][:110]}")


def tester():
    j = murale("2026-11-14T00:00:00")
    h = lambda hh, mm=0: j + hh * 3600 + mm * 60
    fin = lambda publie: publie + 86400
    interrompue = "En raison d'un defaut de porte, la ligne 1 du metro est interrompue jusque 11h 15 environ."
    cas = [
        # (message, publié, maintenant, état attendu, reprise attendue)
        (interrompue, h(10, 59), h(11, 5), "INTERROMPU", h(11, 15)),
        (interrompue, h(10, 59), h(11, 24), "INTERROMPU", h(11, 15)),   # dans la marge de 10 min
        (interrompue, h(10, 59), h(11, 26), "NORMAL", 0),
        ("La ligne 2 est interrompue entre les stations C.H. DRON et TOURCOING CENTRE jusque 11h 40 environ.",
         h(11, 20), h(11, 30), "PARTIEL", h(11, 40)),
        ("La ligne 2 du metro est actuellement interrompue. Nos equipes procedent au diagnostic.",
         h(7, 47), h(8, 30), "INTERROMPU", 0),
        ("La ligne 2 du metro est actuellement interrompue. Nos equipes procedent au diagnostic.",
         h(7, 47), h(10, 0), "NORMAL", 0),                              # plus de 2 h sans nouvelle
        ("Trafic interrompu jusqu'a nouvel ordre sur la ligne 1.", h(6), h(20), "INTERROMPU", 0),
        ("Trafic interrompu jusque 00h30 environ.", h(23, 50), h(24, 10), "INTERROMPU", h(24, 30)),
        ("La ligne 1 du metro circule a nouveau normalement.", h(11, 16), h(11, 17), "NORMAL", 0),
        ("Ligne 1 interrompue, reprise estimee jusque 12h00.", h(11), h(11, 30), "INTERROMPU", h(12)),
        ("Frequence reduite sur la ligne 2 jusque 18h.", h(16), h(17), "PERTURBE", h(18)),
        ("Ligne interrompue jusqu'au 15/11 pour travaux.", h(5), h(22), "INTERROMPU", 0),
    ]
    echecs = 0
    for msg, publie, maintenant, etat, jusqua in cas:
        obtenu = analyser(vers_ascii(msg), publie, fin(publie), maintenant)
        ok = obtenu == (etat, jusqua)
        echecs += not ok
        print(("ok    " if ok else "ECHEC ") + f"{etat:<11} {msg[:60]}" + ("" if ok else f"  -> {obtenu}"))
    brut = "Ce 14/11, à partir de 13h30 – la Liane 5 est déviée.► Arrêts « Gare » non desservis…​"
    attendu = 'Ce 14/11, a partir de 13h30 - la Liane 5 est deviee.> Arrets " Gare " non desservis...'
    ok = vers_ascii(brut) == attendu
    echecs += not ok
    print(("ok    " if ok else "ECHEC ") + "conversion ASCII" + ("" if ok else f"  -> {vers_ascii(brut)!r}"))
    print(f"{len(cas) + 1 - echecs}/{len(cas) + 1} cas reussis")
    return echecs


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(1 if tester() else 0)
    afficher()
