"""Conservative brand detection from cached project identity; no network calls."""
import re
import unicodedata
from collections import Counter

GENERAL = "Общие ключи"
# Explicit spelling variants, not generic casino/betting search terms.
BRANDS = {
    "1win": ["1win", "1 win"], "1xBet": ["1xbet", "1x bet"],
    "Mostbet": ["mostbet", "most bet", "мостбет"], "Pin-Up": ["pinup", "pin-up", "pin up", "пин ап", "пинап"],
    "BetOnRed": ["betonred", "bet on red", "bet-on-red"],
    "Betwinner": ["betwinner"], "Melbet": ["melbet"], "Parimatch": ["parimatch", "pari match"],
    "22Bet": ["22bet"], "1Go": ["1go"], "Vavada": ["vavada"], "Gama": ["gama casino"],
    "R7": ["r7 casino"], "Kent": ["kent casino"], "Kometa": ["kometa casino"],
    "Daddy": ["daddy casino"], "CatCasino": ["catcasino", "cat casino"],
    "SpinBetter": ["spinbetter"], "Nine Casino": ["nine casino", "ninecasino"],
    "Mr Bet": ["mr bet", "mrbet"], "Betway": ["betway"], "Bet365": ["bet365"],
    "Bwin": ["bwin"], "888 Casino": ["888casino", "888 casino"],
    "888sport": ["888sport"], "Stake": ["stake"], "BC.Game": ["bc.game", "bc game"],
    "Betano": ["betano"], "Betfair": ["betfair"], "Unibet": ["unibet"],
    "LeoVegas": ["leovegas", "leo vegas"], "Ice Casino": ["ice casino", "icecasino"],
    "Icebet": ["icebet"], "Verde Casino": ["verde casino"], "Vulkan Vegas": ["vulkan vegas"],
    "Vulkan": ["vulkan casino", "vulcan casino"], "Slottica": ["slottica"],
    "Slots7": ["slots7"], "Spinanga": ["spinanga"], "WinWin": ["winwin casino"],
    "Winz.io": ["winz.io"], "King Billy": ["king billy"], "Fairspin": ["fairspin"],
    "Rabona": ["rabona"], "Casinia": ["casinia"], "Sultan": ["sultan casino"],
    "Dafabet": ["dafabet"], "4rabet": ["4rabet"], "Megapari": ["megapari"],
    "Linebet": ["linebet"], "BetAndYou": ["betandyou"], "Bettilt": ["bettilt"],
    "Leon": ["leonbet", "leon casino"], "JoyCasino": ["joycasino", "joy casino"],
    "PlayFortuna": ["playfortuna", "play fortuna"], "Pokerdom": ["pokerdom"],
    "Casino-X": ["casino-x", "casino x"], "Booi": ["booi"], "Fresh Casino": ["fresh casino"],
    "Sol Casino": ["sol casino"], "Monro": ["monro casino"], "Banda": ["banda casino"],
    "Dragon Money": ["dragon money"], "BetFury": ["betfury"], "FortuneJack": ["fortunejack"],
    "RocketPlay": ["rocketplay"], "National Casino": ["national casino"],
    "Bizzo": ["bizzo"], "Woo Casino": ["woo casino"], "7Bit": ["7bit"],
    "BitStarz": ["bitstarz"], "Wild Tokyo": ["wild tokyo"], "Cashed": ["cashed casino"],
    "Lemon Casino": ["lemon casino"], "Vegas Hero": ["vegas hero"],
    "Vox": ["vox casino"], "Spin Casino": ["spin casino"], "Spin Samurai": ["spin samurai"],
}

def normalized(value):
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value or "").casefold()).strip()

def detect_brand(site):
    title = " " + normalized(site.homepage_title) + " "
    matches = {brand for brand, aliases in BRANDS.items()
               if any(" " + normalized(alias) + " " in title for alias in aliases)}
    # Multiple brand reviews or comparisons are generic pages.
    if len(matches) == 1:
        return next(iter(matches))
    if matches:
        return GENERAL
    # Unlisted brands need two independent cached identity signals:
    # a leading title name and the same name at the start of a project/Main host.
    match = re.match(r"^([\w.-]+(?: [\w.-]+){0,2}?)\s+(?:casino|казино|sportsbook|betting)\b", site.homepage_title or "", re.I)
    if match:
        candidate = match.group(1).strip(" .-")
        generic = {"best", "top", "online", "new", "free", "real", "money", "live", "mobile",
                   "bonus", "bonuses", "casino", "casinos", "sports", "sport", "betting",
                   "official", "legal", "trusted", "safe", "danmark", "danish", "german",
                   "germany", "canada", "canadian", "australia", "australian", "india",
                   "indian", "uk", "usa", "czech", "polish", "swiss", "french", "finnish",
                   "swedish", "irish", "norsk", "norske", "beste", "mejores", "лучшие",
                   "meilleur", "meilleurs", "meilleures", "nye", "nyt", "nouveau",
                   "nouveaux", "migliori", "bedste", "bästa", "najlepsze", "nejlepší",
                   "crypto", "bitcoin", "no", "deposit", "deposits", "plinko", "aviator"}
        key = re.sub(r"[^\w]", "", candidate.casefold())
        from urllib.parse import urlsplit
        hosts = [urlsplit("https://" + (v or "").removeprefix("https://").removeprefix("http://")).hostname or ""
                 for v in [getattr(site, "name", ""), getattr(site, "cache_canon", "")]]
        if len(key) >= 3 and not (set(normalized(candidate).split()) & generic) and any(
            re.sub(r"[^\w]", "", host.removeprefix("www.").split(".")[0].casefold()).startswith(key) for host in hosts
        ):
            return candidate
    return GENERAL

def update_detected_brand(site):
    if site.brand_source != "manual":
        site.brand = detect_brand(site)
        site.brand_source = "detected" if site.brand != GENERAL else "generic"

def backfill(db):
    from sqlalchemy import select
    from app.models import Site
    sites = db.scalars(select(Site)).all()
    for site in sites:
        update_detected_brand(site)
    db.commit()
    counts = Counter(site.brand for site in sites)
    return {"total": len(sites), "defined": len(sites) - counts[GENERAL],
            "general": counts[GENERAL], "brands": dict(counts.most_common())}
