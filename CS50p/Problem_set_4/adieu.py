import inflect

def main():
    adieu()

def adieu():
    p = inflect.engine()
    result = []
    while True:
        try:
            result.append(input("Name: "))
        except KeyboardInterrupt:
            break
    print("Adieu, adieu, to",p.join(result))

main()