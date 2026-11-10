"""Site web de la mediatheque (Flask).

Regles de securite de la couche web :
- les vues n'appellent QUE `Session` (controle des roles dans la couche metier) ;
- les sessions sont gardees cote serveur, le cookie ne contient qu'un jeton
  aleatoire signe (HttpOnly, SameSite=Lax) ;
- tout POST exige un jeton CSRF ;
- en-tetes de securite (CSP stricte, anti-iframe, nosniff) ;
- Jinja echappe automatiquement tout le HTML (pas de XSS via un titre).
"""
import csv
import io
import os
import secrets
import threading
from datetime import date
from functools import wraps
from pathlib import Path

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup

from ..auth import ADHERENT
from ..exceptions import AuthentificationError, MediathequeError
from ..mediatheque import Mediatheque
from ..session import Session, ouvrir_session

TYPES = [("livre", "Livre"), ("dvd", "DVD"), ("revue", "Revue")]
LIBELLE_EXTRA = {"livre": "Auteur", "dvd": "Durée (min)", "revue": "Numéro"}

ICONE_LOGO = Markup(
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" aria-hidden="true"><path d="M4 19V5a2 2 0 0 1 2-2h5v18H6a2 2 0 0 '
    '1-2-2z"/><path d="M11 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/></svg>')

# Aucun script autorise ; seuls les attributs style="" en ligne (largeur des jauges)
CSP = ("default-src 'self'; script-src 'none'; style-src 'self' https://fonts.googleapis.com; "
       "style-src-attr 'unsafe-inline'; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; "
       "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")


def create_app(db, secret_key=None, testing=False):
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
        TESTING=testing,
    )
    m = Mediatheque.charger(db)
    verrou = threading.RLock()
    sessions_actives = {}  # jeton -> Session (cote serveur)

    # ------------------------------------------------------------ outillage
    def compte_enregistre(compte):
        return any(c == compte for c in m.comptes)

    def session_courante():
        jeton = session.get("jeton")
        s = sessions_actives.get(jeton) if jeton else None
        if s is not None and not compte_enregistre(s.compte):
            # compte supprime ou mot de passe change ailleurs : on deconnecte
            sessions_actives.pop(jeton, None)
            s = None
        return s

    def connexion_requise(vue):
        @wraps(vue)
        def enveloppe(*args, **kwargs):
            g.s = session_courante()
            if g.s is None:
                return redirect(url_for("connexion"))
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
        """POST qui modifie l'etat : verrou, sauvegarde, erreurs metier en message."""
        @wraps(vue)
        def enveloppe(*args, **kwargs):
            with verrou:
                try:
                    reponse = vue(*args, **kwargs)
                    m.sauvegarder()
                    return reponse
                except (MediathequeError, ValueError) as e:
                    flash(str(e), "erreur")
                    return redirect(request.referrer or url_for("accueil"))
        return enveloppe

    @app.before_request
    def verifier_csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            envoye = request.form.get("csrf", "")
            if not secrets.compare_digest(envoye, session["csrf"]):
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
                "aujourdhui": date.today(), "TYPES": TYPES, "LIBELLE_EXTRA": LIBELLE_EXTRA}

    @app.template_filter("fr")
    def date_fr(d):
        return d.strftime("%d/%m/%Y") if d else ""

    # --------------------------------------------------------- connexion
    @app.get("/")
    def accueil():
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
            try:
                with verrou:
                    s = ouvrir_session(m, identifiant, request.form.get("mot_de_passe", "")[:256])
            except AuthentificationError as e:
                erreur = str(e)
            else:
                ancien = session.pop("jeton", None)
                sessions_actives.pop(ancien, None)
                session.clear()  # nouvelle session : evite la fixation de session
                jeton = secrets.token_urlsafe(32)
                sessions_actives[jeton] = s
                session["jeton"] = jeton
                session["csrf"] = secrets.token_urlsafe(32)
                return redirect(url_for("accueil"))
        return render_template("connexion.html", erreur=erreur, identifiant=identifiant)

    @app.post("/deconnexion")
    def deconnexion():
        s = sessions_actives.pop(session.get("jeton"), None)
        if s is not None:
            s.fermer()
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
        tous = g.s.catalogue()
        resultats = g.s.catalogue(texte, type_doc)
        mes_reservations = set()
        if not g.s.est_responsable:
            compte = g.s.mon_compte()
            mes_reservations = {r["document"].id for r in compte["reservations"]}
            mes_reservations |= {e["document"].id for e in compte["emprunts"]}
        lignes = [{"doc": d, "statut": st, "attente": g.s.file_attente(d.id),
                   "deja": d.id in mes_reservations} for d, st in resultats]
        return render_template(
            "catalogue.html", lignes=lignes, texte=texte, type_doc=type_doc,
            total=len(tous), dispo=sum(1 for _, st in tous if st == "disponible"))

    @app.post("/reserver/<id_document>")
    @connexion_requise
    @action
    def reserver(id_document):
        g.s.reserver(id_document)
        flash("Réservation enregistrée : le document vous sera mis de côté à son retour.", "ok")
        return redirect(request.referrer or url_for("catalogue"))

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
        return render_template("compte.html", c=g.s.mon_compte())

    @app.post("/compte/mot-de-passe")
    @connexion_requise
    @action
    def changer_mot_de_passe():
        nouveau = request.form.get("nouveau", "")
        if nouveau != request.form.get("confirmation", ""):
            raise MediathequeError("les deux mots de passe ne correspondent pas")
        try:
            g.s.changer_mot_de_passe(request.form.get("ancien", ""), nouveau)
        except AuthentificationError:
            raise MediathequeError("mot de passe actuel incorrect") from None
        # le compte a change : reconnecter proprement la session courante
        compte = next(c for c in m.comptes if c.identifiant == g.s.compte.identifiant)
        sessions_actives[session["jeton"]] = Session(m, compte)
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
            adherents=adherents,
            prochain_doc=_prochain("D", ids),
            prochain_adh=_prochain("A", [a.numero for a, _ in adherents]))

    @app.post("/admin/documents")
    @responsable_requis
    @action
    def admin_ajouter_document():
        f = request.form
        d = g.s.ajouter_document(f["type"], f["id"].strip(), f["titre"].strip(),
                                 f["annee"].strip(), f["extra"].strip())
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
        a = g.s.ajouter_adherent(f["numero"].strip(), f["nom"].strip(),
                                 f["prenom"].strip(), f["type"])
        if f.get("identifiant", "").strip():
            g.s.creer_compte(f["identifiant"], f["mot_de_passe"], ADHERENT, a.numero)
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
