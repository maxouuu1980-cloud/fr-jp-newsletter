import os, pathlib
from flask import Flask, render_template, redirect, url_for, session, request, abort, send_from_directory
import stripe

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY","changeme")
SITE = pathlib.Path(__file__).resolve().parents[1] / "site"

stripe.api_key = os.getenv("STRIPE_SECRET_KEY","")
PRICE_ID = os.getenv("STRIPE_PRICE_ID","")

def is_authenticated():
    return session.get("subscribed") is True

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/archives/")
def archives():
    if not is_authenticated():
        return redirect(url_for("subscribe"))
    return send_from_directory(SITE, "index.html")

@app.route("/issue/<date>/")
def issue(date):
    if not is_authenticated():
        return redirect(url_for("subscribe"))
    return send_from_directory(SITE / date, "index.html")

@app.route("/subscribe/")
def subscribe():
    if not PRICE_ID or not stripe.api_key:
        return render_template("subscribe.html", error="Stripe n'est pas configuré.")
    return render_template("subscribe.html", price_id=PRICE_ID)

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    if not PRICE_ID or not stripe.api_key:
        abort(400, "Stripe non configuré")
    domain = request.url_root.strip("/")
    checkout = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url=f"{domain}/success",
        cancel_url=f"{domain}/subscribe",
    )
    return redirect(checkout.url, code=303)

@app.route("/success")
def success():
    session["subscribed"] = True
    return render_template("success.html")

@app.route("/static/<path:fname>")
def static_files(fname):
    return send_from_directory(SITE, fname)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
