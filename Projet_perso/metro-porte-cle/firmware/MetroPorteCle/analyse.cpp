#include "analyse.h"

#include <ctype.h>
#include <string.h>

// Algorithme de Howard Hinnant (days_from_civil).
static int64_t jours_depuis_1970(int32_t a, int32_t m, int32_t j) {
  a -= (m <= 2) ? 1 : 0;
  const int32_t ere = (a >= 0 ? a : a - 399) / 400;
  const uint32_t anneeEre = (uint32_t)(a - ere * 400);
  const uint32_t jourAnnee = (uint32_t)((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + j - 1);
  const uint32_t jourEre = anneeEre * 365UL + anneeEre / 4 - anneeEre / 100 + jourAnnee;
  return (int64_t)ere * 146097 + (int64_t)jourEre - 719468;
}

int64_t analyse_date_civile(int annee, int mois, int jour, int hh, int mm, int ss) {
  return jours_depuis_1970(annee, mois, jour) * 86400 + (int64_t)hh * 3600 + (int64_t)mm * 60 + ss;
}

static bool lire_nombre(const char *s, int nb, int *valeur) {
  int v = 0;
  for (int i = 0; i < nb; i++) {
    if (!isdigit((unsigned char)s[i])) return false;
    v = v * 10 + (s[i] - '0');
  }
  *valeur = v;
  return true;
}

int64_t analyse_horodatage(const char *iso) {
  if (iso == NULL || strlen(iso) < 19) return -1;
  int a, m, j, hh, mm, ss;
  if (!lire_nombre(iso, 4, &a) || iso[4] != '-' || !lire_nombre(iso + 5, 2, &m) || iso[7] != '-' ||
      !lire_nombre(iso + 8, 2, &j) || !lire_nombre(iso + 11, 2, &hh) || iso[13] != ':' ||
      !lire_nombre(iso + 14, 2, &mm) || iso[16] != ':' || !lire_nombre(iso + 17, 2, &ss)) {
    return -1;
  }
  return analyse_date_civile(a, m, j, hh, mm, ss);
}

void analyse_heure_minute(int64_t murale, int *hh, int *mm) {
  int64_t dansLeJour = murale % 86400;
  if (dansLeJour < 0) dansLeJour += 86400;
  *hh = (int)(dansLeJour / 3600);
  *mm = (int)((dansLeJour % 3600) / 60);
}

static const char *remplacement(uint32_t c) {
  switch (c) {
    case 0xE0: case 0xE2: case 0xE4: return "a";
    case 0xC0: case 0xC2: case 0xC4: return "A";
    case 0xE7: return "c";
    case 0xC7: return "C";
    case 0xE8: case 0xE9: case 0xEA: case 0xEB: return "e";
    case 0xC8: case 0xC9: case 0xCA: case 0xCB: return "E";
    case 0xEE: case 0xEF: return "i";
    case 0xCE: case 0xCF: return "I";
    case 0xF4: case 0xF6: return "o";
    case 0xD4: case 0xD6: return "O";
    case 0xF9: case 0xFB: case 0xFC: return "u";
    case 0xD9: case 0xDB: case 0xDC: return "U";
    case 0x153: return "oe";
    case 0x152: return "OE";
    case 0x2018: case 0x2019: case 0x2032: return "'";
    case 0x201C: case 0x201D: case 0xAB: case 0xBB: return "\"";
    case 0x2010: case 0x2011: case 0x2013: case 0x2014: return "-";
    case 0x2026: return "...";
    case 0x25BA: case 0x25B6: case 0x2192: case 0x2022: return ">";
    case 0xA0: case 0x2009: case 0x202F: return " ";
    case 0xB0: return "o";
    case 0x20AC: return "EUR";
    case 0x200B: case 0x200D: case 0xFEFF: case 0xFE0F: return "";
    default: return "?";
  }
}

void analyse_vers_ascii(const char *utf8, char *sortie, size_t taille) {
  if (taille == 0) return;
  size_t n = 0;
  bool espacePrecedent = true; // supprime aussi les espaces de tête
  const unsigned char *p = (const unsigned char *)(utf8 ? utf8 : "");
  while (*p && n + 1 < taille) {
    uint32_t c = *p++;
    const char *texte = NULL;
    char seul[2] = { 0, 0 };
    if (c < 0x80) {
      seul[0] = (c < 0x20) ? ' ' : (char)c; // retours à la ligne et tabulations -> espace
      texte = seul;
    } else {
      int suite = (c >= 0xF0) ? 3 : (c >= 0xE0) ? 2 : (c >= 0xC0) ? 1 : 0;
      c &= (suite == 3) ? 0x07 : (suite == 2) ? 0x0F : 0x1F;
      while (suite-- > 0 && (*p & 0xC0) == 0x80) c = (c << 6) | (*p++ & 0x3F);
      texte = remplacement(c);
    }
    for (; *texte && n + 1 < taille; texte++) {
      bool espace = (*texte == ' ');
      if (espace && espacePrecedent) continue;
      sortie[n++] = *texte;
      espacePrecedent = espace;
    }
  }
  while (n > 0 && sortie[n - 1] == ' ') n--;
  sortie[n] = '\0';
}

// strstr insensible à la casse ; le motif doit être en minuscules.
static const char *trouve(const char *texte, const char *motif) {
  size_t lm = strlen(motif);
  for (; *texte; texte++) {
    size_t i = 0;
    while (i < lm && texte[i] && tolower((unsigned char)texte[i]) == motif[i]) i++;
    if (i == lm) return texte;
  }
  return NULL;
}

// Cherche « 11h15 », « 08h 05 », « 18 h » dans les caractères qui suivent p.
static bool heure_apres(const char *p, int *hh, int *mm) {
  for (int i = 0; i < 48 && p[i]; i++) {
    if (!isdigit((unsigned char)p[i])) continue;
    int j = i, h = 0, chiffres = 0;
    while (isdigit((unsigned char)p[j])) {
      if (chiffres < 4) h = h * 10 + (p[j] - '0');
      j++;
      chiffres++;
    }
    if (chiffres <= 2) {
      int k = j;
      while (p[k] == ' ') k++;
      if (p[k] == 'h' || p[k] == 'H' || p[k] == ':') {
        k++;
        while (p[k] == ' ') k++;
        int m = 0, chiffresMin = 0;
        while (isdigit((unsigned char)p[k]) && chiffresMin < 2) {
          m = m * 10 + (p[k] - '0');
          k++;
          chiffresMin++;
        }
        if (h < 24 && m < 60) {
          *hh = h;
          *mm = m;
          return true;
        }
      }
    }
    i = j - 1;
  }
  return false;
}

Verdict analyse_perturbation(const char *msg, int64_t publie, int64_t finValidite,
                             int64_t maintenant, int32_t margeFinS, int32_t sansEstimationS) {
  Verdict v = { ETAT_NORMAL, 0 };

  // Message de reprise : la ligne roule de nouveau. Formes conjuguées seulement, pour
  // ne pas confondre avec « reprise estimée vers 11h15 » dans une annonce d'interruption.
  if (trouve(msg, "a repris") || trouve(msg, "ont repris") || trouve(msg, "reprend") ||
      trouve(msg, "retabli") || trouve(msg, "trafic normal") || trouve(msg, "circule a nouveau") ||
      trouve(msg, "circulent a nouveau") || trouve(msg, "fin de perturbation")) {
    return v;
  }
  // L'API retire rarement les messages : passé leur validité (24 h), on n'y croit plus.
  if (finValidite > 0 && maintenant > finValidite) return v;

  bool actif;
  const char *jusqu = trouve(msg, "jusqu");
  int hh, mm;
  if (jusqu && heure_apres(jusqu, &hh, &mm)) {
    int64_t debutJour = publie - (publie % 86400);
    v.jusqua = debutJour + (int64_t)hh * 3600 + (int64_t)mm * 60;
    if (v.jusqua < publie - 300) v.jusqua += 86400; // « jusque 00h30 » publié à 23h50
    actif = maintenant <= v.jusqua + margeFinS;
  } else if (jusqu) {
    actif = true; // « jusqu'à nouvel ordre », « jusqu'au 15/11 » : valable tant que publié
  } else {
    actif = (maintenant - publie) <= sansEstimationS;
  }
  if (!actif) {
    v.jusqua = 0;
    return v;
  }

  if (trouve(msg, "interrompu") || trouve(msg, "ne circule") || trouve(msg, "a l'arret")) {
    bool troncon = trouve(msg, "entre les stations") || trouve(msg, "entre la station") ||
                   trouve(msg, "entre les arrets");
    v.etat = troncon ? ETAT_PARTIEL : ETAT_INTERROMPU;
  } else {
    v.etat = ETAT_PERTURBE;
  }
  return v;
}
