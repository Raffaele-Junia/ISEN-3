def main():
    fuel()

def fuel():
    while True:
        try:
            fraction = input("Fraction: ")
            x,y = fraction.split("/")
            x = int(x)
            y = int(y)

            if y==0 or x > y :
                continue

            percentage = round(x/y*100)

            if percentage == 0:
                print("E")
            elif percentage == 100:
                print("F")
            else:
                print(f"{percentage}%")
        except ValueError:
            pass
        except ZeroDivisionError:
            pass

        break

main()