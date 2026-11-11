"""Tests sans réseau : structure du lien, domaine enregistré et verdict."""

import pytest

from cyberscope.analyzer import anatomy
from cyberscope.link_analysis import check_link
from cyberscope.net import is_valid_url, normalize_url, registrable_domain
from cyberscope.scoring import build_verdict, combined_risk


@pytest.mark.parametrize("host, expected", [
    ("www.google.com", "google.com"),
    ("login.paypal.com.secure-check.io", "secure-check.io"),
    ("www.impots.gouv.fr", "impots.gouv.fr"),
    ("shop.example.co.uk", "example.co.uk"),
    ("192.168.1.10", "192.168.1.10"),
])
def test_registrable_domain(host, expected):
    assert registrable_domain(host) == expected


def test_normalize_and_validate():
    assert normalize_url("bit.ly/abc") == "https://bit.ly/abc"
    assert is_valid_url("https://exemple.fr/page")
    assert not is_valid_url("https://exemple .fr")
    assert not is_valid_url("ftp://exemple.fr")


@pytest.mark.parametrize("url", [
    "https://www.paypal.com/signin",
    "https://www.impots.gouv.fr/accueil",
    "https://www.laposte.fr/outils/suivre-vos-envois",
    "https://orangina.fr",
    "https://cafe-du-coin.fr",
])
def test_official_or_unrelated_sites_are_not_flagged(url):
    check = check_link(url)
    assert all(signal["risk"] < 50 for signal in check["signals"]), check["signals"]


@pytest.mark.parametrize("url, brand", [
    ("https://paypal-secure-login.com/verify", "paypal"),
    ("https://ameli.remboursement-sante.com", "ameli"),
    ("https://colissimo.suivi-colis.top/livraison", "colissimo"),
    ("https://paypa1.com", "paypal"),
    ("https://arnazon.fr", "amazon"),
])
def test_brand_imitation_is_flagged(url, brand):
    check = check_link(url)
    assert check["status"] == "danger"
    assert brand in check["signals"][0]["text"]


def test_at_sign_hides_real_host():
    parts = anatomy("https://www.paypal.com@evil.example/login")
    assert parts["domain"] == "evil.example"
    assert parts["userinfo"] == "www.paypal.com@"
    assert check_link("https://www.paypal.com@evil.example/login")["status"] == "danger"


def test_strong_signal_is_not_diluted():
    # Un seul contrôle très inquiétant au milieu de contrôles sains = danger.
    checks = [
        {"id": "domain", "risk": 75, "signals": [{"text": "Domaine créé hier.", "risk": 75}]},
        {"id": "reputation", "risk": 0, "signals": []},
        {"id": "tls", "risk": 0, "signals": []},
        {"id": "destination", "risk": 0, "signals": []},
    ]
    verdict = build_verdict(checks)
    assert verdict["key"] == "danger"
    assert verdict["reasons"] == ["Domaine créé hier."]


def test_no_evaluable_check_gives_unknown():
    verdict = build_verdict([{"id": "tls", "risk": None, "signals": []}])
    assert verdict["key"] == "unknown"
    assert verdict["score"] is None


def test_combined_risk_bounds():
    assert combined_risk([]) == 0
    assert combined_risk([("reputation", 100)]) == 100
    assert combined_risk([("link", 50), ("domain", 50)]) > 50
