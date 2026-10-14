def main():
    response = input("What is your response? ").lower().replace("-", " ")
    if response == "42" or response == "forty two":
        print("Yes")
    else:
        print("No")

main()
