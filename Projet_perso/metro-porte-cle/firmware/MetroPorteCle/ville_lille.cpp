// Lille : perturbations du réseau ilévia, publiées par la Métropole Européenne de Lille.
// Jeu de données « ilévia - Perturbations sur le réseau ilévia », mis à jour chaque minute :
// https://www.data.gouv.fr/datasets/ilevia-perturbations-sur-le-reseau-bus
//
// Chaque enregistrement vise une ligne (« ILEVIA:LineRef::ME1:LOC ») et porte un message
// rédigé à la main. Il n'y a pas d'enregistrement « reprise » : un message reste publié
// 24 h, même quand le métro roule de nouveau. L'état est donc déduit du texte du dernier
// message de chaque ligne (voir analyse.cpp).
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <sys/time.h>
#include <time.h>

#include "analyse.h"
#include "config.h"
#include "transit.h"

static const char URL_PERTURBATIONS[] =
  "https://data.lillemetropole.fr/geoserver/ogc/features/v1/collections/"
  "dsp_ilevia%3Aperturbations/items?f=application%2Fjson&limit=200";

struct LigneConnue {
  const char *code;
  const char *nom;
  uint16_t couleur;
  uint16_t couleurNom;
};

// Lignes toujours affichées, dans cet ordre. Le tramway est codé « 71 » par ilévia.
static const LigneConnue EPINGLEES[] = {
  { "ME1", "M1", RVB(255, 205, 0), RVB(0, 0, 0) },
  { "ME2", "M2", RVB(226, 0, 26), RVB(255, 255, 255) },
  { "71", "TRAM", RVB(0, 150, 170), RVB(255, 255, 255) },
};
static const uint8_t NB_EPINGLEES = sizeof(EPINGLEES) / sizeof(EPINGLEES[0]);

// Meilleur enregistrement de chaque type pour une ligne, repéré par son rang dans le JSON.
struct Candidat {
  int perturbation;
  int64_t perturbationPubliee;
  int information;
  int64_t informationPubliee;
};

static bool extraire_code(const char *cible, char *code, size_t taille) {
  const char *debut = strstr(cible, "LineRef::");
  if (!debut) return false; // un arrêt, pas une ligne
  debut += 9;
  size_t n = 0;
  while (debut[n] && debut[n] != ':' && n + 1 < taille) {
    code[n] = debut[n];
    n++;
  }
  code[n] = '\0';
  return n > 0;
}

static int chercher_ligne(EtatReseau &reseau, const char *code) {
  for (uint8_t i = 0; i < reseau.nb; i++) {
    if (strcmp(reseau.lignes[i].code, code) == 0) return i;
  }
  return -1;
}

static int ajouter_ligne(EtatReseau &reseau, const char *code, const char *nom, uint16_t couleur,
                         uint16_t couleurNom, bool epinglee) {
  if (reseau.nb >= LIGNES_MAX) return -1;
  Ligne &l = reseau.lignes[reseau.nb];
  memset(&l, 0, sizeof(l));
  strlcpy(l.code, code, sizeof(l.code));
  strlcpy(l.nom, nom, sizeof(l.nom));
  l.couleur = couleur;
  l.couleurNom = couleurNom;
  l.epinglee = epinglee;
  l.etat = ETAT_NORMAL;
  return reseau.nb++;
}

// Règle l'horloge de l'ESP32 sur l'heure du serveur (champ « timeStamp », en vrai UTC)
// et renvoie l'heure murale locale correspondante. Évite une requête NTP à chaque allumage.
static int64_t regler_horloge(const char *horodatageUtc) {
  int64_t utc = analyse_horodatage(horodatageUtc);
  if (utc < 0) return -1;
  struct timeval tv = { (time_t)utc, 0 };
  settimeofday(&tv, nullptr);
  time_t t = (time_t)utc;
  struct tm local;
  localtime_r(&t, &local);
  return analyse_date_civile(local.tm_year + 1900, local.tm_mon + 1, local.tm_mday, local.tm_hour,
                             local.tm_min, local.tm_sec);
}

static void trier(EtatReseau &reseau) {
  // Les épinglées gardent leur place en tête ; les autres par gravité décroissante.
  for (uint8_t i = NB_EPINGLEES + 1; i < reseau.nb; i++) {
    Ligne cle = reseau.lignes[i];
    int j = i - 1;
    while (j >= NB_EPINGLEES &&
           (reseau.lignes[j].etat < cle.etat ||
            (reseau.lignes[j].etat == cle.etat && strcmp(reseau.lignes[j].code, cle.code) > 0))) {
      reseau.lignes[j + 1] = reseau.lignes[j];
      j--;
    }
    reseau.lignes[j + 1] = cle;
  }
}

