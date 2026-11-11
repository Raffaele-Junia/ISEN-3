"""Moteur de recommandation (sans service externe, sans apprentissage).

Deux signaux combines :
1. le CONTENU : meme genre, themes partages, meme auteur, meme revue, epoque proche ;
2. les USAGES : « les lecteurs qui ont emprunte ceci ont aussi emprunte cela »
   (co-emprunts agreges : seuil d'anonymat de 3 autres lecteurs).

Les recommandations personnelles (`pour_adherent`) partent de l'historique du
lecteur et indiquent la raison (« Parce que vous avez aime 1984 »).
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations

POIDS_GENRE = 3.0
POIDS_THEME = 1.5        # par theme partage
POIDS_CREATEUR = 3.0
POIDS_MEME_REVUE = 4.0
POIDS_EPOQUE = 0.5
POIDS_MEME_SUPPORT = 1.0  # film avec film, livre avec livre (a contenu egal)
POIDS_CO_EMPRUNT = 0.8   # par lecteur commun, plafonne (un bonus, pas un lien a lui seul)
PLAFOND_CO_EMPRUNT = 3
SEUIL = 2.5              # en dessous, la ressemblance n'est pas montree
LIEN_CONTENU_MIN = 1.5   # « Dans la meme veine » exige un vrai lien : genre, theme ou auteur
SEUIL_ANONYMAT = 3       # une paire de co-emprunts ne compte qu'a partir de 3 lecteurs (F1)
HISTORIQUE_MAX = 10      # lectures recentes prises en compte pour « Pour vous » (F2)

# Cache des co-emprunts (F2) : recalcule seulement quand un pret est ajoute.
_cache = {"cle": None, "par_lecteur": None, "paires": None}


def _etat(m):
    emprunts = m.emprunts
    return (id(m), len(emprunts), id(emprunts[-1]) if emprunts else None)


def _base(m):
    cle = _etat(m)
    if _cache["cle"] != cle:
        par_lecteur = defaultdict(set)
        for e in m.emprunts:
            par_lecteur[e.numero_adherent].add(e.id_document)
        compteur = Counter()
        for ids in par_lecteur.values():
            for a, b in combinations(sorted(ids), 2):
                compteur[a, b] += 1
        _cache.update(cle=cle, par_lecteur=par_lecteur,
                      paires={k: v for k, v in compteur.items() if v >= SEUIL_ANONYMAT})
    return _cache["par_lecteur"], _cache["paires"]


class CoEmprunts:
    """Vue en lecture des co-emprunts pour un demandeur : ses propres emprunts ne
    comptent pas, et une paire n'existe qu'avec SEUIL_ANONYMAT AUTRES lecteurs (F1)."""

    def __init__(self, paires, retires=frozenset()):
        self._paires, self._retires = paires, retires

    def get(self, cle, defaut=0):
        v = self._paires.get(cle, 0) - (1 if cle in self._retires else 0)
        return v if v >= SEUIL_ANONYMAT else defaut

    def partenaires(self, id_document):
        return {b if a == id_document else a for a, b in self._paires
                if id_document in (a, b) and self.get((a, b))}

    def __bool__(self):
        return bool(self._paires)


def co_emprunts(m, exclure=None):
    """Co-emprunts anonymises vus par le lecteur `exclure` (voir CoEmprunts)."""
    par_lecteur, paires = _base(m)
    retires = frozenset()
    if exclure is not None and exclure in par_lecteur:
        siens = sorted(par_lecteur[exclure])
        retires = frozenset(p for p in combinations(siens, 2) if p in paires)
    return CoEmprunts(paires, retires)


def _candidats(m, doc, co):
    """Documents partageant au moins un critere de contenu avec `doc` (index F2)."""
    index = _index(m)
    cles = [("g", doc.genre)] if doc.genre else []
    cles += [("t", t) for t in doc.themes]
    if doc.createur:
        cles.append(("c", doc.createur))
    if doc.CLE == "revue":
        cles.append(("r", doc.titre))
    ids = set()
    for cle in cles:
        ids |= index.get(cle, set())
    if co:
        ids |= co.partenaires(doc.id)
    ids.discard(doc.id)
    return ids


_cache_index = {"cle": None, "index": None}


def _index(m):
    cle = (id(m), len(m), tuple(sorted((d.id, d.genre, d.themes, d.createur) for d in m)).__hash__())
    if _cache_index["cle"] != cle:
        index = defaultdict(set)
        for d in m:
            if d.genre:
                index["g", d.genre].add(d.id)
            for t in d.themes:
                index["t", t].add(d.id)
            if d.createur:
                index["c", d.createur].add(d.id)
            if d.CLE == "revue":
                index["r", d.titre].add(d.id)
        _cache_index.update(cle=cle, index=index)
    return _cache_index["index"]


def ressemblance(a, b, co=None):
    """Score de ressemblance entre deux documents (symetrique, 0 si identiques)."""
    if a.id == b.id:
        return 0.0
    score = 0.0
    if a.genre and a.genre == b.genre:
        score += POIDS_GENRE
        if a.CLE == b.CLE:
            score += POIDS_MEME_SUPPORT
    score += POIDS_THEME * len(set(a.themes) & set(b.themes))
    if a.createur and a.createur == b.createur:
        score += POIDS_CREATEUR
    if a.CLE == b.CLE == "revue" and a.titre == b.titre:
        score += POIDS_MEME_REVUE
    if abs(a.annee - b.annee) <= 15:
        score += POIDS_EPOQUE
    if co:
        cle = (a.id, b.id) if a.id < b.id else (b.id, a.id)
        score += POIDS_CO_EMPRUNT * min(co.get(cle, 0), PLAFOND_CO_EMPRUNT)
    return score


def similaires(m, id_document, n=6, exclure=(), co=None, numero=None):
    """Les n documents qui ressemblent le plus a `id_document` (pour le lecteur `numero`)."""
    reference = m[id_document]
    co = co_emprunts(m, exclure=numero) if co is None else co
    exclure = set(exclure) | {id_document}
    notes = [(ressemblance(reference, m[i], co), m[i])
             for i in _candidats(m, reference, co) if i not in exclure
             and ressemblance(reference, m[i]) >= LIEN_CONTENU_MIN]
    notes = [(s, d) for s, d in notes if s >= SEUIL]
    # a score egal : le document en rayon d'abord, puis l'ordre alphabetique
    notes.sort(key=lambda sd: (-sd[0], not m.disponible(sd[1].id), sd[1].titre))
    return [d for _, d in notes[:n]]


def populaires(m, n=8, depuis_jours=90, aujourdhui=None, exclure=()):
    aujourdhui = aujourdhui or date.today()
    limite = aujourdhui - timedelta(days=depuis_jours)
    compteur = Counter(e.id_document for e in m.emprunts
                       if e.date_emprunt >= limite and e.id_document not in exclure)
    return [m[i] for i, _ in compteur.most_common(n)]


def pour_adherent(m, numero, n=8, aujourdhui=None):
    """Liste de (document, raison) pour un lecteur, d'apres son historique.

    Exclut ce qu'il a deja emprunte (ou a en main) et ce qu'il a reserve.
    Les emprunts recents pesent plus que les anciens.
    """
    aujourdhui = aujourdhui or date.today()
    historique, deja_vus = {}, set()  # id -> poids (recence)
    for e in sorted((e for e in m.emprunts if e.numero_adherent == numero),
                    key=lambda e: e.date_emprunt, reverse=True):
        deja_vus.add(e.id_document)
        if e.id_document in historique or len(historique) >= HISTORIQUE_MAX:
            continue
        age = max(0, (aujourdhui - e.date_emprunt).days)
        historique[e.id_document] = 1.0 if age < 60 else 0.6 if age < 180 else 0.35
    deja_vus |= {r.id_document for r in m.reservations if r.numero_adherent == numero}

    def repli():
        return [(d, "Très demandé en ce moment")
                for d in populaires(m, n, aujourdhui=aujourdhui, exclure=deja_vus)]

    if not historique:
        return repli()

    co = co_emprunts(m, exclure=numero)
    scores, raisons = defaultdict(float), {}
    for id_vu, poids in historique.items():
        vu = m[id_vu]
        for id_candidat in _candidats(m, vu, co):
            candidat = m[id_candidat]
            if candidat.id in deja_vus:
                continue
            s = ressemblance(vu, candidat, co) * poids
            if s <= 0:
                continue
            scores[candidat.id] += s
            if s > raisons.get(candidat.id, (0, None))[0]:
                raisons[candidat.id] = (s, vu)

    retenus = [i for i, s in scores.items() if s >= SEUIL]
    retenus.sort(key=lambda i: (-scores[i], not m.disponible(i, numero), m[i].titre))
    resultat, revues_vues = [], set()
    for i in retenus:
        if len(resultat) >= n:
            break
        vu, candidat = raisons[i][1], m[i]
        if candidat.CLE == "revue":  # un seul numero par revue : de la variete
            if candidat.titre in revues_vues:
                continue
            revues_vues.add(candidat.titre)
        verbe = "vu" if vu.CLE == "dvd" else "lu"
        if vu.CLE == candidat.CLE == "revue" and vu.titre == candidat.titre:
            raison = f"Un autre numéro de « {vu.titre} »"
        elif ressemblance(vu, candidat) < SEUIL:  # le lien vient des usages, pas du contenu
            raison = f"Les lecteurs de « {vu.titre} » l'ont aussi emprunté"
        elif vu.CLE == "revue" and candidat.CLE != "revue":
            raison = f"Pour prolonger votre lecture de « {vu.titre} »"
        else:
            raison = f"Parce que vous avez {verbe} « {vu.titre} »"
        resultat.append((candidat, raison))
    # fonds sans fiches (genres, themes) : rien de ressemblant, on propose les plus demandes
    return resultat or repli()
