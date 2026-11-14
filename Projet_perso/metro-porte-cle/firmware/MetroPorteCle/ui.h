// Dessin des écrans. Police bitmap intégrée (6x8 px, agrandie) : pas d'accents.
#pragma once
#include <stdint.h>

#include "transit.h"

enum Geste : uint8_t { GESTE_AUCUN, GESTE_TOUCHE, GESTE_HAUT, GESTE_BAS, GESTE_GAUCHE, GESTE_DROITE };

// Écran d'attente ou d'erreur : titre, une ligne (18 caractères), une note (36 caractères).
void ui_message(const char *titre, const char *ligne, const char *note);

// Liste des lignes. enCours : pastille « mise à jour en cours » dans l'en-tête.
void ui_liste(const EtatReseau &reseau, const char *ville, int page, bool enCours);
void ui_pastille_maj(bool visible);
int ui_pages_liste(const EtatReseau &reseau);
// Indice de la ligne affichée à la hauteur y, ou -1.
int ui_ligne_touchee(int16_t y, int page, const EtatReseau &reseau);

// Message complet d'une ligne, paginé.
void ui_detail(const Ligne &ligne, int page);
int ui_pages_detail(const Ligne &ligne);
