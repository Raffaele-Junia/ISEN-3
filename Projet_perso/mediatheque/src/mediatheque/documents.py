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

    def __init_subclass__(cls,**kwargs):
        super().__init__(**kwargs)
        if cls.CLE != "?":
            Document._registre[cls.CLE]=cls

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