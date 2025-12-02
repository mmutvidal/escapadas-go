# flights/api_kiwi.py

import requests
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode, quote

from flights.base import Flight, FlightAPI
# from config.settings import KIWI_API_KEY

from config.settings import KIWI_API_KEY,KIWI_API_BASE 


class KiwiAPI(FlightAPI):
    """
    Implementación de FlightAPI usando Tequila (Kiwi).
    Usa el patrón search(depart_date, return_date) para encajar
    con tu agregador de combinaciones de días.
    """

    def __init__(self, origin: str = "PMI", currency: str = "EUR"):
        if not KIWI_API_KEY:
            raise ValueError("KIWI_API_KEY no está configurada en .env / settings.")

        self.origin = origin
        self.currency = currency
        self.headers = {
            "apikey": KIWI_API_KEY,
            "Content-Type": "application/json",
        }

    def _build_search_params(self, depart_date: str, return_date: str) -> dict:
        """
        depart_date / return_date vienen como 'YYYY-MM-DD' (ISO).
        Kiwi espera dd/mm/YYYY.
        También usamos la diferencia de días como nights_in_dst_from/to.
        """

        d_out = datetime.fromisoformat(depart_date)
        d_ret = datetime.fromisoformat(return_date)

        nights = (d_ret.date() - d_out.date()).days
        if nights <= 0:
            nights = 1  # por si acaso

        date_from = d_out.strftime("%d/%m/%Y")
        date_to = d_out.strftime("%d/%m/%Y")  # misma fecha de salida (rango de un día)

        params = {
            "fly_from": self.origin,
            "fly_to": "anywhere",
            "date_from": date_from,
            "date_to": date_to,
            "curr": self.currency,
            "flight_type": "round",
            "one_for_city": 1,
            "sort": "price",
            "max_stopovers": 0,
            "limit": 50,
            "nights_in_dst_from": nights,
            "nights_in_dst_to": nights,
            "adults": 1,
        }
        return params

    def search(self, depart_date: str, return_date: str) -> List[Flight]:
        """
        depart_date y return_date: 'YYYY-MM-DD'
        Solo aceptamos viajes tipo PMI -> X -> PMI
        (misma ciudad X a la ida y a la vuelta).
        """
    
        params = self._build_search_params(depart_date, return_date)
    
        try:
            r = requests.get(
                f"{KIWI_API_BASE}/v2/search",
                params=params,
                headers=self.headers,
                timeout=20,
            )
            r.raise_for_status()
        except Exception as e:
            print(f"❌ Error en KiwiAPI.search({depart_date} -> {return_date}): {e}")
            return []
    
        data = r.json().get("data", [])
        flights: List[Flight] = []
    
        for item in data:
            price = float(item.get("price", 0.0))
            route = item.get("route", [])
            booking_token = item.get("booking_token")
    
            if not route or price <= 0:
                continue
    
            first_leg = route[0]
            last_leg = route[-1]
    
            # --- 1) Filtrar solo PMI -> X -> PMI (misma ciudad X) ---
    
            origin_airport = first_leg.get("flyFrom")          # ej. PMI
            outbound_city_to = first_leg.get("cityTo")         # ej. Barcelona
            inbound_city_from = last_leg.get("cityFrom")       # ej. Santander o Barcelona
            final_destination_airport = last_leg.get("flyTo")  # debe ser PMI si es ida/vuelta
    
            # queremos:
            #  - que el origen sea nuestro PMI
            #  - que la vuelta termine en PMI
            #  - que la ciudad de ida y la ciudad de vuelta sean la misma
            if origin_airport != self.origin:
                continue
    
            if final_destination_airport != self.origin:
                # no vuelve a PMI, descartamos
                continue
    
            if outbound_city_to != inbound_city_from:
                # open-jaw: ej. ida a Barcelona y vuelta desde Santander → descartamos
                continue
    
            # --- 2) Construir el Flight correcto ---
    
            origin = self.origin                     # PMI
            destination_airport = first_leg.get("flyTo")       # ej. BCN
            destination_city_code = first_leg.get("cityCodeTo")  # ej. BCN también normalmente
    
            departure_time = first_leg.get("utc_departure") or first_leg.get("local_departure")
            return_time = last_leg.get("utc_arrival") or last_leg.get("local_arrival")
    
            airline = first_leg.get("airline", "Kiwi")
    
            if not (destination_airport and departure_time and return_time):
                continue
   
            # distancia (km)
            distance_km = item.get("distance")
            if distance_km is not None:
                try:
                    distance_km = float(distance_km)
                except Exception:
                    distance_km = None
            
            price_per_km = None
            if distance_km and distance_km > 0:
                price_per_km = price / distance_km

            f = Flight(
                origin=origin,
                destination=destination_airport,  # IATA del aeropuerto destino (BCN)
                price=price,
                start_date=departure_time,
                end_date=return_time,
                airline=airline,
                link=item.get("deep_link", ""),
                distance_km=distance_km,
                price_per_km=price_per_km,
            )
            
            if booking_token:
                f.booking_token = booking_token
    
            flights.append(f)
    
        return flights


