// Boîtier porte-clé pour la carte Waveshare ESP32-S3-Touch-LCD-1.69 + accu LiPo.
//
// Deux pièces, sans vis ni supports :
//   - la coque : façade avec fenêtre, flancs, anneau porte-clé, lame-bouton PWR ;
//   - le couvercle : se clipse au dos, ses 4 plots plaquent la carte contre la façade.
//
// Repère = vue de dos (circuit vers soi, comme sur la photo Waveshare) :
//   X vers la droite (USB-C à droite, boutons à gauche), Y vers le haut (antenne, anneau),
//   Z = 0 sur la face avant, Z croissant vers le dos. La coque s'imprime telle quelle,
//   façade sur le plateau.

/* [Affichage] */
// Pièce à afficher ou exporter
piece = "assemblage"; // [assemblage, coupe, impression, coque, couvercle]
// Montrer la carte et l'accu en transparence (assemblage et coupe)
fantome = true;

/* [Carte : cotes du plan Waveshare] */
verre_l = 33.13;   // largeur du verre (X)
verre_h = 41.13;   // hauteur du verre (Y)
pcb_l = 29.83;     // largeur du circuit
pcb_h = 37.12;     // hauteur du circuit
zone_l = 27.97;    // zone affichée, largeur
zone_h = 32.63;    // zone affichée, hauteur
// Décalage de la zone affichée vers le haut (bord large côté nappe, en bas) — relevé sur le plan
zone_dy = 1.25;

/* [Carte : épaisseurs A MESURER au pied à coulisse] */
// Face avant du verre -> face avant du circuit
ep_ecran = 3.2;
// Épaisseur du circuit imprimé
ep_pcb = 1.2;
// Hauteur du plus haut composant au dos (prise USB-C, connecteur batterie)
ep_composants = 3.5;

/* [Carte : positions sur les flancs, relevées sur le plan] */
// Centre de la prise USB-C le long de Y (flanc droit en vue de dos)
usb_y = -1.0;
// Axe de la prise USB-C au-dessus du dos du circuit
usb_dz = 1.6;
// Boutons du flanc gauche le long de Y
pwr_y = 9.0;
boot_y = -0.3;
rst_y = -9.6;
// Axe des boutons au-dessus du dos du circuit
bouton_dz = 0.9;

/* [Accu LiPo] */
// 502030 par défaut (5 x 20 x 30 mm). 4 pour un 402030.
bat_ep = 5.0;
bat_l = 20;
bat_h = 30;

/* [Boîtier] */
paroi = 1.8;
facade = 1.0;      // épaisseur du rebord qui retient le verre
fond = 1.4;        // épaisseur de la plaque du couvercle
jeu = 0.25;        // jeu autour du verre
ajustement = 0.15; // jeu entre la jupe du couvercle et la coque
chanfrein = 0.8;
rayon_cavite = 5;  // inférieur au rayon des coins du verre : il rentre toujours

/* [Lame du bouton PWR] */
lame_ep = 0.8;     // épaisseur de la lame souple
lame_haut = 4.6;
fente = 0.6;
lame_y0 = -6;      // encastrement de la lame (entre RST et BOOT)
// Avancée de l'ergot dans la cavité : distance paroi -> poussoir du bouton PWR
ergot = 1.3;

/* [Anneau] */
anneau_ext = 11;
anneau_trou = 5.5;
anneau_ep = 5;
anneau_dep = 3.5;  // centre du trou au-delà du bord haut

/* [Hidden] */
$fn = 48;
eps = 0.01;

cav_l = verre_l + 2 * jeu;
cav_h = verre_h + 2 * jeu;
ext_l = cav_l + 2 * paroi;
ext_h = cav_h + 2 * paroi;
ext_r = rayon_cavite + paroi;

z_pcb_dos = facade + ep_ecran + ep_pcb;        // dos du circuit
z_module = z_pcb_dos + ep_composants;          // sommet des composants
prof = z_module + 0.3 + bat_ep + 0.3;          // profondeur de la coque
z_bouton = z_pcb_dos + bouton_dz;
z_usb = z_pcb_dos + usb_dz;

fen_l = zone_l + 1.2;
fen_h = zone_h + 1.2;
fen_r = 3.5;
fen_chanfrein = 0.6;

usb_larg = 12.8;   // laisse passer le surmoulage de la fiche
usb_haut = 7.0;

jupe_h = 3.0;
jupe_ep = 1.2;
z_cran = prof - jupe_h / 2;
cran_long = 10;

