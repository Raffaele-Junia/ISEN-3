def moyenne(notes: list[float]) -> float:
    return round(sum(notes) / len(notes), 2)


def creer_filtre_admis(seuil: float):
    def filtre(note):
        return note >= seuil

    return filtre


INDICATEURS = {
    "moyenne": moyenne,
    "minimum": min,
    "maximum": max
}