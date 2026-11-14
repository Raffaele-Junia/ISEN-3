#include "ui.h"

#include <string.h>
#include <time.h>

#include "carte.h"
#include "config.h"

static const uint16_t C_FOND = 0x0000;
static const uint16_t C_AMBRE = RVB(255, 176, 0);
static const uint16_t C_TEXTE = RVB(235, 235, 235);
static const uint16_t C_GRIS = RVB(140, 140, 150);
static const uint16_t C_TRAIT = RVB(45, 45, 52);
static const uint16_t C_VERT = RVB(0, 200, 83);
static const uint16_t C_ORANGE = RVB(255, 145, 0);
static const uint16_t C_ROUGE = RVB(255, 59, 48);
static const uint16_t C_BLEU = RVB(64, 156, 255);

// Liste : 4 rangées de 54 px sous un en-tête de 46 px.
static const int RANGEES = 4;
static const int16_t Y_LISTE = 46;
static const int16_t H_RANGEE = 54;

// Détail : 9 lignes de 18 caractères en taille 2.
static const int COLONNES_DETAIL = 18;
static const int LIGNES_DETAIL = 9;
static const int16_t Y_DETAIL = 60;
static const int16_t PAS_DETAIL = 21;

static int16_t largeur(const char *s, uint8_t taille) {
  return (int16_t)(strlen(s) * 6 * taille);
}

static void texte(int16_t x, int16_t y, uint8_t taille, uint16_t couleur, const char *s) {
  gfx->setTextSize(taille);
  gfx->setTextColor(couleur);
  gfx->setCursor(x, y);
  gfx->print(s);
}

static void texte_centre(int16_t y, uint8_t taille, uint16_t couleur, const char *s) {
  texte((ECRAN_L - largeur(s, taille)) / 2, y, taille, couleur, s);
}

static uint16_t couleur_etat(EtatLigne e) {
  switch (e) {
    case ETAT_INFO: return C_BLEU;
    case ETAT_PERTURBE: return C_ORANGE;
    case ETAT_PARTIEL: return C_ORANGE;
    case ETAT_INTERROMPU: return C_ROUGE;
    default: return C_VERT;
  }
}

static const char *libelle_etat(EtatLigne e) {
  switch (e) {
    case ETAT_INFO: return "Info";
    case ETAT_PERTURBE: return "Perturbee";
    case ETAT_PARTIEL: return "Partielle";
    case ETAT_INTERROMPU: return "Interrompue";
    default: return "Normal";
  }
}

static void badge(const Ligne &l, int16_t x, int16_t y, int16_t w, int16_t h) {
  gfx->fillRoundRect(x, y, w, h, h / 5, l.couleur);
  size_t n = strlen(l.nom);
  uint8_t taille = (n <= 2 && h >= 40) ? 3 : (n <= 4 ? 2 : 1);
  texte(x + (w - largeur(l.nom, taille)) / 2 + taille / 2, y + (h - 7 * taille) / 2, taille,
        l.couleurNom, l.nom);
}

void ui_pastille_maj(bool visible) {
  gfx->fillCircle(104, 21, 4, visible ? C_AMBRE : C_FOND);
}

static void entete_liste(const char *ville, bool enCours) {
  texte(20, 14, 2, C_AMBRE, ville);
  ui_pastille_maj(enCours);

  int pct = carte_batterie_pourcent();
  gfx->drawRect(120, 15, 24, 12, C_GRIS);
  gfx->fillRect(144, 18, 2, 6, C_GRIS);
  gfx->fillRect(122, 17, (int16_t)(20 * pct / 100), 8, pct <= 15 ? C_ROUGE : C_GRIS);

  time_t t = time(nullptr);
  if (t > 1600000000) { // horloge réglée par la première lecture de l'API
    struct tm local;
    localtime_r(&t, &local);
    char heure[8];
    snprintf(heure, sizeof(heure), "%02d:%02d", local.tm_hour, local.tm_min);
    texte(ECRAN_L - 20 - largeur(heure, 2), 14, 2, C_TEXTE, heure);
  }
  gfx->drawFastHLine(12, 40, ECRAN_L - 24, C_TRAIT);
}

static void sous_titre(const Ligne &l, int64_t maintenant, char *sortie, size_t taille) {
  int hh, mm;
  if (l.etat == ETAT_NORMAL) {
    bool aujourdhui = l.message[0] && (l.publie / 86400 == maintenant / 86400);
    if (aujourdhui) {
      analyse_heure_minute(l.publie, &hh, &mm);
      snprintf(sortie, taille, "dernier incident %02dh%02d", hh, mm);
    } else {
      strlcpy(sortie, "aucune alerte", taille);
    }
  } else if (l.etat == ETAT_INFO) {
    strlcpy(sortie, "toucher pour lire", taille);
  } else if (l.jusqua > 0) {
    analyse_heure_minute(l.jusqua, &hh, &mm);
    snprintf(sortie, taille, "jusqu'a %02dh%02d environ", hh, mm);
  } else {
    analyse_heure_minute(l.publie, &hh, &mm);
    snprintf(sortie, taille, "depuis %02dh%02d", hh, mm);
  }
}

