// Registre des villes. Pour en ajouter une : créer ville_xxx.cpp sur le modèle de
// ville_lille.cpp, déclarer sa Ville ici, puis choisir VILLE_ACTIVE dans config.h.
#include "transit.h"

extern const Ville VILLE_LILLE;

const Ville *const VILLES[] = {
  &VILLE_LILLE,
};
const uint8_t NB_VILLES = sizeof(VILLES) / sizeof(VILLES[0]);
