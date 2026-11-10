from abc import ABC, abstractmethod
import csv

class Document(ABC):

    TYPE = "?"
    CLE = "?"

    _registre = {}

    def __init__(self,id,titre,annee,extra):
        self.id = id
        self.titre = titre
        self.annee = annee
        self._extra = extra

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.CLE != "?":
            Document._registre[cls.CLE] = cls

    @property
    @abstractmethod
    def duree_pret_jour(self):
        pass

    @property
    @abstractmethod
    def detail(self):
        pass

    @classmethod
    @abstractmethod
    def from_extra(cls,_extra):
        pass

    @classmethod
    def from_csv_row(cls, row):
        type_doc = row["type"]
        try:
            classe = cls._registre[type_doc]
        except KeyError:
            raise ValueError(f"type de document inconnu : {type_doc}") from None

        return classe(
            row["id"],
            row["titre"],
            int(row["annee"]),
            classe.from_extra(row["extra"]),
        )

    def to_csv_row(self):
        return {
            "id" : self.id,
            "type" : self.CLE,
            "titre" : self.titre,
            "annee" : self.annee,
            "extra" : str(self._extra)
        }

    def __eq__(self,autre):
        if not isinstance(autre,Document):
            return NotImplemented
        return self.id == autre.id

    def __hash__(self):
        return hash(self.id)

    def __lt__(self,autre):
            if not isinstance(autre,Document):
                return NotImplemented
            return self.titre < autre.titre

    def __str__(self):
        return f"[{self.TYPE}] {self.titre} ({self.annee}) - {self.detail}"

    def __repr__(self):
        return f"{type(self).__name__}({self.id!r}, {self.titre!r}, {self.annee!r})"


class Livre(Document):

    TYPE = "Livre"
    CLE = "livre"

    def __init__(self,id,titre,annee,auteur):
        super().__init__(id,titre,annee,auteur)

    @property
    def auteur(self):
        return self._extra

    @property
    def duree_pret_jour(self):
        return 21

    @property
    def detail(self):
        return self.auteur

    @classmethod
    def from_extra(cls, extra):
        return extra

class DVD(Document):
    TYPE = "DVD"
    CLE = "dvd"

    def __init__(self,id,titre,annee,duree_min):
        super().__init__(id,titre,annee,duree_min)

    @property
    def duree_min(self):
        return self._extra

    @property
    def duree_pret_jour(self):
        return 7

    @property
    def detail(self):
        return f"{self.duree_min} min"

    @classmethod
    def from_extra(cls, extra):
        return int(extra)

class Revue(Document):
    TYPE = "Revue"
    CLE = "revue"

    def __init__(self,id,titre,annee,numero):
        super().__init__(id,titre,annee,numero)

    @property
    def numero(self):
        return self._extra

    @property
    def duree_pret_jour(self):
        return 7

    @property
    def detail(self):
        return f"n {self.numero}"

    @classmethod
    def from_extra(cls, extra):
        return int(extra)