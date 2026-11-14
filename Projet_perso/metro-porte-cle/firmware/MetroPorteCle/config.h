// Réglages du porte-clé : brochage de la carte et comportement.
// Carte : Waveshare ESP32-S3-Touch-LCD-1.69 (écran 240x280 ST7789V2, tactile CST816).
#pragma once
#include <stdint.h>

// ---------------------------------------------------------------- Carte
// Waveshare a sorti deux révisions qui diffèrent sur trois broches.
// Symptôme d'un mauvais choix : sur batterie, la carte s'éteint dès qu'on
// relâche le bouton PWR. Dans ce cas, passer cette valeur à 1.
#define CARTE_ANCIENNE_REVISION 0

#define BROCHE_LCD_DC 4
#define BROCHE_LCD_CS 5
#define BROCHE_LCD_SCK 6
#define BROCHE_LCD_MOSI 7
#define BROCHE_LCD_RST 8
#define BROCHE_LCD_RETRO 15

#define BROCHE_I2C_SDA 11
#define BROCHE_I2C_SCL 10
#define BROCHE_TACTILE_RST 13
#define BROCHE_TACTILE_INT 14
#define ADRESSE_TACTILE 0x15

#define BROCHE_BATTERIE 1 // pont diviseur 200k/100k : tension lue x 3

#if CARTE_ANCIENNE_REVISION
#define BROCHE_ALIM_MAINTIEN 35 // SYS_EN : à garder à l'état haut pour rester allumé
#define BROCHE_ALIM_BOUTON 36   // SYS_OUT : état bas quand PWR est appuyé
#define BROCHE_BUZZER 33
#else
#define BROCHE_ALIM_MAINTIEN 41
#define BROCHE_ALIM_BOUTON 40
#define BROCHE_BUZZER 42
#endif

#define ECRAN_L 240
#define ECRAN_H 280
// 0 = haut de l'écran côté antenne (anneau du boîtier). Mettre 2 si l'image est à l'envers.
#define ECRAN_ROTATION 0

// --------------------------------------------------------- Comportement
#define VILLE_ACTIVE 0          // indice dans VILLES[] (villes.cpp)
#define RAFRAICHISSEMENT_S 60   // la source est mise à jour chaque minute
#define EXTINCTION_AUTO_S 45    // sans toucher l'écran, sur batterie
#define WIFI_DELAI_MS 15000
#define HTTP_DELAI_MS 12000
#define LUMINOSITE 220          // 0-255
#define LUMINOSITE_VEILLE 40    // sur USB, après EXTINCTION_AUTO_S sans geste
#define APPUI_LONG_MS 1200

// ------------------------------------------------- Lecture des messages
// Une interruption annoncée « jusque 11h15 » reste affichée ce délai après l'heure dite.
#define MARGE_FIN_S (10 * 60)
// Message de perturbation sans aucune heure de fin : durée pendant laquelle on le croit.
#define SANS_ESTIMATION_S (2 * 3600)
// Les horodatages de l'API Ilévia portent un « Z » mais sont en heure de Paris
// (constaté le 14/11/2026 : « interrompue jusque 11h15 » publié à « 10:59Z »).
#define API_HEURES_LOCALES 1

struct AccesWifi {
  const char *ssid;
  const char *motDePasse;
};
