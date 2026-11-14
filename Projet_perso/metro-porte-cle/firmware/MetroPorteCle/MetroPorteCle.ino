// Porte-clé « état du métro » — Waveshare ESP32-S3-Touch-LCD-1.69.
//
// Un appui sur PWR allume le porte-clé : il rejoint le WiFi, lit les perturbations
// en cours et affiche l'état de chaque ligne. Toucher une ligne ouvre son message.
// Sans geste pendant EXTINCTION_AUTO_S, il se coupe (consommation nulle).
// Branché en USB il reste allumé et se met à jour chaque minute.
//
// Gestes : toucher une ligne = détail ; glisser haut/bas = page suivante/précédente ;
// glisser vers le bas en haut de liste = mise à jour ; dans le détail, « < » ou
// glisser à droite = retour. Bouton PWR : appui court = mise à jour, long = extinction.
#include <WiFi.h>
#include <WiFiMulti.h>
#include <time.h>

#include "carte.h"
#include "config.h"
#include "transit.h"
#include "ui.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copie secrets.example.h sous le nom secrets.h et renseigne ton WiFi."
#endif

enum Vue : uint8_t { VUE_LISTE, VUE_DETAIL, VUE_ERREUR };

static WiFiMulti wifi;
static EtatReseau reseau;
static const Ville *ville = nullptr;

static Vue vue = VUE_ERREUR;
static int pageListe = 0;
static int pageDetail = 0;
static char codeDetail[10] = "";
static uint32_t dernierGeste = 0;
static uint32_t derniereMaj = 0;
static bool attenue = false;

static int indice_detail() {
  for (uint8_t i = 0; i < reseau.nb; i++) {
    if (strcmp(reseau.lignes[i].code, codeDetail) == 0) return i;
  }
  return -1;
}

static void dessiner() {
  if (vue == VUE_DETAIL) {
    int i = indice_detail();
    if (i >= 0 && reseau.lignes[i].message[0]) {
      int pages = ui_pages_detail(reseau.lignes[i]);
      if (pageDetail >= pages) pageDetail = pages - 1;
      ui_detail(reseau.lignes[i], pageDetail);
      return;
    }
    vue = VUE_LISTE; // la ligne a disparu de la liste depuis la dernière mise à jour
  }
  int pages = ui_pages_liste(reseau);
  if (pageListe >= pages) pageListe = pages - 1;
  ui_liste(reseau, ville->nom, pageListe, false);
}

static bool connecter() {
  if (WiFi.status() == WL_CONNECTED) return true;
  uint32_t debut = millis();
  while (millis() - debut < WIFI_DELAI_MS) {
    if (wifi.run(4000) == WL_CONNECTED) return true;
    delay(200);
  }
  return false;
}

static void actualiser() {
  if (vue == VUE_LISTE) ui_pastille_maj(true);
  bool enLigne = connecter();
  bool ok = enLigne && ville->charger(reseau);
  derniereMaj = millis();
  if (!ok) {
    vue = VUE_ERREUR;
    if (!enLigne) {
      ui_message("Pas de WiFi", "Aucun reseau", "Partage de connexion ? Touche l'ecran");
    } else {
      Serial.printf("Echec de lecture : %s\n", reseau.erreur);
      ui_message("Erreur", "Lecture impossible", reseau.erreur);
    }
    return;
  }
  if (vue == VUE_ERREUR) vue = VUE_LISTE;
  dessiner();
}

static void reveiller() {
  dernierGeste = millis();
  if (attenue) {
    attenue = false;
    carte_retroeclairage(LUMINOSITE);
  }
}

// Extinction demandée par un appui long. Sur USB la carte ne peut pas se couper :
// on éteint l'écran, et un appui ou un toucher la redémarre.
static void eteindre() {
  ui_message("", "Extinction", "");
  carte_eteindre();
  carte_retroeclairage(0);
  int16_t x, y;
  while (!carte_bouton_appuye() && !tactile_lire(x, y)) delay(30);
  ESP.restart();
}

static void gerer_bouton() {
  static bool arme = false; // ignore l'appui qui a allumé la carte
  static bool appuye = false;
  static uint32_t debut = 0;
  bool b = carte_bouton_appuye();
  if (!arme) {
    arme = !b;
    return;
  }
  if (b && !appuye) {
    appuye = true;
    debut = millis();
  } else if (b && millis() - debut >= APPUI_LONG_MS) {
    eteindre();
  } else if (!b && appuye) {
    appuye = false;
    if (millis() - debut >= 30) {
      reveiller();
      actualiser();
    }
  }
}

