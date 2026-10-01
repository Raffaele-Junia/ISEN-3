from convertisseur.constantes import KELVIN_OFFSET

def celsius_vers_fahrenheit(c):
    return (c * 9/5) + 32

def celsius_vers_kelvin(c):
    return c + KELVIN_OFFSET