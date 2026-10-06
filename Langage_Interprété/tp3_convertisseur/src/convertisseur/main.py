from convertisseur import (
    entete,
    formater,
    celsius_vers_fahrenheit,
    celsius_vers_kelvin,
    km_vers_miles,
    miles_vers_km
)


def main():
    print(entete())
    print(formater(celsius_vers_fahrenheit(25), "F"))
    print(formater(celsius_vers_kelvin(25), "K"))
    print(formater(km_vers_miles(10), "miles"))
    print(formater(miles_vers_km(5), "km"))


if __name__ == "__main__":
    main()