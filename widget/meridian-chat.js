/* Meridian chat widget: a plain JavaScript web component, with no build step.
 *
 *   <script src="/widget/meridian-chat.js" data-api="" data-store="store-001" defer></script>
 *
 * adds a launcher to the page. data-api is the assistant's base URL; an empty value means the
 * page's own origin. data-store is the store the customer shops at. Without data-api the script
 * only defines <meridian-chat>, which preview.html uses to draw example replies.
 *
 * Everything lives inside Shadow DOM, so the store's CSS and the widget's can't break each other.
 * Colors come from CSS custom properties a host page can set: --meridian-accent,
 * --meridian-surface, --meridian-text, --meridian-muted, --meridian-danger, --meridian-danger-bg.
 *
 * The widget draws the server's blocks as given and adds no text to a reply. Every string from
 * the server goes in through textContent, never innerHTML. Its own words are its chrome only,
 * listed in WORDS. A new block type is one new function in BLOCKS.
 */
(() => {
  "use strict";

  const WORDS = {
    title: "Meridian Pharmacy",
    launcher: "Chat with Meridian Pharmacy",
    close: "Close the chat",
    pharmacist: "Talk to a pharmacist",
    placeholder: "Ask about a product, a store or an order",
    send: "Send",
    you: "You",
    checking: "Checking the label…",
    offer: "A pharmacist can follow up on this.",
    confirm: "Ask a pharmacist",
    retry: "Try again",
    unreachable: "Sorry, the assistant can't be reached right now. If this is an emergency, call 911.",
    sources: "Sources",
    footer: "Not medical advice. In an emergency, call 911.",
  };
  const LIMITS = { message: 2000, order: 64, contact: 254 };

  function el(tag, attributes = {}, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes)) {
      if (value === null || value === undefined || value === false) continue;
      if (name === "text") node.textContent = value;
      else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
      else node.setAttribute(name, value === true ? "" : value);
    }
    for (const child of children) if (child) node.append(child);
    return node;
  }

  function sessionId() {
    const key = "meridian-session";
    try {
      const saved = sessionStorage.getItem(key);
      if (saved && /^[A-Za-z0-9_-]{8,64}$/.test(saved)) return saved;
    } catch (_) { /* storage blocked: a new ID per page load */ }
    const random = window.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}${Math.random()}`;
    const made = random.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64);
    try { sessionStorage.setItem(key, made); } catch (_) { /* see above */ }
    return made;
  }

  /* One function per block type in the reply schema: each draws a block as given. */
  const BLOCKS = {
    text: (block) => el("p", { class: "text", text: block.text }),

    label_section: (block) => el("section", { class: "label" },
      el("h4", {}, el("span", { class: "name", text: block.name }), el("span", { class: "section", text: block.title })),
      el("p", { text: block.text })),

    comparison: (block) => el("div", { class: "scroll" }, el("table", { class: "comparison" },
      el("thead", {}, el("tr", {}, el("td"), ...block.products.map((p) => el("th", { scope: "col", text: p.name })))),
      el("tbody", {}, ...block.rows.map((row) => el("tr", {},
        el("th", { scope: "row", text: row.title }), ...row.texts.map((text) => el("td", { text }))))))),

    product_list: (block) => el("ul", { class: "products" },
      ...block.products.map((p) => el("li", {}, el("strong", { text: p.name }), el("p", { text: p.uses })))),

    availability: (block) => el("section", { class: "availability" },
      el("h4", { text: block.name }),
      el("ul", {}, ...block.stores.map((s) => el("li", { class: s.quantity > 0 ? "in" : "out" },
        el("span", { class: "store", text: s.store_name }), el("span", { text: s.text }))))),

    store_info: (block) => el("section", { class: "store-info" },
      el("h4", { text: block.store.name }),
      el("p", { text: block.store.address }),
      el("p", {}, el("a", { href: `tel:${block.store.phone.replace(/[^\d+]/g, "")}`, text: block.store.phone })),
      el("table", { class: "hours" }, el("tbody", {}, ...Object.entries(block.store.hours).map(([day, hours]) =>
        el("tr", {}, el("th", { scope: "row", text: day }), el("td", { text: hours }))))),
      el("ul", { class: "services" }, ...block.store.services.map((service) => el("li", { text: service })))),

    policy_excerpt: (block) => el("section", { class: "policy" },
      el("h4", { text: block.title }), el("p", { text: block.text })),

    order_status: (block) => el("p", { class: "order-status", text: block.text }),

    order_form: (block, chat) => {
      const number = el("input", { name: "order_number", required: true, maxlength: LIMITS.order, autocomplete: "off" });
      const contact = el("input", { name: "contact", required: true, maxlength: LIMITS.contact, autocomplete: "email" });
      const form = el("form", { class: "order-form" },
        el("p", { text: block.text }),
        el("label", {}, el("span", { text: block.order_number_label }), number),
        el("label", {}, el("span", { text: block.contact_label }), contact),
        el("button", { type: "submit", class: "primary", text: block.submit_label }));
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        chat.verifyOrder(number.value.trim(), contact.value.trim());
        form.reset(); /* the details go to /orders/verify only, never into the chat */
      });
      return form;
    },
  };

  function chip(source) {
    if (source.text !== null && source.text !== undefined) {
      return el("details", { class: "chip" }, el("summary", { text: source.title }), el("blockquote", { text: source.text }));
    }
    const at = source.retrieved_at ? new Date(source.retrieved_at) : null;
    const time = at ? at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
    return el("span", { class: "chip live" }, el("span", { text: source.title }), el("time", { datetime: source.retrieved_at, text: time }));
  }

  function sourcesRow(sources) {
    if (!sources || sources.length === 0) return null;
    return el("div", { class: "sources", role: "group", "aria-label": WORDS.sources }, ...sources.map(chip));
  }

  const STYLE = `
    :host { --accent: var(--meridian-accent, #0b6e4f); --surface: var(--meridian-surface, #ffffff);
      --text: var(--meridian-text, #1d2127); --muted: var(--meridian-muted, #5b6470);
      --danger: var(--meridian-danger, #b42318); --danger-bg: var(--meridian-danger-bg, #fef3f2);
      --line: color-mix(in srgb, var(--muted) 30%, transparent);
      font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--text); }
    *, *::before, *::after { box-sizing: border-box; }
    :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
    button { font: inherit; cursor: pointer; border-radius: 8px; border: 1px solid var(--line);
      background: var(--surface); color: var(--text); padding: 6px 12px; }
    button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    button[disabled] { opacity: .6; cursor: progress; }
    .launcher { position: fixed; right: 20px; bottom: 20px; z-index: 2147483000; border-radius: 999px;
      padding: 12px 18px; background: var(--accent); color: #fff; border: 0; box-shadow: 0 6px 20px rgb(0 0 0 / .2); }
    .panel { position: fixed; right: 20px; bottom: 84px; z-index: 2147483000; width: min(400px, calc(100vw - 32px));
      height: min(640px, calc(100vh - 120px)); display: flex; flex-direction: column; background: var(--surface);
      border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 12px 40px rgb(0 0 0 / .22); overflow: hidden; }
    .panel[hidden] { display: none; }
    :host([inline]) .panel { position: static; width: 100%; height: auto; box-shadow: none; }
    header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--line); }
    header h3 { margin: 0; font-size: 16px; flex: 1; }
    .log { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
    :host([inline]) .log { overflow: visible; }
    .mine { align-self: flex-end; max-width: 85%; background: color-mix(in srgb, var(--accent) 12%, var(--surface));
      border-radius: 12px; padding: 8px 12px; white-space: pre-wrap; margin: 0; }
    .reply { display: flex; flex-direction: column; gap: 8px; }
    .reply p, .reply h4 { margin: 0; }
    .label h4, .availability h4, .store-info h4, .policy h4 { font-size: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    .label .section { color: var(--muted); font-weight: 500; }
    .banner { background: var(--danger-bg); border: 2px solid var(--danger); color: var(--danger);
      border-radius: 10px; padding: 10px 12px; font-weight: 600; }
    .scroll { overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; font-size: 13px; }
    th, td { text-align: left; vertical-align: top; padding: 6px; border-bottom: 1px solid var(--line); }
    .products { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
    .availability ul, .services { margin: 0; padding-left: 18px; }
    .availability .store { font-weight: 600; margin-right: 8px; }
    .availability .out { color: var(--muted); }
    .order-form { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
    .order-form label { display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
    input, textarea { font: inherit; padding: 8px; border: 1px solid var(--line); border-radius: 8px; color: var(--text); background: var(--surface); }
    .sources { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { font-size: 12px; border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px; color: var(--muted); }
    details.chip[open] { border-radius: 10px; flex-basis: 100%; }
    details.chip summary { cursor: pointer; }
    .chip blockquote { margin: 6px 0; color: var(--text); white-space: pre-wrap; }
    .chip.live time { margin-left: 6px; }
    .offer { border: 1px solid var(--accent); border-radius: 10px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
    .offer p, .notice { margin: 0; }
    .checking { color: var(--muted); font-style: italic; margin: 0; }
    form.composer { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--line); }
    form.composer textarea { flex: 1; resize: none; height: 42px; }
    footer { font-size: 12px; color: var(--muted); padding: 6px 12px 10px; text-align: center; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  `;

  class MeridianChat extends HTMLElement {
    constructor() {
      super();
      this.session = sessionId();
      this.root = this.attachShadow({ mode: "open" });
      this.root.append(el("style", { text: STYLE }));
    }

    connectedCallback() {
      if (this.panel) return;
      this.api = (this.getAttribute("api") || "").replace(/\/$/, "");
      this.store = this.getAttribute("store");
      this.live = this.hasAttribute("api");
      this.inline = this.hasAttribute("inline");
      this.build();
    }

    build() {
      this.log = el("div", { class: "log", role: "log", "aria-live": "polite", "aria-relevant": "additions" });
      const header = el("header", {},
        el("h3", { text: WORDS.title }),
        el("button", { type: "button", text: WORDS.pharmacist, onclick: () => this.handoff() }),
        this.inline ? null : el("button", { type: "button", "aria-label": WORDS.close, text: "×", onclick: () => this.close() }));
      this.panel = el("div", { class: "panel", role: "dialog", "aria-label": WORDS.title, hidden: !this.inline },
        header, this.log, this.live ? this.composer() : null, el("footer", { text: WORDS.footer }));
      this.panel.addEventListener("keydown", (event) => { if (event.key === "Escape" && !this.inline) this.close(); });
      if (!this.inline) {
        this.launcher = el("button", { type: "button", class: "launcher", "aria-expanded": "false",
          text: WORDS.launcher, onclick: () => (this.panel.hidden ? this.open() : this.close()) });
        this.root.append(this.launcher);
      }
      this.root.append(this.panel);
    }

    composer() {
      this.input = el("textarea", { "aria-label": WORDS.placeholder, placeholder: WORDS.placeholder, maxlength: LIMITS.message, rows: 1 });
      const form = el("form", { class: "composer" }, this.input, el("button", { type: "submit", class: "primary", text: WORDS.send }));
      form.addEventListener("submit", (event) => { event.preventDefault(); this.send(); });
      this.input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); this.send(); }
      });
      return form;
    }

    open() {
      this.panel.hidden = false;
      this.launcher.setAttribute("aria-expanded", "true");
      (this.input || this.panel).focus();
    }

    close() {
      this.panel.hidden = true;
      this.launcher.setAttribute("aria-expanded", "false");
      this.launcher.focus();
    }

    async post(path, body) {
      const response = await fetch(`${this.api}${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }

    append(node) {
      this.log.append(node);
      this.log.scrollTop = this.log.scrollHeight;
      return node;
    }

    async exchange(path, body) {
      const indicator = this.append(el("p", { class: "checking", role: "status", text: WORDS.checking }));
      try {
        this.showReply(await this.post(path, body));
      } catch (_) {
        this.append(el("p", { class: "notice", text: WORDS.unreachable }));
      } finally {
        indicator.remove();
      }
    }

    send() {
      const message = this.input.value.trim();
      if (!message) return;
      this.input.value = "";
      this.append(el("p", { class: "mine" }, el("span", { class: "visually-hidden", text: `${WORDS.you}: ` }), message));
      return this.exchange("/chat", { session_id: this.session, message, store_id: this.store || null });
    }

    verifyOrder(order_number, contact) {
      if (!order_number || !contact) return;
      return this.exchange("/orders/verify", { session_id: this.session, order_number, contact });
    }

    showReply(reply) {
      const blocks = reply.blocks.map((block) => (BLOCKS[block.type] ? BLOCKS[block.type](block, this) : null));
      const body = reply.emergency
        ? el("div", { class: "banner", role: "alert" }, ...blocks)
        : el("div", { class: "body" }, ...blocks);
      const offer = reply.handoff_offered
        ? el("div", { class: "offer" }, el("p", { text: WORDS.offer }),
          el("button", { type: "button", class: "primary", text: WORDS.confirm, onclick: (event) => this.handoff(event.target) }))
        : null;
      return this.append(el("article", { class: "reply", "data-reply-type": reply.reply_type }, body, sourcesRow(reply.sources), offer));
    }

    async handoff(button) {
      if (button) button.disabled = true;
      try {
        this.showHandoff(await this.post("/handoff", { session_id: this.session, confirmed: true }));
      } catch (_) {
        this.showHandoff({ ticket_id: null, text: WORDS.unreachable });
      } finally {
        if (button) button.disabled = false;
      }
    }

    showHandoff(reply) {
      const retry = reply.ticket_id ? null
        : el("button", { type: "button", text: WORDS.retry, onclick: (event) => { event.target.remove(); this.handoff(); } });
      return this.append(el("div", { class: "offer handoff", "data-ticket": reply.ticket_id || "" }, el("p", { text: reply.text }), retry));
    }
  }

  if (!customElements.get("meridian-chat")) customElements.define("meridian-chat", MeridianChat);

  const script = document.currentScript;
  if (script && script.hasAttribute("data-api")) {
    const mount = () => {
      const chat = document.createElement("meridian-chat");
      chat.setAttribute("api", script.getAttribute("data-api") || "");
      if (script.dataset.store) chat.setAttribute("store", script.dataset.store);
      document.body.append(chat);
    };
    if (document.body) mount();
    else document.addEventListener("DOMContentLoaded", mount);
  }
})();