# def build_kiwi_deep_link(origin_iata, dest_iata, start_date, end_date):
#     # fechas en 'YYYY-MM-DD'
#     base = "https://www.kiwi.com/deep"
#     params = {
#         "from": origin_iata,
#         "to": dest_iata,
#         "departure": start_date,
#     }
#     if end_date:
#         params["return"] = end_date

#     from urllib.parse import urlencode
#     return f"{base}?{urlencode(params)}"



# def build_kiwi_affiliate_link(
#     origin_iata: str,
#     dest_iata: str,
#     start_date: str,
#     end_date: Optional[str] = None,
#     marker: str = TRAVELPAYOUTS_MARKER,
#     sub_id: Optional[str] = None,
# ) -> str:
#     """
#     Construye:
#       1) Deep link de Kiwi con /deep?from=...&to=...&departure=...&return=...
#       2) Lo envuelve en un enlace de Travelpayouts con custom_url (URL-encoded).

#     Devuelve el enlace final que deberías usar en tu web / JSON.
#     """
#     # 1) Deep link "limpio" de Kiwi
#     deep_link = build_kiwi_deep_link(origin_iata, dest_iata, start_date, end_date)

#     # 2) URL encode *solo* el deep_link
#     encoded_deep = quote(deep_link, safe="")

#     # 3) shmarker: ID o ID.SubID
#     sh = marker if not sub_id else f"{marker}.{sub_id}"

#     # 4) Params básicos del click
#     params = {
#         "shmarker": sh,
#         "promo_id": TRAVELPAYOUTS_KIWI_PROMO_ID,
#         "source_type": "customlink",
#         "type": "click",
#     }
#     query = urlencode(params)

#     # 5) OJO: custom_url lo añadimos a mano, para no volver a encodear los %
#     return f"{TRAVELPAYOUTS_BASE}?{query}&custom_url={encoded_deep}"



# Opcional: wrapper para verify_live_price, si quieres reutilizar tu lógica
def verify_live_price(
    booking_token: str,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    currency: str = "EUR",
    locale: str = "es",
    market: str = "es",
) -> dict:
    headers = {
        "apikey": KIWI_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "booking_token": booking_token,
        "adults": adults,
        "children": children,
        "infants": infants,
        "curr": currency,
        "locale": locale,
        "partner_market": market,
        "v": 3,
        "pnum": adults + children + infants,
        "bnum": 0,
    }

    r = requests.post(f"{KIWI_API_BASE}/v2/booking/check", headers=headers, json=payload, timeout=30)

    if r.status_code == 200:
        data = r.json()
        return {
            "ok": True,
            "is_valid": not data.get("flights_invalid", False),
            "current_price": data.get("price"),
            "price_change": data.get("price_change"),
            "raw": data,
        }
    elif r.status_code == 404:
        return {"ok": False, "reason": "404_NOT_FOUND",
                "hint": "Token caducado o booking API no habilitada. Repite búsqueda o revisa permisos."}
    elif r.status_code == 403:
        return {"ok": False, "reason": "403_FORBIDDEN",
                "hint": "La key no tiene permisos para booking/check."}
    elif r.status_code == 400:
        return {"ok": False, "reason": "400_BAD_REQUEST",
                "hint": f"Parámetros inválidos: {r.text[:200]}"}
    else:
        return {"ok": False, "reason": f"{r.status_code}", "hint": r.text[:300]}