static void rangee(const Ligne &l, int64_t maintenant, int16_t y) {
  badge(l, 12, y + 5, 60, 44);
  texte(82, y + 9, 2, couleur_etat(l.etat), libelle_etat(l.etat));
  char note[28];
  sous_titre(l, maintenant, note, sizeof(note));
  texte(82, y + 33, 1, C_GRIS, note);
  gfx->drawFastHLine(82, y + H_RANGEE - 1, ECRAN_L - 94, C_TRAIT);
}

static void points_de_page(int page, int pages) {
  if (pages <= 1) return;
  int16_t x = ECRAN_L / 2 - (pages - 1) * 7;
  for (int i = 0; i < pages; i++) gfx->fillCircle(x + i * 14, 270, 3, i == page ? C_AMBRE : C_TRAIT);
}

int ui_pages_liste(const EtatReseau &reseau) {
  return reseau.nb == 0 ? 1 : (reseau.nb + RANGEES - 1) / RANGEES;
}

int ui_ligne_touchee(int16_t y, int page, const EtatReseau &reseau) {
  if (y < Y_LISTE || y >= Y_LISTE + RANGEES * H_RANGEE) return -1;
  int i = page * RANGEES + (y - Y_LISTE) / H_RANGEE;
  return i < reseau.nb ? i : -1;
}

void ui_liste(const EtatReseau &reseau, const char *ville, int page, bool enCours) {
  gfx->fillScreen(C_FOND);
  entete_liste(ville, enCours);
  for (int r = 0; r < RANGEES; r++) {
    int i = page * RANGEES + r;
    if (i >= reseau.nb) break;
    rangee(reseau.lignes[i], reseau.maj, Y_LISTE + r * H_RANGEE);
  }
  points_de_page(page, ui_pages_liste(reseau));
}

// Découpe s en lignes d'au plus « colonnes » caractères, sans couper les mots quand
// c'est possible. Dessine les lignes [premiere, premiere + nb) si dessiner est vrai.
// Renvoie le nombre total de lignes.
static int mettre_en_lignes(const char *s, int colonnes, int premiere, int nb, bool dessiner,
                            int16_t x, int16_t y, int16_t pas, uint16_t couleur) {
  char tampon[40];
  size_t longueur = strlen(s), pos = 0;
  int ligne = 0;
  while (pos < longueur) {
    while (s[pos] == ' ') pos++;
    if (pos >= longueur) break;
    size_t fin = pos + colonnes;
    if (fin >= longueur) {
      fin = longueur;
    } else if (s[fin] != ' ') {
      size_t k = fin;
      while (k > pos && s[k] != ' ') k--;
      if (k > pos) fin = k; // sinon mot plus long que la ligne : coupe franche
    }
    if (dessiner && ligne >= premiere && ligne < premiere + nb) {
      size_t n = fin - pos;
      if (n > sizeof(tampon) - 1) n = sizeof(tampon) - 1;
      memcpy(tampon, s + pos, n);
      tampon[n] = '\0';
      texte(x, y + (int16_t)(ligne - premiere) * pas, 2, couleur, tampon);
    }
    pos = fin;
    ligne++;
  }
  return ligne;
}

int ui_pages_detail(const Ligne &ligne) {
  int lignes = mettre_en_lignes(ligne.message, COLONNES_DETAIL, 0, 0, false, 0, 0, 0, 0);
  return lignes <= LIGNES_DETAIL ? 1 : (lignes + LIGNES_DETAIL - 1) / LIGNES_DETAIL;
}

void ui_detail(const Ligne &ligne, int page) {
  gfx->fillScreen(C_FOND);
  texte(18, 14, 2, C_GRIS, "<");
  badge(ligne, 38, 8, 50, 28);
  if (ligne.messageActif) {
    texte(96, 14, 2, couleur_etat(ligne.etat), libelle_etat(ligne.etat));
  } else {
    texte(96, 14, 2, C_GRIS, "Termine");
  }
  gfx->drawFastHLine(12, 44, ECRAN_L - 24, C_TRAIT);

  mettre_en_lignes(ligne.message, COLONNES_DETAIL, page * LIGNES_DETAIL, LIGNES_DETAIL, true, 12,
                   Y_DETAIL, PAS_DETAIL, ligne.messageActif ? C_TEXTE : C_GRIS);

  int pages = ui_pages_detail(ligne);
  if (pages > 1) {
    char pied[40];
    snprintf(pied, sizeof(pied), "%d/%d  toucher : suite", page + 1, pages);
    texte_centre(262, 1, C_GRIS, pied);
  }
}

void ui_message(const char *titre, const char *ligne, const char *note) {
  gfx->fillScreen(C_FOND);
  texte_centre(92, 3, C_AMBRE, titre);
  texte_centre(140, 2, C_TEXTE, ligne);
  texte_centre(172, 1, C_GRIS, note);
}