lame_y1 = pwr_y + 2.5;
x_paroi_g = -cav_l / 2;                        // face intérieure du flanc gauche

module rrect(l, h, r) {
  offset(r = r) square([l - 2 * r, h - 2 * r], center = true);
}

// ------------------------------------------------------------------ Coque
module coque_pleine() {
  hull() {
    linear_extrude(eps) rrect(ext_l - 2 * chanfrein, ext_h - 2 * chanfrein, ext_r - chanfrein);
    translate([0, 0, chanfrein]) linear_extrude(prof - chanfrein) rrect(ext_l, ext_h, ext_r);
  }
}

module anneau_plein() {
  hull() {
    translate([0, ext_h / 2 + anneau_dep, 0]) cylinder(d = anneau_ext, h = anneau_ep);
    translate([-anneau_ext / 2 - 2, ext_h / 2 - ext_r, 0]) cube([anneau_ext + 4, 1, anneau_ep]);
  }
}

module fenetre() {
  translate([0, zone_dy, 0]) hull() {
    translate([0, 0, -eps]) linear_extrude(eps)
      rrect(fen_l + 2 * fen_chanfrein, fen_h + 2 * fen_chanfrein, fen_r + fen_chanfrein);
    translate([0, 0, fen_chanfrein]) linear_extrude(facade) rrect(fen_l, fen_h, fen_r);
  }
}

module decoupe_usb() {
  translate([cav_l / 2 - 1.2, usb_y, z_usb]) rotate([0, 90, 0]) hull() {
    for (s = [-1, 1]) translate([0, s * (usb_larg - usb_haut) / 2, 0])
      cylinder(d = usb_haut, h = paroi + 2.4);
  }
}

// Fentes en U qui libèrent la lame du bouton PWR, et amincissement par l'intérieur.
module decoupe_lame() {
  z0 = z_bouton - lame_haut / 2;
  z1 = z_bouton + lame_haut / 2;
  x0 = -ext_l / 2 - 1;
  lx = paroi + 2;
  translate([x0, lame_y0, z0 - fente]) cube([lx, lame_y1 - lame_y0 + fente, fente]);
  translate([x0, lame_y0, z1]) cube([lx, lame_y1 - lame_y0 + fente, fente]);
  translate([x0, lame_y1, z0 - fente]) cube([lx, fente, lame_haut + 2 * fente]);
  // perçages de décharge à l'encastrement
  for (z = [z0 - fente / 2, z1 + fente / 2])
    translate([x0, lame_y0, z]) rotate([0, 90, 0]) cylinder(d = 1.2, h = lx, $fn = 16);
  translate([-ext_l / 2 + lame_ep, lame_y0, z0]) cube([paroi, lame_y1 - lame_y0, lame_haut]);
}

// Ergot porté par la lame : appuie sur le poussoir de PWR. Ses rampes laissent
// passer le verre au montage (la lame s'écarte) et au démontage.
module ergot_pwr() {
  x_base = -ext_l / 2 + lame_ep;
  hull() {
    translate([x_base - eps, pwr_y - 2, z_bouton - 2.2]) cube([eps, 4, 4.4]);
    translate([x_paroi_g + ergot - eps, pwr_y - 1.4, z_bouton - 0.5]) cube([eps, 2.8, 1.0]);
  }
}

module trou_epingle(y) {
  translate([-ext_l / 2 - 1, y, z_bouton]) rotate([0, 90, 0]) cylinder(d = 2.0, h = paroi + 2, $fn = 20);
}

// Rainures où viennent se loger les crans du couvercle.
module rainures() {
  for (s = [-1, 1]) translate([s * cav_l / 2, 0, z_cran]) rotate([90, 0, 0])
    cylinder(r = 0.45, h = cran_long + 1, center = true, $fn = 20);
}

module coque() {
  difference() {
    union() {
      coque_pleine();
      anneau_plein();
    }
    translate([0, 0, facade]) linear_extrude(prof) rrect(cav_l, cav_h, rayon_cavite);
    fenetre();
    translate([0, ext_h / 2 + anneau_dep, -1]) cylinder(d = anneau_trou, h = anneau_ep + 2);
    decoupe_usb();
    decoupe_lame();
    trou_epingle(boot_y); // traverse la lame : BOOT reste accessible à l'épingle
    trou_epingle(rst_y);
    rainures();
    // encoche pour glisser l'ongle sous le couvercle (bord bas)
    translate([-4, -ext_h / 2 - 1, prof - 1]) cube([8, paroi * 0.6 + 1, 1 + eps]);
  }
  ergot_pwr();
}

