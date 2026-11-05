class Etudiant:

    DOMAINE = "isen.fr"

    def __init__(self, nom, prenom, numero):
        self.nom = nom
        self.prenom = prenom
        self.__numero = numero

    @property
    def numero(self):
        return self.__numero

    @property
    def nom_complet(self):
        return f"{self.prenom.title()} {self.nom.upper()}"

    @property
    def email(self):
        return f"{self.prenom.lower()}.{self.nom.lower()}@{self.DOMAINE}"

    def __str__(self):
        return f"{self.numero} - {self.nom_complet}"


class AuditeurLibre:

    def __init__(self, nom_complet, numero):
        self.nom_complet = nom_complet
        self.numero = numero

    def __str__(self):
        return f"{self.numero} - {self.nom_complet} (auditeur libre)"


class Groupe:

    ATTRIBUTS_REQUIS = ("numero", "nom_complet")

    def __init__(self, nom):
        self.nom = nom
        self._membres = {}

    def ajouter(self, personne):
        for attribut in self.ATTRIBUTS_REQUIS:
            if not hasattr(personne, attribut):
                return False

        self._membres[personne.numero] = personne
        return True

    def __len__(self):
        return len(self._membres)

    def __getitem__(self, numero):
        return self._membres[numero]

    def __iter__(self):
        return iter(self._membres.values())

    def __contains__(self, numero):
        return numero in self._membres

    def __str__(self):
        membres = "\n".join(
            str(membre) for membre in self._membres.values()
        )
        return f"Groupe {self.nom} ({len(self)} membres)\n{membres}"