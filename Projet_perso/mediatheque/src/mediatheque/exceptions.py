class MediathequeError(Exception):
    """Classe de base de toutes les erreurs métier de la médiathèque."""


class DocumentInconnuError(MediathequeError):
    def __init__(self, id_document):
        self.id_document = id_document
        super().__init__(f"Document inconnu : {id_document}.")


class AdherentInconnuError(MediathequeError):
    def __init__(self, numero):
        self.numero = numero
        super().__init__(f"Lecteur inconnu : {numero}.")


class DocumentIndisponibleError(MediathequeError):
    def __init__(self, titre, message=None):
        self.titre = titre
        super().__init__(message or f"« {titre} » est déjà emprunté.")


class ReservationImpossibleError(MediathequeError):
    """Reservation refusee (document disponible, doublon, limite atteinte...)."""


class AuthentificationError(MediathequeError):
    """Identifiant ou mot de passe incorrect (message volontairement vague)."""

    def __init__(self, message="Identifiant ou mot de passe incorrect"):
        super().__init__(message)


class CompteBloqueError(AuthentificationError):
    def __init__(self, secondes_restantes):
        self.secondes_restantes = secondes_restantes
        super().__init__(f"Trop de tentatives : réessayez dans {secondes_restantes} s")


class AccesRefuseError(MediathequeError):
    """Action interdite pour le role de l'utilisateur connecte."""


class QuotaDepasseError(MediathequeError):
    def __init__(self, nb_actuel, quota):
        self.nb_actuel = nb_actuel
        self.quota = quota
        super().__init__(f"Carte pleine : ce lecteur a déjà {nb_actuel} documents sur {quota}.")