MORSE = {
    # Lettres
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",

    # Chiffres
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",

    # Ponctuation
    ".": ".-.-.-",
    ",": "--..--",
    "?": "..--..",
    "'": ".----.",
    "!": "-.-.--",
    "/": "-..-.",
    "(": "-.--.",
    ")": "-.--.-",
    "&": ".-...",
    ":": "---...",
    ";": "-.-.-.",
    "=": "-...-",
    "+": ".-.-.",
    "-": "-....-",
    "_": "..--.-",
    '"': ".-..-.",
    "$": "...-..-",
    "@": ".--.-.",
}

REVERSE_MORSE = {value: key for key, value in MORSE.items()}


def encode(text):
    result = []

    for char in text.upper():
        if char == " ":
            result.append("/")
        elif char in MORSE:
            result.append(MORSE[char])
        else:
            raise ValueError(f"Caractère non supporté : {char}")

    return " ".join(result)


def decode(morse):
    result = []

    for code in morse.split():
        if code == "/":
            result.append(" ")
        elif code in REVERSE_MORSE:
            result.append(REVERSE_MORSE[code])
        else:
            raise ValueError(f"Code Morse inconnu : {code}")

    return "".join(result)

print(encode("Hello, World!"))
print(decode(".... . .-.. .-.. --- --..-- / .-- --- .-. .-.. -.. -.-.--"))