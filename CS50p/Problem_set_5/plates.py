import string


def main():
    plate = input("Plate: ")
    if is_valid(plate):
        print("Valid")
    else:
        print("Invalid")


def is_valid(s):
    if len(s) < 2 or len(s) > 6:
        return False

    if s[0] not in string.ascii_letters or s[1] not in string.ascii_letters:
        return False

    digit = 0

    for letter in s:
        if letter in string.digits:
            if digit == 0 and letter == "0":
                return False
            digit += 1

        elif digit > 0:
            return False

        elif letter not in string.ascii_letters:
            return False

    return True


if __name__ == "__main__":
    main()
