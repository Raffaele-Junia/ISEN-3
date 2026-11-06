class MediathequeError(Exception):
    """Classe de base de toutes les erreurs métier de la médiathèque."""


class DocumentInconnuError(MediathequeError):
    def __init__(self, id_document):
        self.id_document = id_document
        super().__init__(f"document inconnu : {id_document}")


class AdherentInconnuError(MediathequeError):
    def __init__(self, numero):
        self.numero = numero
        super().__init__(f"adherent inconnu : {numero}")


class DocumentIndisponibleError(MediathequeError):
    def __init__(self, titre):
        self.titre = titre
        super().__init__(f"document deja emprunte : {titre}")


class QuotaDepasseError(MediathequeError):
    def __init__(self, nb_actuel, quota):
        self.nb_actuel = nb_actuel
        self.quota = quota
        super().__init__(f"quota depasse : {nb_actuel}/{quota}")