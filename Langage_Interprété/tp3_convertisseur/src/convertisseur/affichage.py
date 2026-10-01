import datetime as dt

def entete():
    return "Convertisseur - " + str(dt.date.today())


def formater(valeur, unite):
    return f"{valeur:.2f} {unite}"