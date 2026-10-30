def main():
    greeting = input("Greeting: ")
    print(value(greeting))

def value(greeting):
    if greeting.lower().startswith("hello"):
        return f"$0"
    elif greeting.lower().startswith("h"):
        return f"$20"
    else:
        return f"$100"


if __name__ == "__main__":
    main()
