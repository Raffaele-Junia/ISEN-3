"""Comptes utilisateurs et authentification.

- Mots de passe haches avec scrypt (lent, resistant au GPU) et un sel aleatoire
  par compte : jamais stockes en clair.
- Comparaison en temps constant (hmac.compare_digest).
- Message d'erreur identique que l'identifiant existe ou non, et hachage
  effectue meme pour un identifiant inconnu (pas de fuite par le temps).
- Blocage temporaire apres plusieurs echecs.
"""
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass, replace

from .exceptions import AuthentificationError, CompteBloqueError, MediathequeError

ADHERENT = "adherent"
RESPONSABLE = "responsable"
ROLES = (ADHERENT, RESPONSABLE)

MAX_ECHECS = 5
DUREE_BLOCAGE_S = 300
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
_FORMAT_IDENTIFIANT = re.compile(r"[a-z0-9._-]{3,32}")


def hacher(mot_de_passe, sel):
    return hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, **_SCRYPT)


def valider_mot_de_passe(mot_de_passe):
    if (len(mot_de_passe) < 8 or not re.search(r"[A-Za-z]", mot_de_passe)
            or not re.search(r"\d", mot_de_passe)):
        raise MediathequeError(
            "mot de passe trop faible : 8 caracteres minimum, avec lettres et chiffres")


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

    def __repr__(self):  # ne jamais afficher le hash ni le sel
        return f"Compte({self.identifiant!r}, role={self.role!r})"


class GestionComptes:

    def __init__(self, horloge=time.monotonic):
        self._comptes = {}
        self._echecs = {}  # identifiant -> (nb_echecs, bloque_jusqu_a)
        self._horloge = horloge
        self._sel_leurre = secrets.token_bytes(16)

    def __iter__(self):
        return iter(self._comptes.values())

    def __len__(self):
        return len(self._comptes)

    def __contains__(self, identifiant):
        return identifiant in self._comptes

    def ajouter(self, compte):
        if compte.identifiant in self._comptes:
            raise MediathequeError(f"identifiant deja utilise : {compte.identifiant}")
        self._comptes[compte.identifiant] = compte

    def creer(self, identifiant, mot_de_passe, role, numero_adherent=None):
        identifiant = identifiant.strip().lower()
        if not _FORMAT_IDENTIFIANT.fullmatch(identifiant):
            raise MediathequeError(
                "identifiant invalide : 3 a 32 caracteres parmi a-z 0-9 . _ -")
        valider_mot_de_passe(mot_de_passe)
        sel = secrets.token_bytes(16)
        compte = Compte(identifiant, hacher(mot_de_passe, sel), sel, role, numero_adherent)
        self.ajouter(compte)
        return compte

    def supprimer(self, identifiant):
        self._comptes.pop(identifiant, None)

    def compte_de_adherent(self, numero):
        return next((c for c in self._comptes.values()
                     if c.numero_adherent == numero), None)

    def authentifier(self, identifiant, mot_de_passe):
        identifiant = identifiant.strip().lower()
        maintenant = self._horloge()
        nb, bloque_jusqu_a = self._echecs.get(identifiant, (0, 0.0))
        if bloque_jusqu_a > maintenant:
            raise CompteBloqueError(int(bloque_jusqu_a - maintenant) + 1)

        compte = self._comptes.get(identifiant)
        sel = compte.sel if compte else self._sel_leurre
        calcule = hacher(mot_de_passe, sel)  # calcule meme si compte inconnu
        if compte is not None and hmac.compare_digest(calcule, compte.hash_mdp):
            self._echecs.pop(identifiant, None)
            return compte

        nb += 1
        if nb >= MAX_ECHECS:
            self._echecs[identifiant] = (0, maintenant + DUREE_BLOCAGE_S)
        else:
            self._echecs[identifiant] = (nb, 0.0)
        raise AuthentificationError()

    def changer_mot_de_passe(self, identifiant, ancien, nouveau):
        compte = self.authentifier(identifiant, ancien)
        valider_mot_de_passe(nouveau)
        return self._remplacer_mot_de_passe(compte, nouveau)

    def reinitialiser_mot_de_passe(self, identifiant, nouveau):
        """Reserve au responsable (controle dans Session)."""
        compte = self._comptes.get(identifiant)
        if compte is None:
            raise MediathequeError(f"compte inconnu : {identifiant}")
        valider_mot_de_passe(nouveau)
        self._echecs.pop(identifiant, None)
        return self._remplacer_mot_de_passe(compte, nouveau)

    def _remplacer_mot_de_passe(self, compte, nouveau):
        sel = secrets.token_bytes(16)
        nouveau_compte = replace(compte, sel=sel, hash_mdp=hacher(nouveau, sel))
        self._comptes[compte.identifiant] = nouveau_compte
        return nouveau_compte
