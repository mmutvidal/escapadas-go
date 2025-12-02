# flights/base.py
from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Flight:
    origin: str
    destination: str
    price: float
    start_date: str   # salida
    end_date: str     # vuelta
    airline: str
    link: str = ""    # opcional
    distance_km: Optional[float] = None
    price_per_km: Optional[float] = None

class FlightAPI(ABC):
    @abstractmethod
    def search(self, depart_date, return_date) -> List[Flight]:
        """
        Debe devolver una lista de vuelos para un rango ida/vuelta.
        Cada implementación puede ignorar return_date si no le hace falta,
        pero el agregador siempre llamará con las mismas fechas para todas.
        """
        pass
