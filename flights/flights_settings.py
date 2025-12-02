PRIORITY_DESTINATIONS = {
    "BLQ": 30,   # Bologna
    "MXP": 25,
    "BGY": 20,
    "FCO": 20,
}

PREFERRED_AIRLINES = {
    "Ryanair": 15,
    "Vueling": 10,
}



# DESTINATION_TAGS = {
#     "PAR": ["romantica", "cultural", "gastronomica"],
#     "ORY": ["romantica", "cultural"],
#     "CDG": ["romantica", "cultural"],
#     "VCE": ["romantica", "cultural"],
#     "VRN": ["romantica"],
#     "FCO": ["cultural", "gastronomica"],
#     "CIA": ["cultural"],
#     "BLQ": ["cultural", "gastronomica"],
#     "LIS": ["cultural", "gastronomica"],
#     "OPO": ["cultural", "gastronomica"],
#     "SEV": ["cultural", "gastronomica"],
#     "SVQ": ["cultural", "gastronomica"],
#     "BCN": ["cultural", "gastronomica"],
#     "MAD": ["cultural"],
#     "BUD": ["romantica", "cultural"],
# }

DESTINATION_TAGS = {
    # 🌍 Norte / Centro Europa
    "CPH": ["romantica", "cultural", "gastronomica"],      # Copenhague
    "ARN": ["romantica", "cultural", "gastronomica"],      # Estocolmo
    "GOT": ["cultural", "gastronomica"],                   # Gotemburgo
    "EDI": ["romantica", "cultural"],                      # Edimburgo
    "ATH": ["cultural", "gastronomica"],                   # Atenas

    "DUB": ["cultural", "gastronomica"],                   # Dublín
    "HAM": ["cultural"],                                   # Hamburgo
    "BER": ["cultural", "gastronomica"],                   # Berlín
    "BUD": ["romantica", "cultural"],                      # Budapest
    "DRS": ["cultural"],                                   # Dresde
    "LEJ": ["cultural"],                                   # Leipzig
    "PRG": ["romantica", "cultural", "gastronomica"],      # Praga
    "VIE": ["romantica", "cultural", "gastronomica"],      # Viena
    "AMS": ["romantica", "cultural", "gastronomica"],      # Ámsterdam

    "CGN": ["cultural", "gastronomica"],                   # Colonia
    "ZAG": ["cultural"],                                   # Zagreb
    "NUE": ["cultural", "gastronomica"],                   # Núremberg
    "BRU": ["cultural", "gastronomica"],                   # Bruselas
    "FRA": ["cultural"],                                   # Frankfurt
    "WAW": ["cultural", "gastronomica"],                   # Varsovia
    "MUC": ["cultural", "gastronomica"],                   # Múnich

    "ZRH": ["romantica", "cultural", "gastronomica"],      # Zúrich
    "BSL": ["cultural", "gastronomica"],                   # Basilea

    # ✈️ Aeropuertos “low cost” que sirven a ciudades potentes
    "LTN": ["cultural", "gastronomica"],                   # Londres (Luton)
    "STN": ["cultural", "gastronomica"],                   # Londres (Stansted)
    "LGW": ["cultural", "gastronomica"],                   # Londres (Gatwick)

    # RAK – Marruecos
    "RAK": ["romantica", "cultural", "gastronomica"],      # Marrakech

    # 🇵🇹 Portugal
    "LIS": ["cultural", "gastronomica"],                   # Lisboa
    "OPO": ["cultural", "gastronomica"],                   # Oporto

    # 🇮🇹 Italia
    "NAP": ["cultural", "gastronomica"],                   # Nápoles
    "BLQ": ["cultural", "gastronomica"],                   # Bolonia
    "BGY": ["romantica", "cultural", "gastronomica"],      # Bérgamo / área Milán
    "FCO": ["cultural", "gastronomica"],                   # Roma Fiumicino
    "MXP": ["romantica", "cultural", "gastronomica"],      # Milán Malpensa
    "PSA": ["cultural", "gastronomica"],                   # Pisa / Toscana
    "TSF": ["romantica", "cultural", "gastronomica"],      # Treviso (área Venecia)

    # 🇫🇷 Francia / Suiza francófona
    "ORY": ["romantica", "cultural"],                      # París Orly
    "GVA": ["romantica", "cultural", "gastronomica"],      # Ginebra
    "LYS": ["cultural", "gastronomica"],                   # Lyon
    "MRS": ["cultural", "gastronomica"],                   # Marsella
    "TLS": ["cultural", "gastronomica"],                   # Toulouse

    # 🇪🇸 España (península)
    "SCQ": ["cultural", "gastronomica"],                   # Santiago de Compostela
    "SVQ": ["cultural", "gastronomica"],                   # Sevilla
    "AGP": ["gastronomica", "cultural"],                   # Málaga
    "BIO": ["cultural", "gastronomica"],                   # Bilbao
    "GRX": ["romantica", "cultural", "gastronomica"],      # Granada
    "VIT": ["cultural", "gastronomica"],                   # Vitoria
    "MAD": ["cultural", "gastronomica"],                   # Madrid
    "ZAZ": ["cultural", "gastronomica"],                   # Zaragoza
    "ALC": ["gastronomica"],                               # Alicante
    "VLC": ["cultural", "gastronomica"],                   # Valencia
    "XRY": ["cultural", "gastronomica"],                   # Jerez de la Frontera
    "OVD": ["gastronomica"],                               # Asturias (Oviedo/Gijón)
    "SDR": ["gastronomica"],                               # Santander

    # 🇪🇸 Islas / costa con enfoque más foodie
    "LPA": ["gastronomica"],                               # Las Palmas (Canarias)
}



DESTINATION_CATEGORY_LABELS = {
    "romantica":    "❤️ Escapada Romántica",
    "cultural":     "🏛 Escapada Cultural",
    "gastronomica": "🍝 Escapada Gastronómica",
}
