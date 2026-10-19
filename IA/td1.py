import pandas as pd
import numpy as np

df = pd.read_csv("C:\\Users\\raffa\\Desktop\\customers_tp.csv")

print("Dimensions initiales :", df.shape)
print("\nVariables :\n", df.columns.tolist())
print("\nTypes :\n", df.dtypes)
print("\nStatistiques numériques :\n", df.describe())
print("\nValeurs manquantes :\n", df.isna().sum())
print("\nNombre de lignes dupliquées :", df.duplicated().sum())

df.loc[df["Months Since Last Claim"] > 100, "Months Since Last Claim"] = np.nan

df.loc[df["Number of Policies"] <= 0, "Number of Policies"] = np.nan

colonnes_numeriques = [
    "Monthly Premium Auto",
    "Months Since Last Claim",
    "Number of Policies",
]
for colonne in colonnes_numeriques:
    df[colonne] = df[colonne].fillna(df[colonne].median())

for colonne in ["Education", "Vehicle Size"]:
    df[colonne] = df[colonne].fillna(df[colonne].mode()[0])

print("\nDimensions après nettoyage :", df.shape)
print("\nValeurs manquantes après nettoyage :\n", df.isna().sum())
print("\nDoublons après nettoyage :", df.duplicated().sum())
print("\nTypes après nettoyage :\n", df.dtypes)
print("\nMinima et maxima numériques :\n", df.select_dtypes(include="number").agg(["min", "max"]))
print("\nModalités normalisées :")
for colonne in ["Coverage", "Education", "EmploymentStatus", "Vehicle Size"]:
    print(f"{colonne} :", sorted(df[colonne].dropna().unique()))

assert df.duplicated().sum() == 0
assert (df["Monthly Premium Auto"] >= 0).all()
assert (df["Months Since Last Claim"] <= 100).all()
assert (df["Number of Policies"] > 0).all()
assert df["Education"].notna().all()
assert df["Vehicle Size"].notna().all()
assert "Employeed" not in df["EmploymentStatus"].values
assert "BACHELOR" not in df["Education"].values
assert "Medium" not in df["Vehicle Size"].values

df.to_csv("customers_tp_cleaned.csv", index=False, date_format="%Y-%m-%d")
print("\nFichier exporté : customers_tp_cleaned.csv")
