"""Site web de la mediatheque (Flask).

Regles de securite de la couche web :
- les vues n'appellent QUE `Session` (controle des roles dans la couche metier) ;
- les sessions sont gardees cote serveur, le cookie ne contient qu'un jeton
  aleatoire signe (HttpOnly, SameSite=Lax) ;
- tout POST exige un jeton CSRF ;
- en-tetes de securite (CSP stricte, anti-iframe, nosniff) ;
- Jinja echappe automatiquement tout le HTML (pas de XSS via un titre).
- le hachage scrypt (lent, 128 Mo) ne se fait jamais sous le verrou global :
  au plus HACHAGES_SIMULTANES a la fois, 503 si le site est sature, et une
  limite de tentatives de connexion par adresse IP (429 au-dela).
"""
import csv
import io
import os
import re
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import date
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import (Flask, Response, abort, flash, g, get_flashed_messages, redirect,
                   render_template, request, session, url_for)
from markupsafe import Markup

from ..exceptions import AuthentificationError, MediathequeError
from ..mediatheque import Mediatheque
from ..session import ouvrir_session

TYPES = [("livre", "Livre"), ("dvd", "DVD"), ("revue", "Revue")]
LIBELLE_EXTRA = {"livre": "Auteur", "dvd": "Durée (min)", "revue": "Numéro"}

NOM_MEDIATHEQUE = os.environ.get("MEDIATHEQUE_NOM", "Médiathèque des Tilleuls")

# Trois livres sur une etagere : le logo est dessine, pas une icone de bibliotheque d'icones
ICONE_LOGO = Markup(
    '<svg class="logo-svg" width="34" height="30" viewBox="0 0 34 30" aria-hidden="true">'
    '<rect x="2" y="6" width="7" height="20" rx="1" fill="currentColor"/>'
    '<rect x="11" y="3" width="6" height="23" rx="1" fill="var(--accent-vif)"/>'
    '<rect x="19.5" y="8" width="6" height="18" rx="1" fill="currentColor" '
    'transform="rotate(-12 22.5 26)"/>'
    '<rect x="0" y="27" width="34" height="2.2" rx="1" fill="currentColor"/></svg>')

MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
               "sept.", "oct.", "nov.", "déc."]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
TEINTES = 8  # nombre de couleurs de couverture definies dans style.css


def cote(doc):
    """Cote facon etiquette de dos : LIV HUG, DVD INC, PER SCI."""
    prefixe = {"livre": "LIV", "dvd": "DVD", "revue": "PER"}.get(doc.CLE, "DOC")
    source = doc.detail if doc.CLE == "livre" else doc.titre
    mots = [w for w in source.replace("'", " ").replace(".", " ").split()
            if len(w) > 2 and w.lower() not in ("les", "des", "une", "the")]
    lettres = (mots[-1] if doc.CLE == "livre" and mots else (mots[0] if mots else source))
    lettres = "".join(c for c in lettres.upper() if c.isalpha())[:3]
    return f"{prefixe} {lettres}"


def teinte(doc):
    """Couleur de couverture stable pour un document (0..TEINTES-1)."""
    return sum(map(ord, doc.id + doc.titre)) % TEINTES


DOSSIER_COUVERTURES = Path(__file__).resolve().parent / "static" / "couvertures"


def couverture(doc):
    """Chemin static/ de la vraie couverture si elle a ete telechargee, sinon None
    (le gabarit dessine alors la couverture typographique)."""
    nom = f"{doc.id}.jpg"
    if re.fullmatch(r"D\d{1,6}\.jpg", nom) and (DOSSIER_COUVERTURES / nom).is_file():
        return f"couvertures/{nom}"
    return None


def date_courte(d):
    return f"{d.day} {MOIS_COURTS[d.month - 1]}" if d else ""


def date_longue(d):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS_COURTS[d.month - 1].rstrip('.')} {d.year}"

# Aucun script autorise ; seuls les attributs style="" en ligne (largeur des jauges)
CSP = ("default-src 'self'; script-src 'none'; style-src 'self' https://fonts.googleapis.com; "
       "style-src-attr 'unsafe-inline'; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; "
       "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")

