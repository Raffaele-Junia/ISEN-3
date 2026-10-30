def main():
    text = input("Input: ")
    short = shorten(text)


def shorten(word):
    short = ""
    for letter in word:
        if letter.lower() not in ["a", "e", "i", "o", "u"]:
            short += f"{letter}"
    return short


if __name__ == "__main__":
    main()
