import sympy as sp
import numpy as np

# ==========================
# Variables symboliques
# ==========================
q1, q2, q3 = sp.symbols('q1 q2 q3')
d1, d2, a2, a3 = sp.symbols('d1 d2 a2 a3', positive=True)

# ==========================
# Matrice DH standard
# ==========================
def DH(theta, d, a, alpha):

    return sp.Matrix([
        [sp.cos(theta), -sp.sin(theta)*sp.cos(alpha),
         sp.sin(theta)*sp.sin(alpha), a*sp.cos(theta)],

        [sp.sin(theta), sp.cos(theta)*sp.cos(alpha),
         -sp.cos(theta)*sp.sin(alpha), a*sp.sin(theta)],

        [0, sp.sin(alpha), sp.cos(alpha), d],

        [0, 0, 0, 1]
    ])

# ==========================
# Matrices élémentaires
# ==========================
A1 = DH(q1, d1, 0, sp.pi/2)
A2 = DH(q2, d2, a2, 0)
A3 = DH(q3, 0, a3, 0)

# ==========================
# Modèle géométrique direct
# ==========================
T03 = sp.simplify(A1 * A2 * A3)

print("Matrice homogène T03 :")
sp.pprint(T03)

# ==========================
# Position de l'outil
# ==========================
Px = sp.simplify(T03[0,3])
Py = sp.simplify(T03[1,3])
Pz = sp.simplify(T03[2,3])

print("\nPosition de l'effecteur :")

print("Px = ") 
sp.pprint(Px)

print("Py = ") 
sp.pprint(Py)

print("Pz = ")
sp.pprint(Pz)


# ==========================
# Evaluation numérique
# ==========================

valeurs = {
    L1: 0.40,
    L2: 0.50,
    L3: 0.30,
    q1: np.deg2rad(30),
    q2: np.deg2rad(45),
    q3: np.deg2rad(-20)
}

print("\nT03 avec les valeurs numériques :")
print(T03.evalf(subs=valeurs))