// -------------------------------------------------------------- Couvercle
module couvercle() {
  // plaque
  hull() {
    translate([0, 0, prof]) linear_extrude(fond - chanfrein) rrect(ext_l, ext_h, ext_r);
    translate([0, 0, prof + fond - eps]) linear_extrude(eps)
      rrect(ext_l - 2 * chanfrein, ext_h - 2 * chanfrein, ext_r - chanfrein);
  }
  // jupe : quatre languettes (les angles sont ouverts pour la souplesse)
  jl = cav_l - 2 * ajustement;
  jh = cav_h - 2 * ajustement;
  translate([0, 0, prof - jupe_h]) difference() {
    linear_extrude(jupe_h + eps) rrect(jl, jh, rayon_cavite - ajustement);
    translate([0, 0, -1]) linear_extrude(jupe_h + 2)
      rrect(jl - 2 * jupe_ep, jh - 2 * jupe_ep, rayon_cavite - ajustement - jupe_ep);
    for (sx = [-1, 1], sy = [-1, 1]) translate([sx * jl / 2, sy * jh / 2, 0])
      cube([2 * rayon_cavite + 1, 2 * rayon_cavite + 1, 2 * jupe_h + 4], center = true);
  }
  // crans
  for (s = [-1, 1]) translate([s * jl / 2, 0, z_cran]) rotate([90, 0, 0])
    cylinder(r = 0.35, h = cran_long, center = true, $fn = 20);
  // plots d'appui sur les quatre coins du circuit (pastilles de fixation)
  for (sx = [-1, 1], sy = [-1, 1])
    translate([sx * (pcb_l / 2 - 1.75), sy * (pcb_h / 2 - 1.84), z_pcb_dos])
      cylinder(d1 = 3.0, d2 = 4.5, h = prof - z_pcb_dos + eps);
  // nervures qui calent l'accu
  for (s = [-1, 1]) translate([s * (bat_l / 2 + 1.0) - 0.5, -12, prof - 2])
    cube([1.0, 24, 2 + eps]);
}

// ------------------------------------------------------- Carte (fantôme)
module carte_fantome() {
  color("black", 0.6) translate([0, 0, facade]) linear_extrude(1.6) rrect(verre_l, verre_h, 6.5);
  color("dimgray", 0.6) translate([0, 0, facade + 1.6]) linear_extrude(ep_ecran - 1.6)
    rrect(pcb_l, pcb_h, 4);
  color("royalblue", 0.6) translate([0, 0, facade + ep_ecran]) linear_extrude(ep_pcb)
    rrect(pcb_l, pcb_h, 4);
  // prise USB-C et boutons
  color("silver", 0.8) translate([pcb_l / 2 - 6.5, usb_y - 4.5, z_pcb_dos]) cube([8, 9, 3.2]);
  color("white", 0.8) for (y = [pwr_y, boot_y, rst_y])
    translate([-pcb_l / 2 - 0.6, y - 1.8, z_pcb_dos]) cube([3.2, 3.6, 1.8]);
  color("gold", 0.6) translate([-bat_l / 2, -bat_h / 2, z_module + 0.3]) cube([bat_l, bat_h, bat_ep]);
}

// -------------------------------------------------------------- Affichage
if (piece == "coque") {
  coque();
} else if (piece == "couvercle") {
  // retourné : plaque sur le plateau
  translate([0, 0, prof + fond]) rotate([180, 0, 0]) couvercle();
} else if (piece == "impression") {
  translate([-ext_l / 2 - 4, 0, 0]) coque();
  translate([ext_l / 2 + 4, 0, prof + fond]) rotate([180, 0, 0]) couvercle();
} else if (piece == "coupe") {
  difference() {
    union() {
      color("goldenrod") coque();
      color("darkorange") couvercle();
    }
    translate([-50, -100, -10]) cube([100, 100, 60]);
  }
  if (fantome) carte_fantome();
} else {
  color("goldenrod") coque();
  color("darkorange") translate([0, 0, 12]) couvercle(); // vue éclatée
  if (fantome) carte_fantome();
}

echo(str("Dimensions hors tout : ", ext_l, " x ", ext_h + anneau_dep + anneau_ext / 2, " x ", prof + fond, " mm"));
