// Modèle commun à toutes les villes : une liste de lignes avec leur état.
// Pour ajouter une ville : écrire une fonction « charger » qui remplit un EtatReseau
// (voir ville_lille.cpp) et l'inscrire dans villes.cpp.
#pragma once
#include <stdint.h>

#include "analyse.h"

#define MESSAGE_MAX 420
#define LIGNES_MAX 14

struct Ligne {
  char code[10];        // identifiant dans l'API de la ville (« ME1 »)
  char nom[6];          // texte du badge (« M1 »)
  uint16_t couleur;     // fond du badge, RGB565
  uint16_t couleurNom;  // texte du badge
  bool epinglee;        // toujours affichée, même sans perturbation
  EtatLigne etat;
  bool messageActif;    // faux : « message » est le dernier incident, terminé
  int64_t publie;       // heure murale de publication du message
  int64_t jusqua;       // reprise estimée, 0 si inconnue
  char message[MESSAGE_MAX];
};

struct EtatReseau {
  Ligne lignes[LIGNES_MAX];
  uint8_t nb;
  int64_t maj;          // heure murale de la dernière lecture réussie
  char erreur[40];      // rempli quand charger() échoue
};

struct Ville {
  const char *nom;      // affiché en haut de l'écran
  const char *fuseau;   // chaîne TZ POSIX
  bool (*charger)(EtatReseau &reseau);
};

extern const Ville *const VILLES[];
extern const uint8_t NB_VILLES;

#define RVB(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))
