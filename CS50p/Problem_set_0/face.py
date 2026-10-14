def main():
    text = input("What's your message? ")
    text = text.replace(":)", "🙂")
    text = text.replace(":(", "🙁")
    print(text)

main() 