import sympy as sp

# ==========================
# 1. Variables symboliques
# ==========================
q1, q2, d1, d3 = sp.symbols('q1 q2 d1 d3')

# ==========================
# 2. Matrice DH standard
# ==========================
def DH(theta, d, a, alpha):
    return sp.Matrix([
        [sp.cos(theta), -sp.sin(theta)*sp.cos(alpha),  sp.sin(theta)*sp.sin(alpha), a*sp.cos(theta)],
        [sp.sin(theta),  sp.cos(theta)*sp.cos(alpha), -sp.cos(theta)*sp.sin(alpha), a*sp.sin(theta)],
        [0,              sp.sin(alpha),               sp.cos(alpha),              d],
        [0,              0,                           0,                          1]
    ])

# ==========================
# 3. Matrices d'après le tableau du prof
# ==========================
# Ligne 1 : q = q1, d = d1, a = 0, alpha = pi/2
A1 = DH(q1, d1, 0, sp.pi/2)

# Ligne 2 : q = q2, d = d2, a = a2, alpha = 0
A2 = DH(q2, 0, 0, sp.pi/2)

# Ligne 3 : q = q3, d = 0, a = a3, alpha = 0
A3 = DH(0,d3,0,0)

print("A1:")
sp.pprint(A1)
print("A2:")
sp.pprint(A2)
print("A1:")
sp.pprint(A3)

# ==========================
# 4. Modèle Géométrique Direct (T03)
# ==========================
T03 = sp.trigsimp(A1 * A2 * A3)
print("Matrice homogène T03 :\n")
sp.pprint(T03)

# Extraction des composantes de la position P
Px = sp.trigsimp(T03[0, 3])
Py = sp.trigsimp(T03[1, 3])
Pz = sp.trigsimp(T03[2, 3])

print("--- Vecteur Position P ---")
print("Px =")
sp.pprint(Px)
print("\nPy =")
sp.pprint(Py)
print("\nPz =")
sp.pprint(Pz)

# ==========================
# 5. Calcul du Jacobien (Jv)
# ==========================
#P = sp.Matrix([Px, Py, Pz])
#q = sp.Matrix([q1, q2, d3])

#Jv = sp.trigsimp(P.jacobian(q))

#print("\n--- Matrice Jacobienne Jv ---")
#sp.pprint(Jv)