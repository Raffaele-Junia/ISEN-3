from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Emprunt:
    id_document: str
    numero_adherent: str
    date_emprunt: date
    date_retour: date | None = None

    @property
    def en_cours(self):
        return self.date_retour is None

    def date_limite(self, duree_jours):
        return self.date_emprunt + timedelta(days=duree_jours)

    def jours_retard(self, duree_jours, aujourdhui):
        reference = self.date_retour if self.date_retour is not None else aujourdhui
        retard = (reference - self.date_limite(duree_jours)).days
        return max(0, retard)

    @classmethod
    def from_csv_row(cls, row):
        retour = row["date_retour"]
        return cls(
            row["id_document"],
            row["numero_adherent"],
            date.fromisoformat(row["date_emprunt"]),
            date.fromisoformat(retour) if retour else None,
        )

    def to_csv_row(self):
        return {
            "id_document": self.id_document,
            "numero_adherent": self.numero_adherent,
            "date_emprunt": self.date_emprunt.isoformat(),
            "date_retour": self.date_retour.isoformat() if self.date_retour else "",
        }