"""Journal des actions du personnel (qui a fait quoi, quand).

Ajout seul : aucune methode ne modifie ni ne supprime une entree. On n'y ecrit
JAMAIS de mot de passe ; seulement des identifiants, titres et numeros.
"""
from dataclasses import dataclass
from datetime import datetime

ACTIONS = {
    "connexion": "Connexion",
    "pret": "Prêt",
    "retour": "Retour",
    "ajout_document": "Nouvelle acquisition",
    "retrait_document": "Document retiré",
    "ajout_lecteur": "Lecteur inscrit",
    "creation_compte": "Compte créé",
    "reinit_mdp": "Mot de passe réinitialisé",
    "modif_lecteur": "Fiche lecteur modifiée",
    "annul_reservation": "Réservation annulée pour un lecteur",
    "purge_journal": "Purge du journal (durée de conservation)",
}
# Duree de conservation des entrees (RGPD : le journal cite des lecteurs et les
# titres qu'ils empruntent). La purge n'est JAMAIS automatique : un responsable
# la lance avec `python -m mediatheque.purge_journal` (Mediatheque.purger_journal).
CONSERVATION_JOURNAL_JOURS = 365
_LONGUEURS = {"acteur": 64, "cible": 40, "detail": 300}


@dataclass(frozen=True)
class EntreeJournal:
    horodatage: datetime
    acteur: str
    action: str
    cible: str = ""
    detail: str = ""

    def __post_init__(self):
        if self.action not in ACTIONS:
            raise ValueError(f"action de journal inconnue : {self.action}")
        for champ, maxi in _LONGUEURS.items():
            if len(getattr(self, champ)) > maxi:
                raise ValueError(f"{champ} trop long dans le journal")

    @property
    def libelle(self):
        return ACTIONS[self.action]
