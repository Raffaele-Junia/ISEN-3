logs_connexions = [" user_102 ", " user_405 ", " user_102 ", " user_88 ", "user_405 ", " user_301 "]

logs_connexion = list(set(logs_connexions))

projet_alpha = {" Python ", " Linux ", " Docker ", "SQL "}
projet_beta = {" Python ", " AWS", " Kubernetes ", " Docker "}

print(projet_alpha & projet_beta)
print(projet_beta | projet_alpha)
print(projet_alpha - projet_beta)

panier = {"SSD": 89.99,"RAM 16GB": 65.0, "Clavier": 45.50}

panier["Souris"]= 25.0

print(panier["Souris"])

panier["SSD"] *= 1.1
print(panier["SSD"])

prix = panier.get("Ecran",0.0)
print(prix)

temperatures = [18.5 , 22.0 , 14.2 , 26.5 , 19.8 , 11.0 , 25.0]
temp=filter(lambda x:x>=20 ,temperatures)
print(list(temp))

etiquette= list(map(lambda x : "Chaud" if x>=20 else "Froid",temperatures))
print(etiquette)

capteurs = [" Sensor_A ", " Sensor_B ", " Sensor_C ", " Sensor_D "]
valeurs = [102.4 , 88.1 , 120.5 , 95.0]

dict1 = {capt:val for capt,val in zip(capteurs,valeurs) if val>=90}
print(dict1)

inverse = {val:capt for capt,val in dict1.items()}
print(inverse)

transactions = [120.0, -45.5, 300.0,-12.0, 85.0]
trans = list(filter(lambda x : x>=0 , transactions))
print(list(trans))

euro=list(map(lambda x: x*0.92,trans))
print(list(euro))

employes = [ {"nom": " Sophie ", " anciennete ": 5 , " salaire ": 42000},{"nom": " Alexandre ", " anciennete ": 2 , " salaire ": 35000},{"nom": " Elena ", " anciennete ": 8 , " salaire ": 58000},{"nom": " Marc ", " anciennete ": 5 , " salaire ": 39000}]

employe_tri= sorted(employes, key=lambda x : x[" salaire "], reverse=True)
print(employe_tri)

employe_tri = sorted(
    employes,
    key=lambda x: (x[" anciennete "], -x[" salaire "])
)

print(employe_tri)

etapes = ("Ingestion", "Nettoyage", "Transformation", "Export")

it = iter(etapes)

print(next(it))
print(next(it))
print(next(it))
print(next(it))

try:
    print(next(it))
except StopIteration:
    print("Fin de l'itérateur")

def fibonacci_sequence(longueur):
    a = 0
    b = 1

    for i in range(longueur):
        yield a
        a, b = b, a + b


for nombre in fibonacci_sequence(12):
    print(nombre)


print(list(fibonacci_sequence(0)))

print(list(fibonacci_sequence(1)))

etudiants = [
    ("Dupont", "Alice", [14.0, 16.5, 12.0]),
    ("Martin", "Bob", [8.0, 9.5, 10.0]),
    ("Bernard", "Charlie", [15.0, 18.0, 16.0])
]

registre = {}

for nom, prenom, notes in etudiants:
    moyenne = sum(notes) / len(notes)

    registre[nom] = {
        "prenom": prenom,
        "moyenne": moyenne
    }

for nom in registre:
    registre[nom]["option"] = registre[nom].get("option", "Aucune")

admis = {
    nom: infos
    for nom, infos in registre.items()
    if infos["moyenne"] >= 10.0
}

if admis:
    print("Nombre d'admis :", len(admis))
