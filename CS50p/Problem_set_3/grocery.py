def main():
    caddy = grocery()
    for key,amount in caddy.items():
        print(f"{amount} {key.upper()}")

def grocery():
    caddy={}
    while True:
        try:
            item = input().lower().strip()
            if item not in caddy:
                caddy[item]=1
            else:
                caddy[item]+=1


        except KeyboardInterrupt:
            print()
            break
        except ValueError:
            pass
    return caddy    

main()