import re

# N° de carte : « A » et trois chiffres ASCII (pas de « A١٢٣ ») (Z7).
FORMAT_NUMERO = re.compile(r"A[0-9]{3}")


class Adherent:

    QUOTAS = {"standard": 3, "premium": 6}

    def __init__(self, numero, nom, prenom, type):
        if not self.valider_numero(numero):
            raise ValueError(f"numero d'adherent invalide : {numero}")
        self._numero = numero
        self.nom = nom
        self.prenom = prenom
        self.type = type

    @property
    def numero(self):
        return self._numero

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, valeur):
        if valeur not in self.QUOTAS:
            raise ValueError(f"type d'adherent invalide : {valeur}")
        self._type = valeur

    @property
    def quota(self):
        return self.QUOTAS[self.type]

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom.upper()}"

    @staticmethod
    def valider_numero(numero):
        return isinstance(numero, str) and FORMAT_NUMERO.fullmatch(numero) is not None

    @classmethod
    def from_csv_row(cls, row):
        return cls(row["numero"], row["nom"], row["prenom"], row["type"])

    def to_csv_row(self):
        return {
            "numero": self.numero,
            "nom": self.nom,
            "prenom": self.prenom,
            "type": self.type,
        }

    def __str__(self):
        return f"{self.numero} - {self.nom_complet} ({self.type})"