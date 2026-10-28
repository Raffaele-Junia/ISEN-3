def main():
    outdated()

def outdated():
    months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
]
    while True:
        try:
            date = input("Date: ").strip()
            if "/" in date:
                month, day, year = date.split("/")
                day = int(day)
                year = int(year)
                month = int(month)
            else:
                month, day, year = date.replace(",", "").split()
                month = months.index(month.title())+1
                day = int(day)
                year = int(year)

            if day >= 1 and day <= 31 and month >= 1 and month<=12:
                print(f"{year:04}-{month:02}-{day:02}")
        except KeyboardInterrupt:
            break
        except ValueError:
            pass

main()