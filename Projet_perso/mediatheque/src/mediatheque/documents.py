from abc import ABC, abstractmethod
import re

# Metadonnees OPTIONNELLES d'une fiche (absentes des anciens CSV / bases).
CHAMPS_FICHE = ("genre", "themes", "resume", "editeur", "pages", "isbn", "public")
PUBLICS = ("", "tout public", "jeunesse", "ado", "adulte")
_LONGUEURS_MAX = {"genre": 60, "resume": 1200, "editeur": 80, "public": 20}
_FORMAT_ISBN = re.compile(r"(97[89])?\d{9}[\dX]")


class Document(ABC):

    TYPE = "?"
    CLE = "?"

    _registre = {}

    def __init__(self,id,titre,annee,extra):
        self.id = id
        self.titre = titre
        self.annee = annee
        self._extra = extra
        self.genre = ""
        self.themes = ()
        self.resume = ""
        self.editeur = ""
        self.pages = 0
        self.isbn = ""
        self.public = ""

    def completer_fiche(self, **fiche):
        """Renseigne les metadonnees de la fiche, validees. Renvoie self."""
        inconnus = set(fiche) - set(CHAMPS_FICHE)
        if inconnus:
            raise ValueError(f"champ de fiche inconnu : {', '.join(sorted(inconnus))}")
        for cle, valeur in fiche.items():
            if valeur is None:
                continue
            if cle == "themes":
                if isinstance(valeur, str):
                    valeur = valeur.split("|")
                valeur = tuple(" ".join(t.split()).lower()[:40] for t in valeur if t and t.strip())[:8]
                if any("|" in t for t in valeur):  # separateur de stockage (F5)
                    raise ValueError("un theme ne peut pas contenir le caractere |")
            elif cle == "pages":
                valeur = int(valeur or 0)
                if not 0 <= valeur <= 20000:
                    raise ValueError(f"nombre de pages invalide : {valeur}")
            elif cle == "isbn":
                valeur = str(valeur).replace("-", "").replace(" ", "").upper()
                if valeur and not _FORMAT_ISBN.fullmatch(valeur):
                    raise ValueError(f"ISBN invalide : {valeur}")
            else:
                valeur = " ".join(str(valeur).split())  # pas de retours ni de blancs multiples
                if len(valeur) > _LONGUEURS_MAX[cle]:
                    raise ValueError(f"{cle} trop long ({len(valeur)} caracteres)")
                if cle == "public" and valeur not in PUBLICS:
                    raise ValueError(f"public invalide : {valeur}")
            setattr(self, cle, valeur)
        return self

    @property
    def fiche(self):
        """Metadonnees de la fiche, au format de stockage (themes en 'a|b|c')."""
        return {"genre": self.genre, "themes": "|".join(self.themes), "resume": self.resume,
                "editeur": self.editeur, "pages": self.pages, "isbn": self.isbn,
                "public": self.public}

    @property
    def createur(self):
        """Auteur d'un livre ; vide sinon (utile aux recommandations)."""
        return ""

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

        document = classe(
            row["id"],
            row["titre"],
            int(row["annee"]),
            classe.from_extra(row["extra"]),
        )
        fiche = {c: row.get(c) for c in CHAMPS_FICHE if row.get(c) not in (None, "")}
        return document.completer_fiche(**fiche)

    def to_csv_row(self):
        return {
            "id" : self.id,
            "type" : self.CLE,
            "titre" : self.titre,
            "annee" : self.annee,
            "extra" : str(self._extra),
            **self.fiche,
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
    def createur(self):
        return self.auteur

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