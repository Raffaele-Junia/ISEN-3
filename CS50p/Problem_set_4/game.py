
import random

def main():
    niveau = get_level()
    game(niveau)

def get_level():
    while True:
        try:
            level = int(input("Level: "))
            if level > 0:
                return level
        except ValueError:
            pass

def game(level):
    choice = random.randint(1, level)

    while True:
        try:
            guess = int(input("Guess: "))

            if guess <= 0 or guess > level:
                continue

            if guess < choice:
                print("Too small!")
            elif guess > choice:
                print("Too large!")
            else:
                print("Just right!")
                break

        except ValueError:
            pass

if __name__ == "__main__":
    main()
