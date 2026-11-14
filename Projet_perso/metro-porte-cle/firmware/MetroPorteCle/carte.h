// Matériel de la carte : écran, tactile, bouton et alimentation.
#pragma once
#include <Arduino.h>
#include <Adafruit_ST7789.h>

extern Adafruit_ST7789 *gfx;

// À appeler en tout premier dans setup() : sans cela, sur batterie, la carte
// s'éteint dès que l'on relâche le bouton PWR.
void carte_maintenir_alim();

void carte_demarrer();
void carte_retroeclairage(uint8_t niveau);

bool carte_bouton_appuye();

// Coupe l'alimentation. Ne revient que si la carte est branchée en USB
// (l'USB l'alimente quoi qu'il arrive) ; l'alimentation est alors rétablie.
void carte_eteindre();

int carte_batterie_mv();
int carte_batterie_pourcent();

// Vrai tant qu'un doigt est posé ; x, y dans le repère de l'écran.
bool tactile_lire(int16_t &x, int16_t &y);
