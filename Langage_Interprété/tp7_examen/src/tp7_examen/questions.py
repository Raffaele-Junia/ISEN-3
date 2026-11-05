
from abc import ABC, abstractmethod

class Question(ABC):

    TYPE = "?"
    nb_questions = 0

    def __init__(self, enonce, points):
        self.enonce = enonce
        self._points = points
        Question.nb_questions += 1

    @property
    def points(self):
        return self._points

    @abstractmethod
    def corriger(self, reponse):
        pass

    def __str__(self):
        return f"[{self.TYPE}] {self.enonce} ({self.points} pts)"


class QuestionQCM(Question):

    TYPE = "QCM"

    def __init__(self, enonce, points, choix, bonne):
        super().__init__(enonce, points)
        self.choix = choix
        self.bonne = bonne

    def corriger(self, reponse):
        return self.points if reponse == self.bonne else 0

    def __len__(self):
        return len(self.choix)

class QuestionVraiFaux(Question):

    TYPE = "V/F"

    def __init__(self, enonce, points, vrai):
        super().__init__(enonce, points)
        self.vrai = vrai

    def corriger(self,reponse):
        return self.points if reponse == self.vrai else 0

class QuestionNumerique(Question):

    TYPE="NUM"

    def __init__(self, enonce, points, valeur, tolerance=0.0):
        super().__init__(enonce, points)
        self.valeur = valeur
        self.tolerance = tolerance

    def corriger(self,reponse):
        return self.points if abs(reponse - self.valeur) <= self.tolerance else 0

class QuestionOuverte(Question):

    TYPE="OUV"

    def __init__(self, enonce, points, mots_cles):
        super().__init__(enonce, points)
        self.mots_cles = mots_cles

    def corriger(self, reponse):
        reponse = reponse.lower()
        trouves = sum(1 for mot in self.mots_cles if mot.lower() in reponse)
        resultat = (trouves / len(self.mots_cles)) * self.points
        return round(resultat, 2)