HACHAGES_SIMULTANES = 2      # scrypt N=2**17 : 128 Mo de memoire par calcul
ATTENTE_HACHAGE_S = 3        # au-dela, 503 (site sature)
TENTATIVES_PAR_IP = 10       # tentatives de connexion par adresse...
FENETRE_IP_S = 60            # ...sur une fenetre glissante d'une minute
INACTIVITE_S = 30 * 60       # session fermee apres 30 min sans requete
DUREE_MAX_S = 12 * 3600      # et dans tous les cas 12 h apres la connexion
SESSIONS_PAR_COMPTE = 5     # au-dela, la plus ancienne session du compte est fermee
MESSAGE_EXPIRATION ="session expirée, reconnectez-vous"


class LimiteParIP:
    """Fenetre glissante en memoire : au plus `limite` tentatives par
    `fenetre` secondes et par adresse. Une connexion reussie ne compte pas."""

    _MAX_ADRESSES = 10_000

    def __init__(self, limite, fenetre):
        self.limite, self.fenetre = limite, fenetre
        self._tentatives = {}  # adresse -> deque de dates (time.monotonic)
        self._verrou = threading.Lock()

    def entrer(self, adresse):
        """Enregistre une tentative ; renvoie sa date, ou None si la limite est atteinte."""
        maintenant = time.monotonic()
        with self._verrou:
            dates = self._tentatives.setdefault(adresse, deque())
            while dates and maintenant - dates[0] > self.fenetre:
                dates.popleft()
            if len(dates) >= self.limite:
                return None
            dates.append(maintenant)
            if len(self._tentatives) > self._MAX_ADRESSES:  # memoire bornee
                self._tentatives = {a: d for a, d in self._tentatives.items()
                                    if d and maintenant - d[-1] <= self.fenetre}
            return maintenant

    def oublier(self, adresse, date_tentative):
        """Retire une tentative (connexion reussie, ou jamais traitee)."""
        with self._verrou:
            dates = self._tentatives.get(adresse)
            if dates and date_tentative in dates:
                dates.remove(date_tentative)


