from colorama import Fore, Style,init
init(autoreset=True)
import string

def _contient_type(mot_de_passe: str, ensemble: str) -> bool:
    return any(caractere in ensemble for caractere in mot_de_passe)

def analyser_mot_de_passe ( mot_de_passe : str ) -> str:

    a_lettres = _contient_type(mot_de_passe, string.ascii_letters)
    a_chiffres = _contient_type(mot_de_passe, string.digits)
    a_symboles = _contient_type(mot_de_passe, string.punctuation)

    types_presents = sum([a_lettres, a_chiffres, a_symboles])

    if len(mot_de_passe) >= 12 and a_lettres and a_chiffres and a_symboles:
        return Fore.GREEN + "[FORT] Mot de passe tres solide."

    if len(mot_de_passe) >= 8 and types_presents >= 2:
        return Fore.YELLOW + "[MOYEN]"

    else:
        return Fore.RED + "[FAIBLE]"