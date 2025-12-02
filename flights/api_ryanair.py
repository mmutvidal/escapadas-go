# flights/api_ryanair.py

from typing import List
from pathlib import Path
import pandas as pd

from geopy.geocoders import Photon
from geopy.distance import geodesic
from ryanair import Ryanair
from urllib.parse import urlencode

from flights.base import Flight, FlightAPI



class RyanairAPI(FlightAPI):
    """
    Implementación de FlightAPI para Ryanair.

    - Usa la librería `ryanair` para obtener vuelos ida/vuelta.
    - Calcula distancia y price_per_km.
    - Genera un link navegable a Ryanair con las fechas y ruta correctas.
    """

    DISTANCE_FILE = Path("distance_mapping_pmi.csv")

    def __init__(self, origin: str = "PMI", currency: str = "EUR"):
        self.origin = origin
        self.currency = currency
        self.api = Ryanair(currency=currency)
        self.geolocator = Photon(user_agent="escapadas_mallorca_distance")

        # cache de distancias
        if self.DISTANCE_FILE.exists():
            self.distance_mapping = pd.read_csv(self.DISTANCE_FILE)
        else:
            self.distance_mapping = pd.DataFrame(columns=["DestinationFull", "DistanceKm"])

        self.new_destinations = False

    # -------------------------------
    # Distancias
    # -------------------------------

    def get_distance(self, origin_full: str, destination_full: str) -> float:
        """
        Devuelve distancia en km entre dos ciudades, usando cache + geopy.
        Soporta CSV antiguo (Destination, Distance) y nuevo (DestinationFull, DistanceKm).
        """
        df = self.distance_mapping
    
        # detectar nombres de columnas según el fichero
        if "DestinationFull" in df.columns:
            col_dest = "DestinationFull"
            col_dist = "DistanceKm"
        elif "Destination" in df.columns:
            col_dest = "Destination"
            col_dist = "Distance"
        else:
            col_dest = "DestinationFull"
            col_dist = "DistanceKm"
    
        row = df[df[col_dest] == destination_full]
        if len(row) > 0:
            return float(row[col_dist].values[0])
    
        # calcular con geopy si no está en cache
        loc1 = self.geolocator.geocode(origin_full)
        loc2 = self.geolocator.geocode(destination_full)
    
        if not loc1 or not loc2:
            return 0.0
    
        from geopy.distance import geodesic
        distance = geodesic(
            (loc1.latitude, loc1.longitude),
            (loc2.latitude, loc2.longitude),
        ).km
    
        # añadimos SIEMPRE con columnas nuevas
        self.distance_mapping = pd.concat(
            [
                self.distance_mapping,
                pd.DataFrame(
                    [
                        {
                            "DestinationFull": destination_full,
                            "DistanceKm": distance,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        self.new_destinations = True
        return distance

    def save_distance_cache(self):
        if self.new_destinations:
            self.DISTANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.distance_mapping.to_csv(self.DISTANCE_FILE, index=False)
            self.new_destinations = False

    # -------------------------------
    # Link a Ryanair
    # -------------------------------

    @staticmethod
    def build_ryanair_link(
        origin_iata: str,
        destination_iata: str,
        depart_date: str,   # YYYY-MM-DD
        return_date: str,   # YYYY-MM-DD
        adults: int = 1,
        teens: int = 0,
        children: int = 0,
        infants: int = 0,
    ) -> str:
        """
        Construye un link directo a la selección de vuelos de Ryanair.
        depart_date / return_date deben ser solo fecha (YYYY-MM-DD).
        """

        base_url = "https://www.ryanair.com/es/es/trip/flights/select"

        params = {
            "adults": adults,
            "teens": teens,
            "children": children,
            "infants": infants,
            "dateOut": depart_date,
            "dateIn": return_date,
            "isConnectedFlight": "false",
            "discount": 0,
            "promoCode": "",
            "isReturn": "true",
            "originIata": origin_iata,
            "destinationIata": destination_iata,
            "tpAdults": adults,
            "tpTeens": teens,
            "tpChildren": children,
            "tpInfants": infants,
            "tpStartDate": depart_date,
            "tpEndDate": return_date,
            "tpDiscount": 0,
            "tpPromoCode": "",
            "tpOriginIata": origin_iata,
            "tpDestinationIata": destination_iata,
        }

        return f"{base_url}?{urlencode(params)}"

    # -------------------------------
    # Búsqueda principal
    # -------------------------------

    def search(self, depart_date, return_date) -> List[Flight]:
        """
        depart_date y return_date vienen de tu agregador como 'YYYY-MM-DD' (str).
        Se pasan a Ryanair como rango de un solo día ida/vuelta.

        Devuelve una lista de Flight normalizados.
        """

        flights: List[Flight] = []

        depart_str = str(depart_date)
        return_str = str(return_date)

        try:
            trips = self.api.get_cheapest_return_flights(
                self.origin,
                depart_str, depart_str,   # ida en ese día
                return_str, return_str    # vuelta en ese día
            )
        except Exception as e:
            print(f"❌ Error RyanairAPI para {depart_str} - {return_str}: {e}")
            return []

        for tr in trips:
            outbound = tr.outbound
            inbound = tr.inbound
            price = tr.totalPrice

            # nombres completos de ciudad
            origin_full = outbound.originFull
            destination_full = outbound.destinationFull

            # códigos IATA
            origin_iata = outbound.origin
            destination_iata = outbound.destination

            # distancia + price_per_km
            distance = self.get_distance(origin_full, destination_full)
            price_per_km = None
            if distance and distance > 0:
                price_per_km = price / distance

            # fechas (el wrapper suele devolver datetime)
            # usamos .date() para el link y str() completo para Flight
            try:
                out_dt = outbound.departureTime
                in_dt = inbound.departureTime
                out_date_str = str(out_dt.date())
                in_date_str = str(in_dt.date())
                start_iso = str(out_dt)
                end_iso = str(in_dt)
            except Exception:
                # fallback por si fueran strings ya
                start_iso = str(outbound.departureTime)
                end_iso = str(inbound.departureTime)
                out_date_str = start_iso[:10]
                in_date_str = end_iso[:10]

            # link a Ryanair
            link = self.build_ryanair_link(
                origin_iata=origin_iata,
                destination_iata=destination_iata,
                depart_date=out_date_str,
                return_date=in_date_str,
            )

            f = Flight(
                origin=origin_iata,
                destination=destination_iata,
                price=price,
                start_date=start_iso,
                end_date=end_iso,
                airline="Ryanair",
                link=link,
                distance_km=distance if distance else None,
                price_per_km=price_per_km,
            )

            flights.append(f)

        # guardamos cache de distancias si hay novedades
        self.save_distance_cache()
        return flights
