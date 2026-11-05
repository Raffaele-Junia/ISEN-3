class Epreuve:

    def __init__(self, titre, duree_min):
        self.titre = titre
        self.duree_min = duree_min
        self._questions = []

    def ajouter(self, question):
        if not callable(getattr(question, "corriger", None)):
            return False

        self._questions.append(question)
        return True

    @property
    def bareme(self):
        return sum(question._points for question in self._questions)

    def corriger(self, reponses):
        total = 0

        for question, reponse in zip(self._questions, reponses):
            total += question.corriger(reponse)

        if self.bareme == 0:
            return 0

        return round((total / self.bareme) * 20, 2)

    def resultats(self, groupe, copies):
        result = {}

        for personne in groupe:
            if personne.numero in copies:
                result[personne.numero] = self.corriger(
                    copies[personne.numero]
                )

        return result

    def __len__(self):
        return len(self._questions)

    def __getitem__(self, index):
        return self._questions[index]

    def __iter__(self):
        return iter(self._questions)

    def __str__(self):
        texte = f"Epreuve {self.titre} ({self.duree_min} min, "
        texte += f"{len(self)} questions, {self.bareme} pts)\n"

        for i, question in enumerate(self._questions, start=1):
            texte += f"{i}. {question}\n"

        return texte.rstrip()