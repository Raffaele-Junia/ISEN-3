import sympy as sp

q1, q2, q3 = sp.symbols('q1 q2 q3')
d1, a1, a2, d2, a3 = sp.symbols('d1 a1 a2 d2 a3')

def dh_matrix(theta, d, r, alpha):
    return sp.Matrix([
        [
            sp.cos(theta),
            -sp.cos(alpha) * sp.sin(theta),
            sp.sin(alpha) * sp.sin(theta),
            r * sp.cos(theta)
        ],
        [
            sp.sin(theta),
            sp.cos(alpha) * sp.cos(theta),
            -sp.sin(alpha) * sp.cos(theta),
            r * sp.sin(theta)
        ],
        [
            0,
            sp.sin(alpha),
            sp.cos(alpha),
            d
        ],
        [
            0,
            0,
            0,
            1
        ]
    ])

T01 = dh_matrix(q1, d1, a1, sp.pi/2)
T12 = dh_matrix(q2, d2,  a2, 0)
T23 = dh_matrix(q3, 0,  a3,  0)

T03 = sp.simplify(T01 * T12 * T23)

sp.pprint(T03)