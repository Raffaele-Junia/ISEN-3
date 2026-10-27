def main():
    text = input("Input: ")
    shorten(text)


def shorten(word):
    for letter in word:
        if letter.lower() not in ["a", "e", "i", "o", "u"]:
            print(letter, end="")
    print()


main()
