async function loadFlights() {
  const yearSpan = document.getElementById("year");
  if (yearSpan) {
    yearSpan.textContent = new Date().getFullYear();
  }

  const todayCard = document.getElementById("today-card");
  const recentGrid = document.getElementById("recent-grid");

  // Detectamos el mercado desde el body (ej. "pmi")
  const body = document.body;
  const market = (body && body.dataset.market) ? body.dataset.market : "pmi";

  // URL del JSON en S3 (bucket público)
  const DATA_URL = `https://escapadasgo-public.s3.eu-west-1.amazonaws.com/${market}/flights_of_the_day.json`;

  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("No se pudo cargar flights_of_the_day.json");

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

function renderToday(container, flight) {
  container.classList.remove("loading");
  container.innerHTML = "";

  const price = flight.price_eur != null ? flight.price_eur.toFixed(2) : "N/D";
  const ppk =
    flight.price_per_km != null ? flight.price_per_km.toFixed(2) : null;

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

  const dates = `${flight.start_date} – ${flight.end_date}`;
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
      <div class="card-metrics">
        ${ppk ? `<span>💶 ${ppk} €/km</span>` : ""}
        ${rating10 ? `<span>⭐ ${rating10}/10</span>` : ""}
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
    const dates = `${flight.start_date} – ${flight.end_date}`;
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
