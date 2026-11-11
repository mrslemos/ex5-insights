// EX5 Insights cards, loaded on every page by the integration.
//
//   type: custom:ex5-car-card        The Geely Connect car cards (full card on top of the top view, as one piece),
//                                    with this car's entity prefix, picture and body color filled in.
//   type: custom:ex5-map-card        Where the car is (map of the Geely Connect location, last 24 h).
//   type: custom:ex5-timeline-card   The exact path of the trips of any day, colored by speed.
//
// The cards read the car from sensor.ex5_battery (attributes geely_prefix, tracker, car_image, paint). With more
// than one car, set `entity:` to that car's battery sensor (and `entry:` on the timeline card).
(() => {
  const VERSION = "0.2.0";
  const T = {
    en: {
      noGeely: "The Geely Connect cards were not found. Is Geely Connect installed and up to date?",
      noCar: "EX5 Insights is not set up (sensor.ex5_battery not found).",
      prevDay: "Previous day with trips", nextDay: "Next day with trips", noTrips: "No trips on this day.",
      noSpeed: "no speed", parked: "parked", mapLink: "map", avg: "avg", max: "max", points: "points",
      days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
      label: (dw, d, m, y) => `${dw}, ${m} ${d}, ${y}`, upTo: "up to",
      timelineName: "EX5 timeline", timelineDesc: "Path of the trips of a day.",
      carName: "EX5 car", carDesc: "Geely Connect car cards for this car.",
      mapName: "EX5 map", mapDesc: "Where the car is.",
    },
    pt: {
      noGeely: "Os cartões da Geely Connect não foram encontrados. A Geely Connect está instalada e atualizada?",
      noCar: "O EX5 Insights não está configurado (sensor.ex5_battery não encontrado).",
      prevDay: "Dia anterior com viagem", nextDay: "Próximo dia com viagem", noTrips: "Nenhuma viagem neste dia.",
      noSpeed: "sem velocidade", parked: "parado", mapLink: "mapa", avg: "média", max: "máx.", points: "pontos",
      days: ["dom.", "seg.", "ter.", "qua.", "qui.", "sex.", "sáb."],
      months: ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."],
      label: (dw, d, m, y) => `${dw} ${d} de ${m} de ${y}`, upTo: "até",
      timelineName: "Timeline do EX5", timelineDesc: "Caminho das viagens de um dia.",
      carName: "Carro do EX5", carDesc: "Cartões da Geely Connect para este carro.",
      mapName: "Mapa do EX5", mapDesc: "Onde o carro está.",
    },
  };
  const lang = (hass) => ((hass && (hass.locale?.language || hass.language)) || navigator.language || "en")
    .toLowerCase().startsWith("pt") ? "pt" : "en";
  const tr = (hass) => T[lang(hass)];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const carOf = (hass, config) => hass && hass.states[(config && config.entity) || "sensor.ex5_battery"];

  // ---------------------------------------------------------------- car card

  // The Geely Connect cards rewrite their whole content on every update, which wipes injected styles: put the style
  // back after each redraw.
  const keepStyle = (el, css) => {
    const apply = () => {
      const root = el.shadowRoot;
      if (!root) return;
      let st = root.querySelector("style[data-ex5]");
      if (!st) {
        st = document.createElement("style");
        st.setAttribute("data-ex5", "");
        root.appendChild(st);
      }
      if (st.textContent !== css) st.textContent = css;
    };
    if (el.__ex5Observer) el.__ex5Observer.disconnect();
    const watch = () => {
      if (!el.shadowRoot) return setTimeout(watch, 100);
      el.__ex5Observer = new MutationObserver(apply);
      el.__ex5Observer.observe(el.shadowRoot, { childList: true });
      apply();
    };
    watch();
  };

  class Ex5CarCard extends HTMLElement {
    setConfig(config) {
      this._config = config || {};
      this._key = null;
    }

    set hass(hass) {
      this._hass = hass;
      const car = carOf(hass, this._config);
      const a = car ? car.attributes : null;
      const key = a ? `${a.geely_prefix}|${a.car_image}|${a.paint}|${a.dark_paint}` : "none";
      if (key !== this._key) {
        this._key = key;
        this._build(a);
      }
      (this._cards || []).forEach((c) => { c.hass = hass; });
    }

    getCardSize() { return 12; }
    getGridOptions() { return { columns: "full", rows: "auto" }; }

    async _build(a) {
      const t = tr(this._hass);
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      const root = this.shadowRoot;
      this._cards = [];
      if (!a || !a.geely_prefix) {
        root.innerHTML = `<ha-card><div style="padding:16px">${esc(t.noCar)}</div></ha-card>`;
        return;
      }
      const ok = await Promise.race([
        customElements.whenDefined("geely-card").then(() => true),
        new Promise((r) => setTimeout(() => r(false), 15000)),
      ]);
      if (!ok) {
        root.innerHTML = `<ha-card><div style="padding:16px">${esc(t.noGeely)}</div></ha-card>`;
        return;
      }
      root.innerHTML = `<style>:host{display:block}.stack{display:flex;flex-direction:column;gap:0}</style><div class="stack"></div>`;
      const stack = root.querySelector(".stack");
      const paint = a.paint ? `:host { --geely-car-paint: ${a.paint}; }\n` : "";
      const onBody = a.dark_paint
        ? ".tv-lab.onbody { fill: rgba(255,255,255,.55) !important; }\n.tv-stat.onbody { fill: rgba(255,255,255,.85) !important; }\n.tv-stat.open.onbody { fill: #e8a13a !important; }\n"
        : "";
      const name = this._config.name || "Geely EX5";
      const full = document.createElement("geely-card");
      const fullConfig = { type: "custom:geely-card", prefix: a.geely_prefix, name, nav: ["maps", "waze", "apple"] };
      if (a.car_image) {
        // The pictures face right; the hotspots are where the headlight, taillight and charging port are.
        Object.assign(fullConfig, {
          car_image: a.car_image, car_image_facing: "right",
          car_image_hotspots: { headlight: [95, 46], taillight: [5, 34], port: [76, 45] },
        });
      }
      full.setConfig(fullConfig);
      keepStyle(full, paint + onBody
        + ".shell { border-bottom: none !important; border-bottom-left-radius: 0 !important; border-bottom-right-radius: 0 !important; padding-bottom: 0 !important; }\n.footer { display: none !important; }\n");
      this._cards.push(full);
      stack.appendChild(full);
      if (customElements.get("geely-card-top")) {
        const top = document.createElement("geely-card-top");
        top.setConfig({ type: "custom:geely-card-top", prefix: a.geely_prefix, name });
        keepStyle(top, paint + onBody
          + ".shell { border: 1px solid var(--divider-color, rgba(120,130,140,.2)) !important; border-top: none !important; border-radius: 0 0 var(--ha-card-border-radius, 12px) var(--ha-card-border-radius, 12px) !important; background: var(--ha-card-background, var(--card-background-color, #fff)) !important; padding: 4px 20px 16px !important; }\n.shell > :not(.carwrap):not(.footer) { display: none !important; }\n");
        this._cards.push(top);
        stack.appendChild(top);
      }
      this._cards.forEach((c) => { c.hass = this._hass; });
    }
  }

  // ---------------------------------------------------------------- map card

  class Ex5MapCard extends HTMLElement {
    setConfig(config) {
      this._config = config || {};
      this._tracker = null;
    }

    set hass(hass) {
      this._hass = hass;
      const car = carOf(hass, this._config);
      const tracker = car && car.attributes.tracker;
      if (tracker && tracker !== this._tracker) {
        this._tracker = tracker;
        this._build(tracker);
      }
      if (this._card) this._card.hass = hass;
    }

    getCardSize() { return 5; }
    getGridOptions() { return { columns: "full", rows: 5 }; }

    async _build(tracker) {
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      const helpers = await window.loadCardHelpers();
      this._card = helpers.createCardElement({
        type: "map", entities: [{ entity: tracker, name: this._config.name || "EX5" }],
        hours_to_show: this._config.hours_to_show ?? 24, default_zoom: this._config.default_zoom ?? 15,
      });
      this._card.hass = this._hass;
      this.shadowRoot.innerHTML = "<style>:host{display:block;height:100%}</style>";
      this.shadowRoot.appendChild(this._card);
    }
  }

  // ---------------------------------------------------------------- timeline card

  // Speed bands (km/h): up to, color.
  const BANDS = [[30, "#43a047"], [60, "#c0ca33"], [90, "#fb8c00"], [110, "#f4511e"], [Infinity, "#c62828"]];
  const NO_SPEED = "#9e9e9e";
  const speedColor = (v) => (v == null ? NO_SPEED : BANDS.find(([upTo]) => v < upTo)[1]);

  class Ex5TimelineCard extends HTMLElement {
    setConfig(config) {
      this._config = { height: 420, ...config };
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      this._mounted = false;
    }

    set hass(hass) {
      this._hass = hass;
      if (this._map) this._map.hass = hass;
      if (!this._mounted) {
        this._mounted = true;
        this._mount();
      }
    }

    getCardSize() { return 8; }
    getGridOptions() { return { columns: "full", rows: "auto" }; }

    _api(path) {
      const q = this._config.entry ? `?entry=${encodeURIComponent(this._config.entry)}` : "";
      return this._hass.callApi("GET", `ex5_insights/${path}${q}`);
    }

    async _mount() {
      const t = tr(this._hass);
      const r = this.shadowRoot;
      const legend = BANDS.map(([upTo, color], i) => {
        const from = i ? BANDS[i - 1][0] : 0;
        const txt = i === 0 ? `${t.upTo} ${upTo}` : upTo === Infinity ? `${from}+` : `${from}–${upTo}`;
        return `<span><i class="line" style="background:${color}"></i>${txt}</span>`;
      }).join("");
      r.innerHTML = `
        <style>
          ha-card { padding: 12px 12px 8px; }
          .bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
          .bar input { flex: 1; min-width: 0; font: inherit; font-size: 15px; padding: 8px 10px; border-radius: 10px;
            border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
          .bar button { border: 0; background: var(--secondary-background-color); color: var(--primary-text-color);
            width: 40px; height: 38px; border-radius: 10px; font-size: 20px; cursor: pointer; }
          .bar button:disabled { opacity: .35; cursor: default; }
          .title { font-weight: 600; margin: 2px 2px 8px; }
          .map { height: ${Number(this._config.height || this._config.altura) || 420}px; border-radius: 12px; overflow: hidden; }
          .list { margin-top: 10px; display: grid; gap: 6px; }
          .item { display: flex; gap: 8px; align-items: baseline; font-size: 14px; }
          .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; transform: translateY(1px); }
          .empty { color: var(--secondary-text-color); padding: 16px 4px; text-align: center; }
          .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px; font-size: 12px;
            color: var(--secondary-text-color); }
          .legend span { display: inline-flex; align-items: center; gap: 4px; }
          .line { width: 14px; height: 4px; border-radius: 2px; display: inline-block; }
          .num { color: var(--secondary-text-color); }
          a { color: var(--primary-color); }
        </style>
        <ha-card>
          <div class="bar">
            <button class="prev" title="${esc(t.prevDay)}">‹</button>
            <input type="date" class="date">
            <button class="next" title="${esc(t.nextDay)}">›</button>
          </div>
          <div class="title"></div>
          <div class="map"></div>
          <div class="legend">${legend} <span>km/h</span>
            <span><i class="line" style="background:${NO_SPEED}"></i>${esc(t.noSpeed)}</span></div>
          <div class="list"></div>
        </ha-card>`;
      this._el = {
        prev: r.querySelector(".prev"), next: r.querySelector(".next"), date: r.querySelector(".date"),
        title: r.querySelector(".title"), map: r.querySelector(".map"), list: r.querySelector(".list"),
      };
      this._el.prev.addEventListener("click", () => this._jump(-1));
      this._el.next.addEventListener("click", () => this._jump(1));
      this._el.date.addEventListener("change", () => this._show(this._el.date.value));

      // ha-map is loaded on demand by Home Assistant: creating a map card forces it.
      if (!customElements.get("ha-map")) {
        try {
          const helpers = await window.loadCardHelpers();
          helpers.createCardElement({ type: "map", entities: ["zone.home"] });
        } catch (e) { /* keep waiting */ }
      }
      await customElements.whenDefined("ha-map");
      this._map = document.createElement("ha-map");
      this._map.hass = this._hass;
      this._map.autoFit = false;
      this._map.fitPadding = 30;
      this._map.style.height = "100%";
      this._el.map.appendChild(this._map);

      try { this._days = await this._api("days"); } catch (e) { this._days = []; }
      if (this._days.length) {
        this._el.date.min = this._days[0];
        this._el.date.max = this._days[this._days.length - 1];
      }
      const today = new Date();
      const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      this._show(this._days[this._days.length - 1] || iso);
    }

    _jump(step) {
      const now = this._el.date.value;
      const list = step < 0 ? this._days.filter((d) => d < now).reverse() : this._days.filter((d) => d > now);
      if (list.length) this._show(list[0]);
    }

    async _show(day) {
      if (!day) return;
      const t = tr(this._hass);
      this._el.date.value = day;
      const [y, m, d] = day.split("-").map(Number);
      this._el.title.textContent = t.label(t.days[new Date(y, m - 1, d).getDay()], d, t.months[m - 1], y);
      this._el.prev.disabled = !this._days.some((x) => x < day);
      this._el.next.disabled = !this._days.some((x) => x > day);
      const request = (this._request = Symbol());
      let trips = [];
      try { trips = await this._api(`day/${day}`); } catch (e) { trips = []; }
      if (request !== this._request) return;   // another day was chosen meanwhile
      const paths = [];
      const rows = [];
      const when = (h) => new Date(`${day}T${h || "00:00"}:00`);
      for (const trip of trips) {
        const pts = trip.points || [];
        // One path per stretch (previous point → point), with the stretch's speed color and name.
        for (let k = 1; k < pts.length; k++) {
          const [la0, lo0, h0] = pts[k - 1];
          const [la1, lo1, h1, v, vColor] = pts[k];
          paths.push({
            color: speedColor(vColor), gradualOpacity: 0,
            name: v != null ? `${v} km/h` : vColor != null ? `≈ ${vColor} km/h` : t.noSpeed,
            points: [{ point: [la0, lo0], timestamp: when(h0) }, { point: [la1, lo1], timestamp: when(h1) }],
          });
        }
        if (pts.length === 1) {
          const [la, lo, h] = pts[0];
          paths.push({ color: NO_SPEED, name: t.parked, points: [{ point: [la, lo], timestamp: when(h) }] });
        }
        const speed = trip.avg_speed != null
          ? ` <span class="num">· ${t.avg} ${trip.avg_speed}${trip.max_speed ? ` · ${t.max} ${trip.max_speed}` : ""} km/h</span>` : "";
        const link = trip.map ? ` · <a href="${esc(trip.map)}" target="_blank" rel="noreferrer">${esc(t.mapLink)}</a>` : "";
        rows.push(`<div class="item"><span class="dot" style="background:${speedColor(trip.avg_speed)}"></span>
          <span>${esc(trip.start)} – ${esc(trip.end)} · ${esc(trip.summary)}${speed}${link}</span></div>`);
      }
      this._map.paths = paths;
      this._map.hass = this._hass;
      this._el.list.innerHTML = rows.length ? rows.join("") : `<div class="empty">${esc(t.noTrips)}</div>`;
      // Frame all of the day's paths. ha-map's fitMap only considers entities and zones; its internal engine
      // (_engine.fitBounds, list of [lat, lon]) is used directly, with fitMap as a fallback if it changes.
      if (paths.length) {
        const all = paths.flatMap((p) => p.points.map((x) => x.point));
        const frame = (attempt = 0) => {
          try {
            if (this._map._engine && this._map._engine.fitBounds) {
              this._map._engine.fitBounds(all, { maxZoom: 16, pad: 0.05, padding: 30, animate: false });
              return;
            }
          } catch (e) { /* try again */ }
          if (attempt < 10) setTimeout(() => frame(attempt + 1), 300);
          else if (this._map.fitMap) { try { this._map.fitMap(); } catch (e) { /* ok */ } }
        };
        setTimeout(() => frame(), 300);
      }
    }
  }

  const define = (tag, cls) => { if (!customElements.get(tag)) customElements.define(tag, cls); };
  define("ex5-car-card", Ex5CarCard);
  define("ex5-map-card", Ex5MapCard);
  define("ex5-timeline-card", Ex5TimelineCard);
  const t = T[(navigator.language || "en").toLowerCase().startsWith("pt") ? "pt" : "en"];
  window.customCards = window.customCards || [];
  window.customCards.push(
    { type: "ex5-car-card", name: t.carName, description: t.carDesc },
    { type: "ex5-map-card", name: t.mapName, description: t.mapDesc },
    { type: "ex5-timeline-card", name: t.timelineName, description: t.timelineDesc },
  );
  console.info(`EX5 Insights cards ${VERSION}`);
})();
