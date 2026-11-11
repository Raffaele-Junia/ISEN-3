"""Comptes utilisateurs et authentification.

- Mots de passe haches avec scrypt (lent, resistant au GPU) et un sel aleatoire
  par compte : jamais stockes en clair.
- Comparaison en temps constant (hmac.compare_digest).
- Message d'erreur identique que l'identifiant existe ou non, et hachage
  effectue meme pour un identifiant inconnu (pas de fuite par le temps).
- Delai progressif par identifiant apres plusieurs echecs (1, 2, 4... s,
  plafonne) : la force brute reste lente, sans qu'un tiers puisse bloquer
  longtemps un compte (le responsable notamment).
- Utilisable depuis plusieurs threads (site web) : un petit verrou interne
  protege le registre et les compteurs d'echecs, mais le hachage scrypt
  (lent) se fait toujours EN DEHORS de ce verrou (W1).
"""
import hashlib
import hmac
import math
import re
import secrets
import threading
import time
from dataclasses import dataclass, replace

from .exceptions import AuthentificationError, CompteBloqueError, MediathequeError

ADHERENT = "adherent"
RESPONSABLE = "responsable"
ROLES = (ADHERENT, RESPONSABLE)

MAX_ECHECS = 5            # echecs consecutifs tolores sans delai
DELAI_BASE_S = 1          # delai apres le MAX_ECHECS-ieme echec, double ensuite
DELAI_MAX_S = 60          # plafond du delai
DUREE_BLOCAGE_S = DELAI_MAX_S  # attente maximale (nom historique)
OUBLI_S = 3600            # compteur oublie apres 1 h sans echec
_MAX_SUIVIS = 10_000      # au-dela, purge des compteurs perimes
_FORMAT_IDENTIFIANT = re.compile(r"[a-z0-9._-]{3,32}")

# --- Hachage scrypt ----------------------------------------------------------
# Production : minimum OWASP (N=2**17, r=8, p=1), soit 128 Mo de memoire.
_MAXMEM = 256 * 2**20
_SCRYPT = {"n": 2**17, "r": 8, "p": 1, "dklen": 32, "maxmem": _MAXMEM}
# Parametres utilises pour les NOUVEAUX hashes. Seuls les tests les abaissent
# (tests/conftest.py) ; ne jamais les modifier en production.
parametres_scrypt = _SCRYPT
# Hashes d'avant S6 : 32 octets bruts, N=2**14 (toujours acceptes, puis
# re-haches avec les parametres courants a la connexion suivante).
_SCRYPT_HISTORIQUE = {"n": 2**14, "r": 8, "p": 1, "dklen": 32, "maxmem": _MAXMEM}
# Format actuel : b"$s1$" + log2(n), r, p (1 octet chacun) + empreinte de 32 octets.
_PREFIXE = b"$s1$"
_DKLEN = 32


def _encoder(params, empreinte):
    if params["n"] == _SCRYPT_HISTORIQUE["n"] and params["r"] == 8 and params["p"] == 1:
        return empreinte  # format historique (brut)
    return _PREFIXE + bytes((params["n"].bit_length() - 1, params["r"], params["p"])) + empreinte


def parametres_du_hash(hash_mdp):
    """Parametres scrypt d'un hash stocke. Leve ValueError s'ils sont invalides
    ou demesures (base falsifiee : deni de service par la memoire)."""
    if not (hash_mdp.startswith(_PREFIXE) and len(hash_mdp) == len(_PREFIXE) + 3 + _DKLEN):
        return _SCRYPT_HISTORIQUE
    log_n, r, p = hash_mdp[len(_PREFIXE):len(_PREFIXE) + 3]
    if not (1 <= log_n <= 20 and 1 <= r <= 32 and 1 <= p <= 16
            and 128 * r * (2**log_n + p) <= _MAXMEM - 2**20):
        raise ValueError("parametres de hachage invalides")
    return {"n": 2**log_n, "r": r, "p": p, "dklen": _DKLEN, "maxmem": _MAXMEM}


def _memes_parametres(a, b):
    return all(a[k] == b[k] for k in ("n", "r", "p", "dklen"))


