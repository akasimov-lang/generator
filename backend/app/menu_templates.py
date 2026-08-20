from __future__ import annotations

from typing import TypedDict


class MenuTemplateItem(TypedDict):
    external_id: str
    parent_external_id: str | None
    name: str
    path: str
    menu_type: str


def _item(
    external_id: str,
    parent_external_id: str | None,
    name: str,
    path: str,
) -> MenuTemplateItem:
    return {
        "external_id": external_id,
        "parent_external_id": parent_external_id,
        "name": name,
        "path": path,
        "menu_type": "header",
    }


DE_CASINO_REVIEW_HEADER_ITEMS: list[MenuTemplateItem] = [
    _item("de-online-casinos", None, "Online Casinos", "/online-casinos/"),
    _item("de-best-online-casinos", "de-online-casinos", "Beste Online Casinos", "/online-casinos/beste/"),
    _item("de-casino-tests", "de-online-casinos", "Casino Tests", "/online-casinos/tests/"),
    _item("de-all-casino-tests", "de-casino-tests", "Alle Casino Tests", "/online-casinos/tests/alle/"),
    _item("de-new-online-casinos", "de-casino-tests", "Neue Online Casinos", "/online-casinos/tests/neue/"),
    _item("de-trusted-online-casinos", "de-casino-tests", "Seriöse Online Casinos", "/online-casinos/tests/serioese/"),
    _item("de-mobile-casinos", "de-casino-tests", "Mobile Casinos", "/online-casinos/tests/mobile/"),
    _item("de-casino-types", "de-online-casinos", "Casino-Arten", "/online-casinos/arten/"),
    _item("de-casinos-without-oasis", "de-casino-types", "Casinos ohne OASIS", "/online-casinos/arten/ohne-oasis/"),
    _item("de-casinos-without-lugas", "de-casino-types", "Casinos ohne LUGAS", "/online-casinos/arten/ohne-lugas/"),
    _item("de-no-verification-casinos", "de-casino-types", "Casinos ohne Verifizierung", "/online-casinos/arten/ohne-verifizierung/"),
    _item("de-no-limit-casinos", "de-casino-types", "Casinos ohne Limit", "/online-casinos/arten/ohne-limit/"),
    _item("de-crypto-casinos", "de-casino-types", "Krypto Casinos", "/online-casinos/arten/krypto/"),
    _item("de-high-roller-casinos", "de-casino-types", "High Roller Casinos", "/online-casinos/arten/high-roller/"),
    _item("de-casinos-by-licence", "de-online-casinos", "Casinos nach Lizenz", "/online-casinos/lizenzen/"),
    _item("de-german-licensed-casinos", "de-casinos-by-licence", "Casinos mit deutscher Lizenz", "/online-casinos/lizenzen/deutschland/"),
    _item("de-mga-casinos", "de-casinos-by-licence", "MGA Casinos", "/online-casinos/lizenzen/mga/"),
    _item("de-international-casinos", "de-casinos-by-licence", "Internationale Casinos", "/online-casinos/lizenzen/international/"),
    _item("de-casinos-without-german-licence", "de-casinos-by-licence", "Casinos ohne deutsche Lizenz", "/online-casinos/lizenzen/ohne-deutsche-lizenz/"),
    _item("de-compare-casinos", "de-online-casinos", "Casinos vergleichen", "/online-casinos/vergleichen/"),

    _item("de-casino-bonuses", None, "Casino Boni", "/casino-boni/"),
    _item("de-best-casino-bonuses", "de-casino-bonuses", "Beste Casino Boni", "/casino-boni/beste/"),
    _item("de-bonus-types", "de-casino-bonuses", "Bonusarten", "/casino-boni/arten/"),
    _item("de-welcome-bonus", "de-bonus-types", "Willkommensbonus", "/casino-boni/arten/willkommensbonus/"),
    _item("de-no-deposit-bonus", "de-bonus-types", "Bonus ohne Einzahlung", "/casino-boni/arten/ohne-einzahlung/"),
    _item("de-free-spins", "de-bonus-types", "Freispiele", "/casino-boni/arten/freispiele/"),
    _item("de-cashback-bonus", "de-bonus-types", "Cashback Bonus", "/casino-boni/arten/cashback/"),
    _item("de-reload-bonus", "de-bonus-types", "Reload Bonus", "/casino-boni/arten/reload/"),
    _item("de-vip-loyalty-bonus", "de-bonus-types", "VIP- und Treuebonus", "/casino-boni/arten/vip-treue/"),
    _item("de-no-wagering-bonus", "de-bonus-types", "Bonus ohne Umsatzbedingungen", "/casino-boni/arten/ohne-umsatzbedingungen/"),
    _item("de-bonus-terms", "de-casino-bonuses", "Bonusbedingungen erklärt", "/casino-boni/bedingungen/"),
    _item("de-current-promotions", "de-casino-bonuses", "Aktuelle Aktionen", "/casino-boni/aktionen/"),

    _item("de-casino-games", None, "Casinospiele", "/casinospiele/"),
    _item("de-slots", "de-casino-games", "Spielautomaten", "/casinospiele/slots/"),
    _item("de-best-online-slots", "de-slots", "Beste Online Slots", "/casinospiele/slots/beste/"),
    _item("de-new-slots", "de-slots", "Neue Slots", "/casinospiele/slots/neue/"),
    _item("de-jackpot-slots", "de-slots", "Jackpot Slots", "/casinospiele/slots/jackpot/"),
    _item("de-megaways-slots", "de-slots", "Megaways Slots", "/casinospiele/slots/megaways/"),
    _item("de-free-slots", "de-slots", "Kostenlose Slots", "/casinospiele/slots/kostenlos/"),
    _item("de-live-casino", "de-casino-games", "Live Casino", "/casinospiele/live-casino/"),
    _item("de-live-roulette", "de-live-casino", "Live Roulette", "/casinospiele/live-casino/roulette/"),
    _item("de-live-blackjack", "de-live-casino", "Live Blackjack", "/casinospiele/live-casino/blackjack/"),
    _item("de-live-baccarat", "de-live-casino", "Live Baccarat", "/casinospiele/live-casino/baccarat/"),
    _item("de-live-game-shows", "de-live-casino", "Live Game Shows", "/casinospiele/live-casino/game-shows/"),
    _item("de-other-casino-games", "de-casino-games", "Weitere Casinospiele", "/casinospiele/weitere/"),
    _item("de-crash-games", "de-other-casino-games", "Crash Games", "/casinospiele/weitere/crash-games/"),
    _item("de-table-games", "de-other-casino-games", "Tischspiele", "/casinospiele/weitere/tischspiele/"),
    _item("de-video-poker", "de-other-casino-games", "Video Poker", "/casinospiele/weitere/video-poker/"),
    _item("de-bingo-keno", "de-other-casino-games", "Bingo und Keno", "/casinospiele/weitere/bingo-keno/"),
    _item("de-game-providers", "de-casino-games", "Spielehersteller", "/casinospiele/hersteller/"),

    _item("de-payments", None, "Zahlungen", "/zahlungen/"),
    _item("de-fast-payout-casinos", "de-payments", "Casinos mit schneller Auszahlung", "/zahlungen/schnelle-auszahlung/"),
    _item("de-payment-methods", "de-payments", "Zahlungsmethoden", "/zahlungen/methoden/"),
    _item("de-paypal-casinos", "de-payment-methods", "PayPal Casinos", "/zahlungen/methoden/paypal/"),
    _item("de-paysafecard-casinos", "de-payment-methods", "Paysafecard Casinos", "/zahlungen/methoden/paysafecard/"),
    _item("de-credit-card-casinos", "de-payment-methods", "Kreditkarten Casinos", "/zahlungen/methoden/kreditkarten/"),
    _item("de-ewallet-casinos", "de-payment-methods", "E-Wallet Casinos", "/zahlungen/methoden/e-wallets/"),
    _item("de-bank-transfer-casinos", "de-payment-methods", "Banküberweisung Casinos", "/zahlungen/methoden/bankueberweisung/"),
    _item("de-mobile-payments", "de-payment-methods", "Apple Pay und Google Pay", "/zahlungen/methoden/apple-google-pay/"),
    _item("de-bitcoin-crypto-payments", "de-payment-methods", "Bitcoin und Krypto", "/zahlungen/methoden/bitcoin-krypto/"),
    _item("de-deposits-withdrawals", "de-payments", "Ein- und Auszahlung", "/zahlungen/ein-auszahlung/"),
    _item("de-withdrawal-times", "de-deposits-withdrawals", "Auszahlungsdauer", "/zahlungen/ein-auszahlung/dauer/"),
    _item("de-payment-fees-limits", "de-deposits-withdrawals", "Gebühren und Limits", "/zahlungen/ein-auszahlung/gebuehren-limits/"),
    _item("de-withdrawal-kyc", "de-deposits-withdrawals", "KYC bei Auszahlungen", "/zahlungen/ein-auszahlung/kyc/"),

    _item("de-guides-safety", None, "Ratgeber & Sicherheit", "/ratgeber-sicherheit/"),
    _item("de-casino-guides", "de-guides-safety", "Casino Ratgeber", "/ratgeber-sicherheit/casino-ratgeber/"),
    _item("de-choose-online-casino", "de-casino-guides", "Online Casino auswählen", "/ratgeber-sicherheit/casino-ratgeber/auswahl/"),
    _item("de-registration-kyc", "de-casino-guides", "Registrierung und KYC", "/ratgeber-sicherheit/casino-ratgeber/registrierung-kyc/"),
    _item("de-rtp-winning-chances", "de-casino-guides", "RTP und Gewinnchancen", "/ratgeber-sicherheit/casino-ratgeber/rtp/"),
    _item("de-understand-bonus-terms", "de-casino-guides", "Bonusbedingungen verstehen", "/ratgeber-sicherheit/casino-ratgeber/bonusbedingungen/"),
    _item("de-laws-licences", "de-guides-safety", "Recht und Lizenzen", "/ratgeber-sicherheit/recht-lizenzen/"),
    _item("de-german-gambling-law", "de-laws-licences", "Glücksspielrecht in Deutschland", "/ratgeber-sicherheit/recht-lizenzen/deutschland/"),
    _item("de-ggl-explained", "de-laws-licences", "GGL erklärt", "/ratgeber-sicherheit/recht-lizenzen/ggl/"),
    _item("de-oasis-explained", "de-laws-licences", "OASIS erklärt", "/ratgeber-sicherheit/recht-lizenzen/oasis/"),
    _item("de-lugas-explained", "de-laws-licences", "LUGAS erklärt", "/ratgeber-sicherheit/recht-lizenzen/lugas/"),
    _item("de-check-casino-licence", "de-laws-licences", "Casino-Lizenz prüfen", "/ratgeber-sicherheit/recht-lizenzen/lizenz-pruefen/"),
    _item("de-play-safely", "de-guides-safety", "Sicher spielen", "/ratgeber-sicherheit/sicher-spielen/"),
    _item("de-identify-trusted-casinos", "de-play-safely", "Seriöse Casinos erkennen", "/ratgeber-sicherheit/sicher-spielen/serioese-casinos/"),
    _item("de-scams-blacklists", "de-play-safely", "Betrug und schwarze Listen", "/ratgeber-sicherheit/sicher-spielen/betrug-blacklists/"),
    _item("de-privacy-account-security", "de-play-safely", "Datenschutz und Kontosicherheit", "/ratgeber-sicherheit/sicher-spielen/datenschutz/"),
    _item("de-responsible-gambling", "de-guides-safety", "Verantwortungsvolles Spielen", "/ratgeber-sicherheit/verantwortungsvolles-spielen/"),
    _item("de-deposit-limits", "de-responsible-gambling", "Einzahlungslimits", "/ratgeber-sicherheit/verantwortungsvolles-spielen/einzahlungslimits/"),
    _item("de-self-exclusion", "de-responsible-gambling", "Selbstausschluss", "/ratgeber-sicherheit/verantwortungsvolles-spielen/selbstausschluss/"),
    _item("de-help-support-services", "de-responsible-gambling", "Hilfe und Beratungsstellen", "/ratgeber-sicherheit/verantwortungsvolles-spielen/hilfe/"),

    _item("de-news", None, "News", "/news/"),
    _item("de-casino-news", "de-news", "Casino News", "/news/casino/"),
    _item("de-new-casino-games-news", "de-news", "Neue Casinospiele", "/news/neue-casinospiele/"),
    _item("de-regulation-licences-news", "de-news", "Regulierung und Lizenzen", "/news/regulierung-lizenzen/"),
    _item("de-operators-industry", "de-news", "Anbieter und Branche", "/news/anbieter-branche/"),
    _item("de-bonus-news", "de-news", "Bonus News", "/news/bonus/"),

    _item("de-about-us", None, "Über Uns", "/ueber-uns/"),
    _item("de-how-we-review", "de-about-us", "Wie wir Casinos bewerten", "/ueber-uns/wie-wir-bewerten/"),
    _item("de-editorial-experts", "de-about-us", "Redaktion und Experten", "/ueber-uns/redaktion/"),
    _item("de-review-methodology", "de-about-us", "Bewertungsmethodik", "/ueber-uns/bewertungsmethodik/"),
    _item("de-affiliate-disclosure", "de-about-us", "Affiliate-Offenlegung", "/ueber-uns/affiliate-offenlegung/"),
    _item("de-contact", "de-about-us", "Kontakt", "/ueber-uns/kontakt/"),
]


DE_CASINO_REVIEW_HEADER_TEMPLATE = {
    "id": "de-casino-review-header-v1",
    "language": "de",
    "name": "DE Casino-Ratgeber — Header",
    "description": "Vollständige Header-Menüstruktur für eine deutschsprachige Casino-Vergleichsseite.",
    "max_depth": 3,
    "items": DE_CASINO_REVIEW_HEADER_ITEMS,
}


MENU_TEMPLATES = {DE_CASINO_REVIEW_HEADER_TEMPLATE["id"]: DE_CASINO_REVIEW_HEADER_TEMPLATE}
