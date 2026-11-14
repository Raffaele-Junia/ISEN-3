#include "carte.h"

#include <SPI.h>
#include <Wire.h>

#include "config.h"

static Adafruit_ST7789 ecran(&SPI, BROCHE_LCD_CS, BROCHE_LCD_DC, BROCHE_LCD_RST);
Adafruit_ST7789 *gfx = &ecran;

void carte_maintenir_alim() {
  pinMode(BROCHE_ALIM_MAINTIEN, OUTPUT);
  digitalWrite(BROCHE_ALIM_MAINTIEN, HIGH);
  pinMode(BROCHE_ALIM_BOUTON, INPUT);
}

void carte_retroeclairage(uint8_t niveau) {
  analogWrite(BROCHE_LCD_RETRO, niveau);
}

static bool tactile_ecrire(uint8_t registre, uint8_t valeur) {
  Wire.beginTransmission((uint8_t)ADRESSE_TACTILE);
  Wire.write(registre);
  Wire.write(valeur);
  return Wire.endTransmission() == 0;
}

void carte_demarrer() {
  pinMode(BROCHE_BUZZER, OUTPUT);
  digitalWrite(BROCHE_BUZZER, LOW);

  pinMode(BROCHE_LCD_RETRO, OUTPUT);
  digitalWrite(BROCHE_LCD_RETRO, LOW); // pas d'image parasite avant le premier dessin
  SPI.begin(BROCHE_LCD_SCK, -1, BROCHE_LCD_MOSI, BROCHE_LCD_CS);
  gfx->init(ECRAN_L, ECRAN_H); // règle aussi le décalage de la dalle 240x280 dans le ST7789
  gfx->setSPISpeed(40000000);
  gfx->setRotation(ECRAN_ROTATION);
  gfx->fillScreen(0x0000);
  gfx->setTextWrap(false);

  pinMode(BROCHE_TACTILE_INT, INPUT_PULLUP);
  pinMode(BROCHE_TACTILE_RST, OUTPUT);
  digitalWrite(BROCHE_TACTILE_RST, LOW);
  delay(10);
  digitalWrite(BROCHE_TACTILE_RST, HIGH);
  delay(60);
  Wire.begin(BROCHE_I2C_SDA, BROCHE_I2C_SCL, 400000);
  // Désactive la mise en sommeil automatique du CST816 (registre 0xFE). Sans effet
  // sur certaines variantes : tactile_lire() tolère de toute façon un contrôleur endormi.
  tactile_ecrire(0xFE, 0x01);

  analogReadResolution(12);
}

bool carte_bouton_appuye() {
  return digitalRead(BROCHE_ALIM_BOUTON) == LOW;
}

void carte_eteindre() {
  // Tant que PWR est enfoncé, le bouton alimente lui-même la carte.
  uint32_t debut = millis();
  while (carte_bouton_appuye() && millis() - debut < 5000) delay(10);
  carte_retroeclairage(0);
  digitalWrite(BROCHE_ALIM_MAINTIEN, LOW);
  delay(800);
  // Toujours en vie : alimentation par USB.
  digitalWrite(BROCHE_ALIM_MAINTIEN, HIGH);
}

int carte_batterie_mv() {
  uint32_t somme = 0;
  for (int i = 0; i < 8; i++) somme += analogReadMilliVolts(BROCHE_BATTERIE);
  return (int)(somme / 8) * 3;
}

int carte_batterie_pourcent() {
  // Courbe de décharge approximative d'un accu LiPo au repos.
  static const int mv[] = { 3300, 3500, 3700, 3800, 3950, 4150 };
  static const int pct[] = { 0, 5, 25, 50, 75, 100 };
  int v = carte_batterie_mv();
  if (v <= mv[0]) return 0;
  for (int i = 1; i < 6; i++) {
    if (v <= mv[i]) return pct[i - 1] + (v - mv[i - 1]) * (pct[i] - pct[i - 1]) / (mv[i] - mv[i - 1]);
  }
  return 100;
}

bool tactile_lire(int16_t &x, int16_t &y) {
  // Registres 0x02..0x06 : nombre de doigts, X (poids fort, faible), Y (fort, faible).
  Wire.beginTransmission((uint8_t)ADRESSE_TACTILE);
  Wire.write((uint8_t)0x02);
  if (Wire.endTransmission(false) != 0) return false; // contrôleur endormi : pas de doigt
  if (Wire.requestFrom((int)ADRESSE_TACTILE, 5) != 5) return false;
  uint8_t d[5];
  for (int i = 0; i < 5; i++) d[i] = (uint8_t)Wire.read();
  if ((d[0] & 0x0F) == 0) return false;

  int16_t bx = (int16_t)(((d[1] & 0x0F) << 8) | d[2]);
  int16_t by = (int16_t)(((d[3] & 0x0F) << 8) | d[4]);
  if (bx >= ECRAN_L || by >= ECRAN_H) return false;
#if ECRAN_ROTATION == 2
  bx = ECRAN_L - 1 - bx;
  by = ECRAN_H - 1 - by;
#endif
  x = bx;
  y = by;
  return true;
}
