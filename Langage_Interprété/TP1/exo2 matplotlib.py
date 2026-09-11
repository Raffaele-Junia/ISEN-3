import matplotlib.pyplot as plt
import numpy as np

mois=["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
visiteurs=[1200,1350,1600,1450,1800,2100,1950,1700,2200,2400,2600,3000]

fig, ax = plt.subplots()             # Create a figure containing a single Axes.
ax.plot(mois, visiteurs)  # Plot some data on the Axes.
ax.set_title('Visites 2026')
ax.set_ylabel('Visites')
ax.set_xlabel('Mois')
plt.show()                           # Show the figure.