// Suit le doigt et rend un geste au moment où il se lève ; x, y = point de départ.
static Geste lire_geste(int16_t &x, int16_t &y) {
  static bool pose = false;
  static int16_t x0, y0, x1, y1;
  static uint32_t dernierContact = 0;
  int16_t tx, ty;
  if (tactile_lire(tx, ty)) {
    if (!pose) {
      pose = true;
      x0 = tx;
      y0 = ty;
    }
    x1 = tx;
    y1 = ty;
    dernierContact = millis();
    return GESTE_AUCUN;
  }
  if (!pose || millis() - dernierContact < 40) return GESTE_AUCUN;
  pose = false;
  x = x0;
  y = y0;
  int dx = x1 - x0, dy = y1 - y0;
  if (abs(dy) >= 36 && abs(dy) > abs(dx)) return dy < 0 ? GESTE_HAUT : GESTE_BAS;
  if (abs(dx) >= 36) return dx < 0 ? GESTE_GAUCHE : GESTE_DROITE;
  return GESTE_TOUCHE;
}

static void traiter_geste(Geste geste, int16_t x, int16_t y) {
  (void)x;
  if (vue == VUE_ERREUR) {
    ui_message(ville->nom, "Nouvel essai", "");
    actualiser();
    return;
  }
  if (vue == VUE_LISTE) {
    if (geste == GESTE_HAUT && pageListe + 1 < ui_pages_liste(reseau)) {
      pageListe++;
      dessiner();
    } else if (geste == GESTE_BAS && pageListe > 0) {
      pageListe--;
      dessiner();
    } else if (geste == GESTE_BAS) {
      actualiser();
    } else if (geste == GESTE_TOUCHE) {
      int i = ui_ligne_touchee(y, pageListe, reseau);
      if (i >= 0 && reseau.lignes[i].message[0]) {
        strlcpy(codeDetail, reseau.lignes[i].code, sizeof(codeDetail));
        pageDetail = 0;
        vue = VUE_DETAIL;
        dessiner();
      }
    }
    return;
  }
  // VUE_DETAIL
  int i = indice_detail();
  int pages = (i >= 0) ? ui_pages_detail(reseau.lignes[i]) : 1;
  if (geste == GESTE_DROITE || (geste == GESTE_TOUCHE && y < 48)) {
    vue = VUE_LISTE;
  } else if (geste == GESTE_BAS) {
    if (pageDetail > 0) pageDetail--;
  } else if (geste == GESTE_HAUT) {
    if (pageDetail + 1 < pages) pageDetail++;
  } else if (geste == GESTE_TOUCHE) {
    pageDetail = (pageDetail + 1 < pages) ? pageDetail + 1 : 0;
  }
  dessiner();
}

void setup() {
  carte_maintenir_alim(); // en premier : garde la carte allumée une fois PWR relâché
  Serial.begin(115200);

  ville = VILLES[VILLE_ACTIVE < NB_VILLES ? VILLE_ACTIVE : 0];
  setenv("TZ", ville->fuseau, 1);
  tzset();

  carte_demarrer();
  ui_message(ville->nom, "Connexion WiFi", "");
  carte_retroeclairage(LUMINOSITE);

  WiFi.mode(WIFI_STA);
  for (const AccesWifi &acces : RESEAUX_WIFI) wifi.addAP(acces.ssid, acces.motDePasse);

  actualiser();
  dernierGeste = millis();
}

void loop() {
  int16_t x = 0, y = 0;
  Geste geste = lire_geste(x, y);
  if (geste != GESTE_AUCUN) {
    reveiller();
    traiter_geste(geste, x, y);
  }
  gerer_bouton();

  if (millis() - derniereMaj >= RAFRAICHISSEMENT_S * 1000UL) actualiser();

  if (millis() - dernierGeste >= EXTINCTION_AUTO_S * 1000UL) {
    // Sur batterie, l'alimentation se coupe ici. Sur USB on continue, écran atténué,
    // et on réessaie plus tard (au cas où le câble aurait été débranché entre-temps).
    carte_retroeclairage(LUMINOSITE_VEILLE);
    attenue = true;
    carte_eteindre();
    dernierGeste = millis();
  }
  delay(15);
}
