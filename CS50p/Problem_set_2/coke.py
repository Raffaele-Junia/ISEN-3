
def main():
    coke()


def coke():
    amount = 50
    print(f"Amount Due: {amount}")

    while amount > 0:
        value = int(input("Insert Coin: "))

        if value == 25:
            amount -= 25
        elif value == 10:
            amount -= 10
        elif value == 5:
            amount -= 5

        if amount > 0:
            print(f"Amount Due: {amount}")

    print(f"Change Owed: {-amount}")


main()
