import random


def main():
    level = get_level()
    score = get_score(level)
    print(f"Score: {score}")

def get_level():
    while True:
        try:
            level = int(input("Level: "))
            if 1<=level<=3:
                return level
        except ValueError:
            pass


def generate_integer(level):
    if level == 1:
        return random.randint(0, 9)
    elif level == 2:
        return random.randint(10, 99)
    elif level == 3:
        return random.randint(100, 999)
    else:
        raise ValueError


def get_score(level):
    score = 0

    for _ in range(10):
        x = generate_integer(level)
        y = generate_integer(level)
        attempts = 0

        while attempts < 3:
            try:
                answer = int(input(f"{x} + {y} = "))

                if answer == x + y:
                    score += 1
                    break

                print("EEE")
                attempts += 1

            except ValueError:
                print("EEE")
                attempts += 1

        if attempts == 3:
            pass

    return score


if __name__ == "__main__":
    main()