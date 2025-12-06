# content/destinations.py

# content/destinations.py
from __future__ import annotations
from typing import Dict, Any, Optional


# ---- Base curada de destinos (los que tú has definido a mano) ----
DESTINATIONS: Dict[str, Dict[str, Any]] = {
    "PMI": {"city": "Mallorca", "country": "España"},
    "AGP": {"city": "Málaga", "country": "España"},
    "ALC": {"city": "Alicante", "country": "España"},
    "AMS": {"city": "Ámsterdam", "country": "Países Bajos"},
    "ATH": {"city": "Atenas", "country": "Grecia"},
    "BGY": {"city": "Milán", "country": "Italia"},
    "BIO": {"city": "Bilbao", "country": "España"},
    "BLQ": {"city": "Bolonia", "country": "Italia"},
    "BOH": {"city": "Bournemouth", "country": "Reino Unido"},
    "BRE": {"city": "Bremen", "country": "Alemania"},
    "BRU": {"city": "Bruselas", "country": "Bélgica"},
    "BRS": {"city": "Bristol", "country": "Reino Unido"},
    "BSL": {"city": "Basilea", "country": "Suiza"},
    "BUD": {"city": "Budapest", "country": "Hungría"},
    "BCN": {"city": "Barcelona", "country": "España"},
    "BHX": {"city": "Birmingham", "country": "Reino Unido"},
    "CGN": {"city": "Colonia", "country": "Alemania"},
    "CPH": {"city": "Copenhague", "country": "Dinamarca"},
    "CRL": {"city": "Bruselas", "country": "Bélgica"},
    "DRS": {"city": "Dresde", "country": "Alemania"},
    "DUB": {"city": "Dublín", "country": "Irlanda"},
    "DUS": {"city": "Düsseldorf", "country": "Alemania"},
    "DTM": {"city": "Dortmund", "country": "Alemania"},
    "EDI": {"city": "Edimburgo", "country": "Reino Unido"},
    "EIN": {"city": "Eindhoven", "country": "Países Bajos"},
    "EMA": {"city": "East Midlands", "country": "Reino Unido"},
    "EXT": {"city": "Exeter", "country": "Reino Unido"},
    "FCO": {"city": "Roma", "country": "Italia"},
    "FDH": {"city": "Friedrichshafen", "country": "Alemania"},
    "FMM": {"city": "Múnich", "country": "Alemania"},
    "FMO": {"city": "Münster Osnabrück", "country": "Alemania"},
    "FRA": {"city": "Fráncfort", "country": "Alemania"},
    "FKB": {"city": "Karlsruhe", "country": "Alemania"},
    "GOT": {"city": "Gotemburgo", "country": "Suecia"},
    "GVA": {"city": "Ginebra", "country": "Suiza"},
    "GRX": {"city": "Granada", "country": "España"},
    "HAM": {"city": "Hamburgo", "country": "Alemania"},
    "HHN": {"city": "Fráncfort", "country": "Alemania"},
    "IBZ": {"city": "Ibiza", "country": "España"},
    "KLU": {"city": "Klagenfurt", "country": "Austria"},
    "KRK": {"city": "Cracovia", "country": "Polonia"},
    "KUN": {"city": "Kaunas", "country": "Lituania"},
    "LEJ": {"city": "Leipzig", "country": "Alemania"},
    "LGW": {"city": "Londres", "country": "Reino Unido"},
    "LIS": {"city": "Lisboa", "country": "Portugal"},
    "LBA": {"city": "Leeds Bradford", "country": "Reino Unido"},
    "LBC": {"city": "Lübeck", "country": "Alemania"},
    "LTN": {"city": "Londres", "country": "Reino Unido"},
    "LPA": {"city": "Gran Canaria", "country": "España"},
    "LPL": {"city": "Liverpool", "country": "Reino Unido"},
    "LUX": {"city": "Luxemburgo", "country": "Luxemburgo"},
    "LYS": {"city": "Lyon", "country": "Francia"},
    "MAD": {"city": "Madrid", "country": "España"},
    "MAH": {"city": "Menorca", "country": "España"},
    "MAN": {"city": "Mánchester", "country": "Reino Unido"},
    "MRS": {"city": "Marsella", "country": "Francia"},
    "MUC": {"city": "Múnich", "country": "Alemania"},
    "MXP": {"city": "Milán", "country": "Italia"},
    "NAP": {"city": "Nápoles", "country": "Italia"},
    "NCL": {"city": "Newcastle", "country": "Reino Unido"},
    "NOC": {"city": "Knock", "country": "Irlanda"},
    "NRN": {"city": "Düsseldorf", "country": "Alemania"},
    "NUE": {"city": "Núremberg", "country": "Alemania"},
    "OPO": {"city": "Oporto", "country": "Portugal"},
    "ORY": {"city": "París Orly", "country": "Francia"},
    "OVD": {"city": "Asturias", "country": "España"},
    "PAD": {"city": "Paderborn", "country": "Alemania"},
    "PED": {"city": "Pardubice", "country": "República Checa"},
    "PIK": {"city": "Glasgow", "country": "Reino Unido"},
    "POZ": {"city": "Poznań", "country": "Polonia"},
    "PRG": {"city": "Praga", "country": "República Checa"},
    "RAK": {"city": "Marrakech", "country": "Marruecos"},
    "SCQ": {"city": "Santiago", "country": "España"},
    "SDR": {"city": "Santander", "country": "España"},
    "SOF": {"city": "Sofía", "country": "Bulgaria"},
    "STN": {"city": "Londres", "country": "Reino Unido"},
    "STR": {"city": "Stuttgart", "country": "Alemania"},
    "SVQ": {"city": "Sevilla", "country": "España"},
    "TFN": {"city": "Tenerife Norte", "country": "España"},
    "TLS": {"city": "Toulouse", "country": "Francia"},
    "TSF": {"city": "Venecia", "country": "Italia"},
    "VIE": {"city": "Viena", "country": "Austria"},
    "VIT": {"city": "Vitoria", "country": "España"},
    "VLC": {"city": "Valencia", "country": "España"},
    "WAW": {"city": "Varsovia", "country": "Polonia"},
    "WMI": {"city": "Varsovia", "country": "Polonia"},
    "WRO": {"city": "Wrocław", "country": "Polonia"},
    "XRY": {"city": "Jerez de la Frontera", "country": "España"},
    "ZAG": {"city": "Zagreb", "country": "Croacia"},
    "ZAZ": {"city": "Zaragoza", "country": "España"},
    "ZRH": {"city": "Zúrich", "country": "Suiza"},
}


