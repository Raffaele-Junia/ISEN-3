// Lecture des messages de perturbation : aucune dépendance Arduino, pour pouvoir
// tester ces règles sur un PC (voir outils/simulateur.py, qui applique les mêmes).
#pragma once
#include <stddef.h>
#include <stdint.h>

enum EtatLigne : uint8_t {
  ETAT_NORMAL = 0,
  ETAT_INFO,       // message d'information en cours (déviation, travaux...)
  ETAT_PERTURBE,   // perturbation sans interruption
  ETAT_PARTIEL,    // interrompue sur un tronçon
  ETAT_INTERROMPU  // ligne entièrement interrompue
};

struct Verdict {
  EtatLigne etat;
  int64_t jusqua; // heure « murale » de reprise estimée, 0 si le message n'en donne pas
};

// Heure « murale » : secondes depuis 1970 comptées telles qu'on les lit sur une
// horloge, sans fuseau. Permet de comparer les heures de l'API (locales) entre elles.
int64_t analyse_date_civile(int annee, int mois, int jour, int hh, int mm, int ss);

// « 2026-11-14T10:59:27.098Z » -> heure murale des chiffres écrits ; -1 si illisible.
int64_t analyse_horodatage(const char *iso);

void analyse_heure_minute(int64_t murale, int *hh, int *mm);

// UTF-8 -> ASCII (é -> e, ’ -> ', ► -> >...) : la police de l'écran n'a pas d'accents.
void analyse_vers_ascii(const char *utf8, char *sortie, size_t taille);

// Décide si un message de type « Perturbation » est encore d'actualité.
// messageAscii : sortie de analyse_vers_ascii. Les heures sont murales.
Verdict analyse_perturbation(const char *messageAscii, int64_t publie, int64_t finValidite,
                             int64_t maintenant, int32_t margeFinS, int32_t sansEstimationS);
