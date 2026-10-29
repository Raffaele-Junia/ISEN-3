import emoji

def main():
    emojize()

def emojize():
    result = input("Input: ")
    print(emoji.emojize(f"Output: {result}"))

main()