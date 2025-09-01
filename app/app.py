import os, pathlib, json
from flask import Flask, render_template, redirect, url_for, session, request, abort, send_from_directory
import stripe

# -----------------------------
# Config Flask / chemins
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "changeme")
SITE = pathlib.Path(__file__).resolve().parents[1] / "site"

# -----------------------------
# Stripe (clés depuis variables d'environnement)
# -----------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# -----------------------------
# Helpers
# -----------------------------
def is_authenticated():
    """MVP : accès basé sur la session navigateur.
    Pour un système robuste multi-appareils, remplacer par une vérification en base
    (customer_id / email -> abonnement actif)."""
    return session.get("subscribed") is True

# -----------------------------
# Routes publiques
# -----------------------------
@app.route("/")
def home():
    # landing minimal : redirige ou rend un template
    return render_template("home.html")

@app.route("/subscribe/")
def subscribe():
    # Affiche le bouton Stripe Checkout
    # Si PRICE_ID ou stripe.api_key manquent, on montre un message d'erreur
    error = None
    if not PRICE_ID or not stripe.api_key:
        error = "Stripe n'est pas configuré (STRIPE_SECRET_KEY / STRIPE_PRICE_ID)."
    return render_template("subscribe.html", error=error, price_id=PRICE_ID)

# -----------------------------
# Paiement / Stripe Checkout
# -----------------------------
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    if not PRICE_ID or not stripe.api_key:
        abort(400, "Stripe non configuré")
    # Domaine de base pour redirections de Stripe (succès / annulation)
    domain = request.url_root.strip("/")
    checkout = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url=f"{domain}/success",
        cancel_url=f"{domain}/subscribe",
    )
    # Redirection 303 vers l'URL Stripe
    return redirect(checkout.url, code=303)

@app.route("/success")
def success():
    # MVP : marquer la session comme abonnée
    # (Robuste : attendre le webhook puis vérifier en base)
    session["subscribed"] = True
    return render_template("success.html")

# -----------------------------
# Paywall : archives + issues
# -----------------------------
@app.route("/archives/")
def archives():
    if not is_authenticated():
        return redirect(url_for("subscribe"))
    # Sert la page d'index des archives générée par le script (site/index.html)
    return send_from_directory(SITE, "index.html")

@app.route("/issue/<date>/")
def issue(date):
    if not is_authenticated():
        return redirect(url_for("subscribe"))
    # Sert le numéro daté : site/YYYY-MM-DD/index.html
    issue_dir = SITE / date
    if not issue_dir.exists():
        abort(404)
    return send_from_directory(issue_dir, "index.html")

# -----------------------------
# Webhook Stripe (robuste)
# -----------------------------
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Réception des événements Stripe.
    À minima, on gère checkout.session.completed.
    Pour un suivi complet, gérer aussi customer.subscription.updated / deleted, etc."""
    if not WEBHOOK_SECRET:
        abort(400, "Webhook secret not set")

    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig, secret=WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return "invalid", 400

    # Traite les événements utiles
    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        # Exemples de champs disponibles :
        # customer_id = session_obj.get("customer")
        # subscription_id = session_obj.get("subscription")
        # customer_email = session_obj.get("customer_details", {}).get("email")
        #
        # TODO (robuste) :
        # 1) Enregistrer / mettre à jour l'abonné dans une BDD (email/customer_id)
        # 2) Marquer le statut = active
        # 3) À la connexion, vérifier l'état en base au lieu d'une simple session
        pass

    # Autres événements intéressants :
    # - customer.subscription.updated
    # - customer.subscription.deleted
    # TODO : gérer la révocation, la période expirée, etc.

    return "ok", 200

# -----------------------------
# Static files (si besoin)
# -----------------------------
@app.route("/static/<path:fname>")
def static_files(fname):
    # Sert des fichiers statiques depuis /site si tu en as besoin
    return send_from_directory(SITE, fname)

# -----------------------------
# Lancement local
# -----------------------------
if __name__ == "__main__":
    # En local : FLASK_APP=app/app.py flask run
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