def hacher(mot_de_passe, sel, params=None):
    """Hash encode (parametres inclus) ; `params` par defaut : parametres_scrypt."""
    params = parametres_scrypt if params is None else params
    empreinte = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, n=params["n"],
                               r=params["r"], p=params["p"], dklen=params["dklen"],
                               maxmem=params.get("maxmem", _MAXMEM))
    return _encoder(params, empreinte)


def valider_mot_de_passe(mot_de_passe):
    if (len(mot_de_passe) < 8 or not re.search(r"[A-Za-z]", mot_de_passe)
            or not re.search(r"\d", mot_de_passe)):
        raise MediathequeError(
            "Mot de passe trop faible : 8 caractères minimum, avec des lettres et des chiffres.")


@dataclass(frozen=True)
class Compte:
    """Immuable : un changement de mot de passe remplace le compte dans le registre."""
    identifiant: str
    hash_mdp: bytes
    sel: bytes
    role: str
    numero_adherent: str | None = None

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role invalide : {self.role}")
        if self.role == ADHERENT and not self.numero_adherent:
            raise ValueError("un compte adherent doit etre lie a un numero d'adherent")
        parametres_du_hash(self.hash_mdp)  # ValueError si parametres falsifies

    def __repr__(self):  # ne jamais afficher le hash ni le sel
        return f"Compte({self.identifiant!r}, role={self.role!r})"