def create_app(db, secret_key=None, testing=False, *,
               attente_hachage_s=ATTENTE_HACHAGE_S,
               tentatives_par_ip=TENTATIVES_PAR_IP, fenetre_ip_s=FENETRE_IP_S,
               inactivite_s=INACTIVITE_S, duree_max_s=DUREE_MAX_S):
    db = Path(db)
    if not db.exists():
        raise FileNotFoundError(
            f"{db} introuvable : creez-la avec `uv run mediatheque-init`")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key or os.environ.get("MEDIATHEQUE_SECRET") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("MEDIATHEQUE_HTTPS") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
        # le cookie signe lui-meme est refuse au-dela de la duree maximale ; il
        # reste un cookie de navigateur (non permanent), efface a la fermeture
        PERMANENT_SESSION_LIFETIME=duree_max_s,
        TESTING=testing,
    )
    m = Mediatheque.charger(db)
    verrou = threading.RLock()
    sessions_actives = {}  # jeton -> Session (cote serveur)
    horodatage = {}        # jeton -> [cree_le, vu_le] (time.monotonic) (W2)
    hachage = threading.BoundedSemaphore(HACHAGES_SIMULTANES)  # jamais sous `verrou` (W1)
    limite_ip = LimiteParIP(tentatives_par_ip, fenetre_ip_s)

    # ------------------------------------------------------------ outillage
    def page_precedente(defaut):
        """URL interne de retour : le chemin (et la recherche) de la page
        precedente si elle est sur ce site, sinon la page `defaut`. Jamais
        de redirection vers un autre site, meme si le CSRF etait assoupli."""
        precedente = urlsplit(request.referrer or "")
        if (precedente.scheme in ("http", "https") and precedente.netloc == request.host
                and precedente.path.startswith("/") and not precedente.path.startswith("//")):
            return precedente.path + (f"?{precedente.query}" if precedente.query else "")
        return url_for(defaut)

    @contextmanager
    def emplacement_hachage():
        """Un des HACHAGES_SIMULTANES emplacements, ou 503 si le site est sature."""
        if not hachage.acquire(timeout=attente_hachage_s):
            abort(503)
        try:
            yield
        finally:
            hachage.release()

    def compte_enregistre(compte):
        # session revoquee (compte supprime, role ou mot de passe change par le
        # responsable) : on deconnecte proprement au lieu d'une erreur 500
        return m.comptes.get(compte.identifiant) == compte

    def expiree(jeton, maintenant):
        cree, vu = horodatage.get(jeton, (float("-inf"), float("-inf")))
        return maintenant - vu > inactivite_s or maintenant - cree > duree_max_s

    def retirer(jeton):
        s = sessions_actives.pop(jeton, None)
        horodatage.pop(jeton, None)
        if s is not None:
            s.fermer()

    def purger(identifiant):
        """A chaque connexion (W3) : retire les sessions expirees ou revoquees,
        et ne garde que les SESSIONS_PAR_COMPTE - 1 plus recentes du compte
        qui se connecte (la plus ancienne est fermee)."""
        maintenant = time.monotonic()
        for jeton, s in list(sessions_actives.items()):
            if expiree(jeton, maintenant) or not compte_enregistre(s.compte):
                retirer(jeton)
        miennes = sorted((horodatage[j][0], j) for j, s in sessions_actives.items()
                         if s.compte.identifiant == identifiant)
        for _, jeton in miennes[:max(0, len(miennes) - SESSIONS_PAR_COMPTE + 1)]:
            retirer(jeton)

    def enregistrer(s):
        purger(s.compte.identifiant)
        jeton = secrets.token_urlsafe(32)
        maintenant = time.monotonic()
        sessions_actives[jeton] = s
        horodatage[jeton] = [maintenant, maintenant]
        return jeton

    def session_courante():
        jeton = session.get("jeton")
        s = sessions_actives.get(jeton) if jeton else None
        if s is None:
            return None
        maintenant = time.monotonic()
        if expiree(jeton, maintenant):
            # inactivite ou duree maximale depassee (W2) : message neutre
            retirer(jeton)
            session.pop("jeton", None)
            flash(MESSAGE_EXPIRATION, "expiration")
            return None
        if not compte_enregistre(s.compte):
            # compte supprime ou mot de passe change ailleurs : on deconnecte
            retirer(jeton)
            return None
        horodatage[jeton][1] = maintenant
        return s

    def connexion_requise(vue=None, *, sous_verrou=True):
        """Session valide exigee. La vue s'execute sous `verrou` (W5) : meme une
        page GET peut modifier l'etat (mon_compte -> actualiser_reservations).
        `sous_verrou=False` : seulement pour une vue qui hache un mot de passe
        (W1) et prend elle-meme le verrou pour modifier ou sauvegarder."""
        if vue is None:
            return lambda v: connexion_requise(v, sous_verrou=sous_verrou)

        @wraps(vue)
        def enveloppe(*args, **kwargs):
            with verrou:
                g.s = session_courante()
                if g.s is None:
                    return redirect(url_for("connexion"))
                if sous_verrou:
                    return vue(*args, **kwargs)
            return vue(*args, **kwargs)
        return enveloppe

    def responsable_requis(vue):
        @wraps(vue)
        @connexion_requise
        def enveloppe(*args, **kwargs):
            if not g.s.est_responsable:
                abort(403)
            return vue(*args, **kwargs)
        return enveloppe

    def action(vue):
        """POST qui modifie l'etat : verrou, sauvegarde, erreurs metier en message.
        Atomique (W4) : si la vue ou la sauvegarde echoue, la memoire est
        rechargee depuis la base, en place."""
        @wraps(vue)
        def enveloppe(*args, **kwargs):
            with verrou:
                try:
                    reponse = vue(*args, **kwargs)
                    m.sauvegarder()
                    return reponse
                except BaseException as e:
                    m.recharger()  # memoire = base, quoi qu'il arrive
                    if not isinstance(e, (MediathequeError, ValueError)):
                        raise
                    flash(str(e), "erreur")
                    return redirect(page_precedente("accueil"))
        return enveloppe

    @app.before_request
    def verifier_csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            envoye = request.form.get("csrf", "")
            # en octets : compare_digest(str, str) leve TypeError hors ASCII (W6)
            if not secrets.compare_digest(envoye.encode(), session["csrf"].encode()):
                abort(400, "jeton CSRF invalide")

    @app.after_request
    def entetes_securite(reponse):
        reponse.headers["Content-Security-Policy"] = CSP
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["Referrer-Policy"] = "same-origin"
        reponse.headers["Cache-Control"] = "no-store"
        return reponse

    @app.context_processor
    def contexte():
        s = getattr(g, "s", None)
        csrf = session.get("csrf", "")

        def jeton():
            return Markup('<input type="hidden" name="csrf" value="{}">').format(csrf)

        return {"csrf": csrf, "jeton": jeton, "icone_logo": ICONE_LOGO, "s": s,
                "nom_mediatheque": NOM_MEDIATHEQUE, "cote": cote, "teinte": teinte,
                "couverture": couverture,
                "aujourdhui": date.today(), "TYPES": TYPES, "LIBELLE_EXTRA": LIBELLE_EXTRA}

    @app.template_filter("fr")
    def date_fr(d):
        return d.strftime("%d/%m/%Y") if d else ""

    app.add_template_filter(date_courte, "court")
    app.add_template_filter(date_longue, "long")

    # --------------------------------------------------------- connexion
    @app.get("/")
    def accueil():
        with verrou:  # registre des sessions partage entre les threads
            s = session_courante()
        if s is None:
            return redirect(url_for("connexion"))
        return redirect(url_for("tableau_de_bord" if s.est_responsable else "catalogue"))

    @app.route("/connexion", methods=["GET", "POST"])
    def connexion():
        erreur = None
        identifiant = ""
        if request.method == "POST":
            identifiant = request.form.get("identifiant", "")[:64]
            adresse = request.remote_addr or "?"
            tentative = limite_ip.entrer(adresse)
            if tentative is None:
                abort(429)
            try:
                # scrypt HORS du verrou global (W1), sous le semaphore
                with emplacement_hachage():
                    s = ouvrir_session(m, identifiant,
                                       request.form.get("mot_de_passe", "")[:256])
            except AuthentificationError as e:
                erreur = str(e)
            except BaseException:  # 503 (sature) : la tentative n'a pas eu lieu
                limite_ip.oublier(adresse, tentative)
                raise
            else:
                limite_ip.oublier(adresse, tentative)  # une reussite ne compte pas
                ancien = session.pop("jeton", None)
                session.clear()  # nouvelle session : evite la fixation de session
                with verrou:  # registre partage entre les threads
                    retirer(ancien)
                    session["jeton"] = enregistrer(s)
                session["csrf"] = secrets.token_urlsafe(32)
                return redirect(url_for("accueil"))
        else:
            # la page de connexion n'affiche pas les messages flash du gabarit :
            # le message d'expiration (W2) passe par l'emplacement d'erreur
            erreur = next(iter(get_flashed_messages(category_filter=["expiration"])), None)
        return render_template("connexion.html", erreur=erreur, identifiant=identifiant)

    @app.post("/deconnexion")
    def deconnexion():
        jeton = session.get("jeton")
        with verrou:
            if jeton in sessions_actives:
                retirer(jeton)
        session.clear()
        return redirect(url_for("connexion"))

    # ---------------------------------------------------------- adherent
    @app.get("/catalogue")
    @connexion_requise
    def catalogue():
        texte = request.args.get("q", "")[:100]
        type_doc = request.args.get("type") or None
        if type_doc not in (None, *dict(TYPES)):
            type_doc = None
        genres = g.s.genres()
        genre = request.args.get("genre") or None
        if genre not in {nom for nom, _ in genres}:
            genre = None
        tous = g.s.catalogue()
        resultats = g.s.catalogue(texte, type_doc, genre)
        return render_template(
            "catalogue.html", lignes=lignes_etagere(resultats), texte=texte, type_doc=type_doc,
            genre=genre, genres=genres,
            total=len(tous), dispo=sum(1 for _, st in tous if st == "disponible"))

    def mes_documents():
        """{id: libelle} des documents que le lecteur a chez lui ou a reserves."""
        if g.s.est_responsable:
            return {}
        compte = g.s.mon_compte()
        a_moi = {r["document"].id: "Réservé ✓" for r in compte["reservations"]}
        a_moi |= {e["document"].id: "Chez vous" for e in compte["emprunts"]}
        return a_moi

    def lignes_etagere(documents_statuts, raisons=None):
        a_moi = mes_documents()
        return [{"doc": d, "statut": st, "attente": g.s.file_attente(d.id),
                 "a_moi": a_moi.get(d.id), "raison": (raisons or {}).get(d.id)}
                for d, st in documents_statuts]

    @app.get("/document/<id_document>")
    @connexion_requise
    def document(id_document):
        if not re.fullmatch(r"D\d{1,6}", id_document):
            abort(404)
        try:
            f = g.s.fiche(id_document)
        except MediathequeError:
            abort(404)
        return render_template(
            "document.html", f=f, d=f["document"], a_moi=mes_documents().get(id_document),
            meme_createur=lignes_etagere(f["meme_createur"]),
            similaires=lignes_etagere(g.s.similaires(id_document)))

    @app.post("/reserver/<id_document>")
    @connexion_requise
    @action
    def reserver(id_document):
        g.s.reserver(id_document)
        flash("Réservation enregistrée : le document vous sera mis de côté à son retour.", "ok")
        return redirect(page_precedente("catalogue"))

    @app.post("/annuler/<id_document>")
    @connexion_requise
    @action
    def annuler(id_document):
        g.s.annuler_reservation(id_document)
        flash("Réservation annulée.", "ok")
        return redirect(url_for("compte"))

    @app.get("/compte")
    @connexion_requise
    def compte():
        if g.s.est_responsable:
            return redirect(url_for("tableau_de_bord"))
        suggestions = g.s.pour_moi(n=6)
        pour_vous = lignes_etagere([(x["document"], x["statut"]) for x in suggestions],
                                   {x["document"].id: x["raison"] for x in suggestions})
        return render_template("compte.html", c=g.s.mon_compte(), pour_vous=pour_vous)

    @app.post("/compte/mot-de-passe")
    @connexion_requise(sous_verrou=False)
    def changer_mot_de_passe():
        # Pas de @action : les deux scrypt se font HORS du verrou global (W1),
        # sous le semaphore ; seule la sauvegarde prend le verrou.
        nouveau = request.form.get("nouveau", "")
        try:
            if nouveau != request.form.get("confirmation", ""):
                raise MediathequeError("les deux mots de passe ne correspondent pas")
            with emplacement_hachage():
                try:
                    g.s.changer_mot_de_passe(request.form.get("ancien", ""), nouveau)
                except AuthentificationError:
                    raise MediathequeError("mot de passe actuel incorrect") from None
        except MediathequeError as e:
            flash(str(e), "erreur")
            return redirect(url_for("compte"))
        with verrou:
            try:
                m.sauvegarder()
            except BaseException:
                m.recharger()  # W4 : la memoire ne garde pas un changement non enregistre
                raise
        # la Session met elle-meme son compte a jour (S4) : rien a reconstruire
        flash("Mot de passe modifié.", "ok")
        return redirect(url_for("compte"))

    # ------------------------------------------------------- responsable
    @app.get("/admin")
    @responsable_requis
    def tableau_de_bord():
        catalogue_complet = g.s.catalogue()
        adherents = g.s.adherents()
        noms = {a.numero: a.nom_complet for a in adherents}
        comptes_adh = [g.s.mon_compte(a.numero) for a in adherents]
        stats = {
            "documents": len(catalogue_complet),
            "en_rayon": sum(1 for _, st in catalogue_complet if st == "disponible"),
            "emprunts": sum(len(c["emprunts"]) for c in comptes_adh),
            "emprunteurs": sum(1 for c in comptes_adh if c["emprunts"]),
            "reservations": sum(len(c["reservations"]) for c in comptes_adh),
            "mises_de_cote": sum(1 for c in comptes_adh for r in c["reservations"]
                                 if r["statut"] == "disponible"),
        }
        retards = [{"emprunt": e, "doc": d, "jours": j, "nom": noms.get(e.numero_adherent, "")}
                   for e, d, j in g.s.retards()]
        top = [(noms.get(num, num), nb) for num, nb in g.s.statistiques()]
        return render_template(
            "admin_tableau.html", stats=stats, retards=retards, top=top,
            top_max=max((nb for _, nb in top), default=1),
            documents=[d for d, _ in catalogue_complet], adherents=adherents,
            onglet=request.args.get("onglet", "emprunt"))

    @app.post("/admin/emprunt")
    @responsable_requis
    @action
    def admin_emprunt():
        e = g.s.enregistrer_emprunt(request.form["id_document"], request.form["numero"])
        flash(f"Emprunt de {e.id_document} par {e.numero_adherent} enregistré.", "ok")
        return redirect(url_for("tableau_de_bord"))

    @app.post("/admin/retour")
    @responsable_requis
    @action
    def admin_retour():
        e = g.s.enregistrer_retour(request.form["id_document"])
        message = f"Retour de {e.id_document} enregistré."
        if g.s.file_attente(e.id_document):
            message += " Le document est mis de côté pour le premier de la file."
        flash(message, "ok")
        return redirect(url_for("tableau_de_bord", onglet="retour"))

    @app.get("/admin/retards.csv")
    @responsable_requis
    def admin_retards_csv():
        tampon = io.StringIO()
        ecrivain = csv.writer(tampon)
        ecrivain.writerow(["id_document", "titre", "numero_adherent", "jours_retard"])
        for e, d, j in g.s.retards():
            ecrivain.writerow([_cellule(e.id_document), _cellule(d.titre),
                               _cellule(e.numero_adherent), j])
        return Response(tampon.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=retards.csv"})

    @app.get("/admin/gestion")
    @responsable_requis
    def gestion():
        onglet = "adherents" if request.args.get("onglet") == "adherents" else "documents"
        catalogue_complet = g.s.catalogue()
        adherents = [(a, g.s.mon_compte(a.numero)) for a in g.s.adherents()]
        ids = [d.id for d, _ in catalogue_complet]
        return render_template(
            "admin_gestion.html", onglet=onglet, documents=catalogue_complet,
            adherents=adherents, genres=g.s.genres(),
            prochain_doc=_prochain("D", ids),
            prochain_adh=_prochain("A", [a.numero for a, _ in adherents]))

    @app.post("/admin/documents")
    @responsable_requis
    @action
    def admin_ajouter_document():
        f = request.form
        d = g.s.ajouter_document(
            f["type"], f["id"].strip(), f["titre"].strip(), f["annee"].strip(), f["extra"].strip(),
            genre=f.get("genre", "").strip(), resume=f.get("resume", "").strip(),
            themes=[t for t in f.get("themes", "").split(",")])
        flash(f"« {d.titre} » ajouté au catalogue.", "ok")
        return redirect(url_for("gestion"))

    @app.post("/admin/documents/<id_document>/supprimer")
    @responsable_requis
    @action
    def admin_supprimer_document(id_document):
        d = g.s.supprimer_document(id_document)
        flash(f"« {d.titre} » supprimé du catalogue.", "ok")
        return redirect(url_for("gestion"))

    @app.post("/admin/adherents")
    @responsable_requis
    @action
    def admin_ajouter_adherent():
        f = request.form
        # identifiant et mot de passe valides AVANT la creation de l'adherent (W4)
        a = g.s.ajouter_adherent(f["numero"].strip(), f["nom"].strip(),
                                 f["prenom"].strip(), f["type"],
                                 f.get("identifiant", "").strip() or None,
                                 f.get("mot_de_passe", ""))
        flash(f"Adhérent {a.numero} ({a.nom_complet}) créé.", "ok")
        return redirect(url_for("gestion", onglet="adherents"))

    @app.post("/admin/comptes/mot-de-passe")
    @responsable_requis
    @action
    def admin_reinitialiser():
        g.s.reinitialiser_mot_de_passe(request.form["identifiant"].strip().lower(),
                                       request.form["mot_de_passe"])
        flash("Mot de passe réinitialisé.", "ok")
        return redirect(url_for("gestion", onglet="adherents"))

    @app.errorhandler(403)
    def interdit(_):
        return render_template("erreur.html", code=403,
                               message="Cette page est réservée au responsable."), 403

    @app.errorhandler(400)
    def mauvaise_requete(_):
        return render_template("erreur.html", code=400,
                               message="Requête invalide ou expirée. Rechargez la page."), 400

    @app.errorhandler(404)
    def introuvable(_):
        return render_template("erreur.html", code=404, message="Page introuvable."), 404

    @app.errorhandler(429)
    def trop_de_tentatives(_):
        return render_template(
            "erreur.html", code=429,
            message="Trop de tentatives de connexion depuis cette adresse. "
                    "Patientez une minute avant de réessayer."
        ), 429, {"Retry-After": str(int(fenetre_ip_s))}

    @app.errorhandler(503)
    def site_sature(_):
        return render_template(
            "erreur.html", code=503,
            message="Beaucoup de lecteurs se connectent en même temps. "
                    "Réessayez dans quelques secondes."
        ), 503, {"Retry-After": "5"}

    app.extensions["mediatheque"] = m
    return app


def _cellule(valeur):
    """Neutralise les formules a l'ouverture dans Excel (injection CSV)."""
    texte = str(valeur)
    return "'" + texte if texte[:1] in ("=", "+", "-", "@", "\t", "\r") else texte


def _prochain(prefixe, existants):
    nums = [int(x[1:]) for x in existants if x[1:].isdigit()]
    return f"{prefixe}{max(nums, default=0) + 1:03d}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Lance le site de la mediatheque")
    parser.add_argument("--db", default="mediatheque.db")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app = create_app(args.db)
    print(f"Site disponible sur http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
