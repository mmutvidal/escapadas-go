async function loadFlights() {
  const yearSpan = document.getElementById("year");
  if (yearSpan) {
    yearSpan.textContent = new Date().getFullYear();
  }

  const todayCard = document.getElementById("today-card");
  const recentGrid = document.getElementById("recent-grid");

  // 🔹 NUEVO: URL base de S3 + market
  const FLIGHTS_BASE_URL = "https://escapadasgo-public.s3.eu-north-1.amazonaws.com";
  const MARKET = "mad";  // en el futuro podrás usar "mad", "bcn", etc.
  const FLIGHTS_URL = `${FLIGHTS_BASE_URL}/${MARKET}/flights_of_the_day.json`;

  try {
    const res = await fetch(FLIGHTS_URL, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`No se pudo cargar ${FLIGHTS_URL} (status ${res.status})`);
    }

    const data = await res.json();
    const flights = data.flights || [];

    if (!flights.length) {
      todayCard.innerHTML = "<p>No hay escapadas disponibles por ahora.</p>";
      return;
    }

    const today = flights[0];
    const recent = flights.slice(1, 5); // hasta 4 anteriores

    renderToday(todayCard, today);
    renderRecent(recentGrid, recent);
  } catch (err) {
    console.error(err);
    todayCard.innerHTML = "<p>⚠️ Error cargando las escapadas. Inténtalo más tarde.</p>";
  }
}

function formatDateFriendly(raw) {
  if (!raw) return "";
  // Si viene en ISO largo, acortamos a la parte de fecha
  const onlyDate = raw.split("T")[0] || raw;
  const d = new Date(onlyDate);

  if (isNaN(d.getTime())) {
    // Si no se puede parsear, devolvemos al menos YYYY-MM-DD
    return onlyDate;
  }

  return d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatDateRange(startRaw, endRaw) {
  const start = formatDateFriendly(startRaw);
  const end = formatDateFriendly(endRaw);
  return `${start} – ${end}`;
}

function getDiscountPct(flight) {
  if (flight.discount_pct != null) {
    return flight.discount_pct;
  }

  if (flight.route_typical_price != null && flight.price_eur != null) {
    const habitual = Number(flight.route_typical_price);
    const price = Number(flight.price_eur);
    if (habitual > 0 && price > 0) {
      const disc = (1 - price / habitual) * 100;
      return Math.max(0, disc);
    }
  }

  return null;
}

function renderToday(container, flight) {
  container.classList.remove("loading");
  container.innerHTML = "";

  const price = flight.price_eur != null ? flight.price_eur.toFixed(2) : "N/D";
  const ppk =
    flight.price_per_km != null ? flight.price_per_km.toFixed(2) : null;

  const discount = getDiscountPct(flight);
  let rawScore = flight.score != null ? flight.score : null;

  // Pequeño bonus visual para "finde_perfecto"
  if (rawScore != null && flight.category_code === "finde_perfecto") {
    rawScore += 3.5;
  }

  // Mapeamos tu score a una escala "optimista" 7–10
  let rating10 = null;
  let starsText = null;
  if (rawScore != null) {
    const min = 5;
    const max = 15;

    let t = (rawScore - min) / (max - min);
    t = Math.max(0, Math.min(1, t));

    const scaled = 7 + t * 3;
    rating10 = scaled.toFixed(1);

    const stars = Math.max(4, Math.round(scaled / 2));
    const starFull = "★".repeat(stars);
    const starEmpty = "☆".repeat(5 - stars);
    starsText = `${starFull}${starEmpty}`;
  }

  const dates = formatDateRange(flight.start_date, flight.end_date);
  const title = `${flight.origin_iata} → ${flight.destination_iata}`;
  const subtitle = `${flight.origin_city} → ${flight.destination_city}`;
  const tag = flight.category_label || "Escapada";

  const card = document.createElement("div");
  card.className = "card";

  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-route">${title}</div>
        <div class="card-airline">${subtitle} · ${flight.airline || ""}</div>
      </div>
      <div class="card-tag">${tag}</div>
    </div>
    <div class="card-body">
      <p class="card-line"><strong>Fechas:</strong> ${dates}</p>
      <p class="card-line">
        <strong>Precio:</strong> ${price} € ida y vuelta
      </p>
      ${
        flight.route_typical_price != null
          ? `<p class="card-line" style="color:#94a3b8;font-size:0.85rem;">
               Precio habitual: ${flight.route_typical_price.toFixed(0)} €
             </p>`
          : ""
      }
      <div class="card-metrics">
        ${ppk ? `<span>💶 ${ppk} €/km</span>` : ""}
        ${rating10 ? `<span>⭐ ${rating10}/10</span>` : ""}
        ${
          discount != null
            ? `<span class="${discount >= 50 ? "metric-strong" : ""}">
                 ⬇️ ${discount.toFixed(0)}% dto
               </span>`
            : ""
        }
      </div>
      <div class="card-actions">
        ${
          flight.affiliate_url
            ? `<a class="btn" href="${flight.affiliate_url}" target="_blank" rel="nofollow">Ver vuelo</a>`
            : flight.booking_url
            ? `<a class="btn" href="${flight.booking_url}" target="_blank" rel="nofollow">Ver vuelo</a>`
            : ""
        }
        ${
          flight.reel_url
            ? `<a class="btn btn-secondary" href="${flight.reel_url}" target="_blank">Ver Reel en Instagram</a>`
            : ""
        }
      </div>
    </div>
  `;

  container.appendChild(card);
}

function renderRecent(container, flights) {
  container.innerHTML = "";

  if (!flights.length) {
    container.innerHTML =
      "<p style='color:#9ca3af;font-size:0.9rem;'>Todavía no hay escapadas anteriores.</p>";
    return;
  }

  flights.forEach((flight) => {
    const price =
      flight.price_eur != null ? flight.price_eur.toFixed(2) : "N/D";
    const dates = formatDateRange(flight.start_date, flight.end_date);
    const title = `${flight.origin_iata} → ${flight.destination_iata}`;
    const subtitle = `${flight.origin_city} → ${flight.destination_city}`;
    const tag = flight.category_label || "Escapada";

    const card = document.createElement("div");
    card.className = "card";

    card.innerHTML = `
      <div class="card-header">
        <div>
          <div class="card-route">${title}</div>
          <div class="card-airline">${subtitle}</div>
        </div>
        <div class="card-tag">${tag}</div>
      </div>
      <div class="card-body">
        <p class="card-line"><strong>Fechas:</strong> ${dates}</p>
        <p class="card-line"><strong>Precio:</strong> ${price} € ida y vuelta</p>
        <div class="card-actions">
          ${
            flight.affiliate_url
              ? `<a class="btn btn-secondary" href="${flight.affiliate_url}" target="_blank" rel="nofollow">Ver vuelo</a>`
              : flight.booking_url
              ? `<a class="btn btn-secondary" href="${flight.booking_url}" target="_blank" rel="nofollow">Ver vuelo</a>`
              : ""
          }
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}

document.addEventListener("DOMContentLoaded", loadFlights);
