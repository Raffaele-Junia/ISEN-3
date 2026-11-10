from dataclasses import dataclass
from datetime import date, timedelta

EN_ATTENTE = "en_attente"   # dans la file, le document est encore emprunte
DISPONIBLE = "disponible"   # document rendu et mis de cote pour cet adherent
HONOREE = "honoree"         # l'adherent a emprunte le document
ANNULEE = "annulee"
EXPIREE = "expiree"         # pas venu le chercher dans le delai

STATUTS = (EN_ATTENTE, DISPONIBLE, HONOREE, ANNULEE, EXPIREE)
ACTIFS = (EN_ATTENTE, DISPONIBLE)

DELAI_RETRAIT_JOURS = 3     # duree de mise de cote apres le retour
MAX_RESERVATIONS = 3        # reservations actives par adherent


@dataclass
class Reservation:
    id_document: str
    numero_adherent: str
    date_reservation: date
    statut: str = EN_ATTENTE
    date_disponible: date | None = None

    def __post_init__(self):
        if self.statut not in STATUTS:
            raise ValueError(f"statut de reservation invalide : {self.statut}")

    @property
    def active(self):
        return self.statut in ACTIFS

    @property
    def date_limite_retrait(self):
        if self.date_disponible is None:
            return None
        return self.date_disponible + timedelta(days=DELAI_RETRAIT_JOURS)

    def mettre_de_cote(self, jour):
        self.statut = DISPONIBLE
        self.date_disponible = jour

    @classmethod
    def from_csv_row(cls, row):
        dispo = row.get("date_disponible") or ""
        return cls(
            row["id_document"],
            row["numero_adherent"],
            date.fromisoformat(row["date_reservation"]),
            row["statut"],
            date.fromisoformat(dispo) if dispo else None,
        )

    def to_csv_row(self):
        return {
            "id_document": self.id_document,
            "numero_adherent": self.numero_adherent,
            "date_reservation": self.date_reservation.isoformat(),
            "statut": self.statut,
            "date_disponible": self.date_disponible.isoformat() if self.date_disponible else "",
        }