class GestionComptes:

    def __init__(self, horloge=time.monotonic):
        self._comptes = {}
        self._echecs = {}  # identifiant -> (nb_echecs, bloque_jusqu_a, dernier_echec)
        self._horloge = horloge
        self._sel_leurre = secrets.token_bytes(16)
        # protege _comptes et _echecs ; jamais tenu pendant un hachage (W1)
        self._verrou = threading.Lock()

    def __iter__(self):
        with self._verrou:
            return iter(list(self._comptes.values()))

    def __len__(self):
        return len(self._comptes)

    def __contains__(self, identifiant):
        return identifiant in self._comptes

    def ajouter(self, compte):
        with self._verrou:
            if compte.identifiant in self._comptes:
                raise MediathequeError(f"Cet identifiant est déjà pris : {compte.identifiant}.")
            self._comptes[compte.identifiant] = compte

    def verifier_nouveau(self, identifiant, mot_de_passe):
        """Controles d'un futur compte SANS rien modifier : format de
        l'identifiant, unicite, politique de mot de passe. Renvoie
        l'identifiant normalise."""
        identifiant = identifiant.strip().lower()
        if not _FORMAT_IDENTIFIANT.fullmatch(identifiant):
            raise MediathequeError(
                "identifiant invalide : 3 a 32 caracteres parmi a-z 0-9 . _ -")
        if identifiant in self._comptes:
            raise MediathequeError(f"Cet identifiant est déjà pris : {identifiant}.")
        valider_mot_de_passe(mot_de_passe)
        return identifiant

    def creer(self, identifiant, mot_de_passe, role, numero_adherent=None):
        identifiant = self.verifier_nouveau(identifiant, mot_de_passe)
        sel = secrets.token_bytes(16)
        compte = Compte(identifiant, hacher(mot_de_passe, sel), sel, role, numero_adherent)
        self.ajouter(compte)
        return compte

    def get(self, identifiant):
        """Compte actuellement enregistre pour cet identifiant (ou None)."""
        return self._comptes.get(identifiant)

    def synchroniser(self, autre):
        """Aligne le registre sur `autre` (comptes relus en base). Un compte
        identique garde son objet actuel : les sessions ouvertes dessus restent
        valides ; un compte different ou disparu les revoque (S4)."""
        with self._verrou:
            actuels = self._comptes
            self._comptes = {
                c.identifiant: (actuels[c.identifiant]
                                if actuels.get(c.identifiant) == c else c)
                for c in autre}

    def supprimer(self, identifiant):
        with self._verrou:
            self._comptes.pop(identifiant, None)

    def compte_de_adherent(self, numero):
        return next((c for c in self if c.numero_adherent == numero), None)

    def authentifier(self, identifiant, mot_de_passe):
        identifiant = identifiant.strip().lower()
        with self._verrou:
            maintenant = self._horloge()
            _, bloque_jusqu_a, _ = self._echecs.get(identifiant, (0, 0.0, 0.0))
            if bloque_jusqu_a > maintenant:
                # refuse meme le bon mot de passe ; la tentative n'est pas comptee
                raise CompteBloqueError(math.ceil(bloque_jusqu_a - maintenant))
            compte = self._comptes.get(identifiant)
            historiques = self._a_des_hash_anciens()

        # hachage (lent) hors du verrou interne
        sel = compte.sel if compte else self._sel_leurre
        params = parametres_du_hash(compte.hash_mdp) if compte else parametres_scrypt
        a_jour = _memes_parametres(params, parametres_scrypt)
        # calcule meme si le compte est inconnu (pas de fuite par le temps)
        calcule = hacher(mot_de_passe, sel) if a_jour else hacher(mot_de_passe, sel, params)
        # Cout constant (W7) : tant qu'il reste des hashes anciens, CHAQUE
        # tentative coute un hash courant + un hash historique, que le compte
        # soit a jour, ancien ou inconnu (le second est un leurre).
        if not a_jour:
            hacher(mot_de_passe, self._sel_leurre)
        elif historiques:
            hacher(mot_de_passe, self._sel_leurre, _SCRYPT_HISTORIQUE)
        if compte is not None and hmac.compare_digest(calcule, compte.hash_mdp):
            with self._verrou:
                self._echecs.pop(identifiant, None)
            if not a_jour:  # hash ancien : re-hache avec les parametres courants
                compte = self._remplacer_mot_de_passe(compte, mot_de_passe)
            return compte

        with self._verrou:
            # relu sous le verrou : deux echecs simultanes comptent bien pour deux
            nb, _, dernier = self._echecs.get(identifiant, (0, 0.0, 0.0))
            if nb and maintenant - dernier > OUBLI_S:
                nb = 0
            nb += 1
            delai = 0.0
            if nb >= MAX_ECHECS:
                delai = min(DELAI_BASE_S * 2 ** (nb - MAX_ECHECS), DELAI_MAX_S)
            self._echecs[identifiant] = (nb, maintenant + delai, maintenant)
            if len(self._echecs) > _MAX_SUIVIS:
                self._purger(maintenant)
        raise AuthentificationError()

    def _a_des_hash_anciens(self):
        """Vrai s'il reste un compte au hash non courant (format d'avant S6).
        Information globale, identique pour tous les identifiants : elle ne
        renseigne pas sur l'existence d'un compte. Appelee sous self._verrou."""
        return any(not _memes_parametres(parametres_du_hash(c.hash_mdp), parametres_scrypt)
                   for c in self._comptes.values())

    def _purger(self, maintenant):
        """Oublie les compteurs sans echec depuis OUBLI_S (memoire bornee).
        Appelee sous self._verrou."""
        self._echecs = {i: e for i, e in self._echecs.items()
                        if maintenant - e[2] <= OUBLI_S}

    def changer_mot_de_passe(self, identifiant, ancien, nouveau):
        compte = self.authentifier(identifiant, ancien)
        valider_mot_de_passe(nouveau)
        return self._remplacer_mot_de_passe(compte, nouveau)

    def reinitialiser_mot_de_passe(self, identifiant, nouveau):
        """Reserve au responsable (controle dans Session)."""
        compte = self._comptes.get(identifiant)
        if compte is None:
            raise MediathequeError(f"Aucun compte avec l'identifiant {identifiant}.")
        valider_mot_de_passe(nouveau)
        with self._verrou:
            self._echecs.pop(identifiant, None)
        return self._remplacer_mot_de_passe(compte, nouveau)

    def _remplacer_mot_de_passe(self, compte, nouveau):
        sel = secrets.token_bytes(16)
        nouveau_compte = replace(compte, sel=sel, hash_mdp=hacher(nouveau, sel))  # hors verrou
        with self._verrou:
            if self._comptes.get(compte.identifiant) is not compte:
                # compte remplace entre-temps (reinitialise ailleurs) : on
                # n'ecrase pas la modification la plus recente
                raise AuthentificationError()
            self._comptes[compte.identifiant] = nouveau_compte
        return nouveau_compte
