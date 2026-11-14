// Copie ce fichier sous le nom « secrets.h » (ignoré par git) et renseigne tes réseaux.
// Le porte-clé se connecte au premier réseau de la liste qu'il capte.
// Dehors, il lui faut le partage de connexion du téléphone : ajoute-le ici.
#pragma once
#include "config.h"

static const AccesWifi RESEAUX_WIFI[] = {
  { "NomDeLaBox", "mot-de-passe-de-la-box" },
  { "Partage de connexion du telephone", "mot-de-passe-du-partage" },
};