COUNTRY_FLAGS = {
    "España": "🇪🇸",
    "Reino Unido": "🇬🇧",
    "Francia": "🇫🇷",
    "Italia": "🇮🇹",
    "Portugal": "🇵🇹",
    "Alemania": "🇩🇪",
    "Austria": "🇦🇹",
    "Suiza": "🇨🇭",
    "Países Bajos": "🇳🇱",
    "Bélgica": "🇧🇪",
    "Dinamarca": "🇩🇰",
    "Suecia": "🇸🇪",
    "Noruega": "🇳🇴",
    "Irlanda": "🇮🇪",
    "Chequia": "🇨🇿",
    "Polonia": "🇵🇱",
    "Hungría": "🇭🇺",
    "Croacia": "🇭🇷",
    "Austria": "🇦🇹",
    "Marruecos": "🇲🇦",
    "Luxemburgo": "🇱🇺",
    "Lituania": "🇱🇹",
    "Eslovenia": "🇸🇮",
    "Eslovaquia": "🇸🇰",
    "Finlandia": "🇫🇮",
}


def get_city(iata: str, default: str | None = None, include_flag=True) -> str:
    iata = (iata or "").upper()
    data = DESTINATIONS.get(iata)

    if not data:
        return default or f"{iata}"

    city = data["city"]
    country = data.get("country")
    flag = COUNTRY_FLAGS.get(country, "")
    
    return f"{flag} {city}" if include_flag else city