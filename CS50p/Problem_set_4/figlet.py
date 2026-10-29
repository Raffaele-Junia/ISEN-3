
from pyfiglet import Figlet
import sys
import random

def main():
    figlet()

def figlet():
    f = Figlet()

    if len(sys.argv) == 1:
        f.setFont(font=random.choice(f.getFonts()))

    elif len(sys.argv) == 3 and sys.argv[1] in ["-f", "--font"]:
        if sys.argv[2] not in f.getFonts():
            sys.exit("Invalid usage")
        f.setFont(font=sys.argv[2])

    else:
        sys.exit("Invalid usage")

    text = input("Input: ")
    print(f.renderText(text))

main()