static bool lille_charger(EtatReseau &reseau) {
  reseau.erreur[0] = '\0';

  WiFiClientSecure client;
  // Données publiques en lecture seule : on ne vérifie pas le certificat, pour ne pas
  // tomber en panne le jour où l'autorité de certification du portail change.
  client.setInsecure();

  HTTPClient http;
  http.useHTTP10(true); // réponse non découpée (« chunked »), lisible en flux par ArduinoJson
  http.setTimeout(HTTP_DELAI_MS);
  if (!http.begin(client, URL_PERTURBATIONS)) {
    strlcpy(reseau.erreur, "URL refusee", sizeof(reseau.erreur));
    return false;
  }
  http.addHeader("Accept", "application/json");
  int statut = http.GET();
  if (statut != HTTP_CODE_OK) {
    snprintf(reseau.erreur, sizeof(reseau.erreur), "Serveur : %d", statut);
    http.end();
    return false;
  }

  // On ne garde en mémoire que les champs utiles (la réponse complète pèse 25 à 100 ko).
  JsonDocument filtre;
  filtre["timeStamp"] = true;
  JsonObject champs = filtre["features"][0]["properties"].to<JsonObject>();
  champs["cible"] = true;
  champs["type_perturbation"] = true;
  champs["heure_fin_prevue"] = true;
  champs["date_modification"] = true;
  champs["message"] = true;

  JsonDocument doc;
  DeserializationError erreur =
    deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filtre));
  http.end();
  if (erreur) {
    snprintf(reseau.erreur, sizeof(reseau.erreur), "JSON : %s", erreur.c_str());
    return false;
  }

  int64_t maintenant = regler_horloge(doc["timeStamp"] | "");
  if (maintenant < 0) {
    strlcpy(reseau.erreur, "Heure serveur absente", sizeof(reseau.erreur));
    return false;
  }
#if !API_HEURES_LOCALES
  // Si un jour l'API passe en vrai UTC : tout comparer en UTC.
  maintenant = analyse_horodatage(doc["timeStamp"] | "");
#endif

  reseau.nb = 0;
  Candidat candidats[LIGNES_MAX];
  for (uint8_t i = 0; i < LIGNES_MAX; i++) candidats[i] = { -1, 0, -1, 0 };
  for (uint8_t i = 0; i < NB_EPINGLEES; i++) {
    ajouter_ligne(reseau, EPINGLEES[i].code, EPINGLEES[i].nom, EPINGLEES[i].couleur,
                  EPINGLEES[i].couleurNom, true);
  }

  // Passe 1 : pour chaque ligne, le message le plus récent de chaque type.
  JsonArray enregistrements = doc["features"].as<JsonArray>();
  int rang = 0;
  for (JsonObject enregistrement : enregistrements) {
    JsonObject p = enregistrement["properties"];
    char code[10];
    int64_t publie = analyse_horodatage(p["date_modification"] | "");
    if (publie >= 0 && extraire_code(p["cible"] | "", code, sizeof(code))) {
      int i = chercher_ligne(reseau, code);
      if (i < 0) i = ajouter_ligne(reseau, code, code, RVB(70, 70, 78), RVB(255, 255, 255), false);
      if (i >= 0) {
        bool perturbation = strcmp(p["type_perturbation"] | "", "Perturbation") == 0;
        Candidat &c = candidats[i];
        if (perturbation && (c.perturbation < 0 || publie > c.perturbationPubliee)) {
          c.perturbation = rang;
          c.perturbationPubliee = publie;
        } else if (!perturbation && (c.information < 0 || publie > c.informationPubliee)) {
          c.information = rang;
          c.informationPubliee = publie;
        }
      }
    }
    rang++;
  }

  // Passe 2 : état de chaque ligne.
  for (uint8_t i = 0; i < reseau.nb; i++) {
    Ligne &l = reseau.lignes[i];
    Candidat &c = candidats[i];
    if (c.perturbation >= 0) {
      JsonObject p = enregistrements[c.perturbation]["properties"];
      analyse_vers_ascii(p["message"] | "", l.message, sizeof(l.message));
      Verdict v = analyse_perturbation(l.message, c.perturbationPubliee,
                                       analyse_horodatage(p["heure_fin_prevue"] | ""), maintenant,
                                       MARGE_FIN_S, SANS_ESTIMATION_S);
      l.etat = v.etat;
      l.jusqua = v.jusqua;
      l.publie = c.perturbationPubliee;
      l.messageActif = (v.etat != ETAT_NORMAL);
    }
    if (l.etat == ETAT_NORMAL && c.information >= 0) {
      JsonObject p = enregistrements[c.information]["properties"];
      int64_t fin = analyse_horodatage(p["heure_fin_prevue"] | "");
      if (fin < 0 || maintenant <= fin) {
        analyse_vers_ascii(p["message"] | "", l.message, sizeof(l.message));
        l.etat = ETAT_INFO;
        l.jusqua = 0;
        l.publie = c.informationPubliee;
        l.messageActif = true;
      }
    }
  }

  // Les lignes de bus sans rien d'actif n'encombrent pas la liste.
  uint8_t garde = 0;
  for (uint8_t i = 0; i < reseau.nb; i++) {
    if (reseau.lignes[i].epinglee || reseau.lignes[i].etat != ETAT_NORMAL) {
      if (garde != i) reseau.lignes[garde] = reseau.lignes[i];
      garde++;
    }
  }
  reseau.nb = garde;
  trier(reseau);
  reseau.maj = maintenant;
  return true;
}

extern const Ville VILLE_LILLE = { "LILLE", "CET-1CEST,M3.5.0,M10.5.0/3", lille_charger };
