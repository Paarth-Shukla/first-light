// Behaviour for the harness selfcheck page. Loaded as an ES module on purpose:
// it only runs if the test server sends a JavaScript MIME type.

const $ = (id) => document.getElementById(id);
const show = (id, text) => { $(id).textContent = String(text); };
const isTyping = (target) => target.matches("input, textarea");

// -- mouse ---------------------------------------------------------------
let clicks = 0;
$("counter").addEventListener("click", (event) => {
  clicks += 1;
  show("counter", `Clicked ${clicks} time${clicks === 1 ? "" : "s"}`);
  show("click-info", `trusted=${event.isTrusted} detail=${event.detail} button=${event.button}`);
});
$("hover-target").addEventListener("mouseenter", () => show("hover-target", "Hovered"));
$("disabled").addEventListener("click", () => show("disabled", "Clicked while disabled"));
$("covered").addEventListener("click", () => show("covered", "Clicked through the overlay"));
$("open-drawer").addEventListener("click", () => $("drawer").classList.add("open"));
$("drawer-button").addEventListener("click", () => show("drawer-button", "Drawer clicked"));
$("far").addEventListener("click", () => show("far", "Reached"));

// -- keyboard ------------------------------------------------------------
let keydowns = 0;
let inputs = 0;
$("echo").addEventListener("keydown", () => show("keydowns", keydowns += 1));
$("echo").addEventListener("input", (event) => {
  show("inputs", inputs += 1);
  show("echo-out", event.target.value);
});

function moveSelection(step) {
  const items = Array.from(document.querySelectorAll("#list li"));
  const current = items.findIndex((item) => item.classList.contains("selected"));
  const next = Math.max(0, Math.min(items.length - 1, current + step));
  items[current].classList.remove("selected");
  items[next].classList.add("selected");
}

document.addEventListener("keydown", (event) => {
  const modifiers = ["alt", "ctrl", "meta", "shift"].filter((name) => event[`${name}Key`]).join("+");
  show("last-key", `${event.key}|${event.code}|${modifiers}|trusted=${event.isTrusted}`);
  if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    $("palette").hidden = !$("palette").hidden;
    return;
  }
  if (event.key === "Escape") {
    $("palette").hidden = true;
    $("help").hidden = true;
    document.activeElement.blur();
    return;
  }
  if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.key === "/") {
    event.preventDefault();
    $("echo").focus();
  } else if (event.key === "?") {
    $("help").hidden = false;
  } else if (event.key === "j") {
    moveSelection(1);
  } else if (event.key === "k") {
    moveSelection(-1);
  }
});

// -- environment ---------------------------------------------------------
function watchMedia(query, id, whenTrue, whenFalse) {
  const media = matchMedia(query);
  const update = () => show(id, media.matches ? whenTrue : whenFalse);
  media.addEventListener("change", update);
  update();
}
watchMedia("(prefers-color-scheme: dark)", "scheme", "dark", "light");
watchMedia("(prefers-reduced-motion: reduce)", "motion", "reduced", "full");
watchMedia("(max-width: 600px)", "layout", "narrow", "wide");
watchMedia("(pointer: coarse)", "pointer", "coarse", "fine");

const showViewport = () => show("viewport", `${innerWidth}x${innerHeight}@${devicePixelRatio}`);
addEventListener("resize", showViewport);
showViewport();

const showOnline = () => show("online", navigator.onLine ? "online" : "offline");
addEventListener("online", showOnline);
addEventListener("offline", showOnline);
showOnline();

const showRoute = () => show("route", location.hash || "(none)");
addEventListener("hashchange", showRoute);
showRoute();

show("seed", window.__seed === undefined ? "(none)" : window.__seed);

// -- data and storage ----------------------------------------------------
async function loadData() {
  try {
    const response = await fetch("data.json");
    show("data", (await response.json()).message);
  } catch (error) {
    show("data", `fetch failed: ${error.message}`);
  }
}
$("refetch").addEventListener("click", () => {
  show("data", "loading");
  loadData();
});
$("missing").addEventListener("click", async () => {
  const response = await fetch("missing.json");
  show("missing-out", `status ${response.status}`);
});

const visits = Number(localStorage.getItem("selfcheck.visits") || "0") + 1;
localStorage.setItem("selfcheck.visits", String(visits));
show("visits", visits);
show("note", localStorage.getItem("selfcheck.note") || "(none)");
$("save").addEventListener("click", () => {
  localStorage.setItem("selfcheck.note", $("echo").value);
  show("note", $("echo").value);
});

$("external").addEventListener("click", () => {
  const image = new Image();
  image.addEventListener("load", () => show("external-out", "loaded"));
  image.addEventListener("error", () => show("external-out", "failed"));
  image.src = "https://images.example.com/harness-selfcheck.png";
});

// -- errors --------------------------------------------------------------
$("console-error").addEventListener("click", () => console.error("deliberate console error", { code: 7 }));
$("console-warn").addEventListener("click", () => console.warn("deliberate warning", [1, "two"]));
$("throw").addEventListener("click", () => {
  setTimeout(() => { throw new Error("deliberate uncaught exception"); }, 0);
});
$("reject").addEventListener("click", () => {
  Promise.reject(new Error("deliberate unhandled rejection"));
});

// -- dialogs, files, timing ----------------------------------------------
$("ask").addEventListener("click", () => show("answer", confirm("Proceed?") ? "confirmed" : "declined"));
$("prompt").addEventListener("click", () => show("answer", `prompt: ${prompt("Your name?")}`));
$("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify({ exported: true, visits })], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "selfcheck-export.json";
  link.click();
  URL.revokeObjectURL(link.href);
});
$("import").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  show("import-out", `${file.name}: ${(await file.text()).split("\n")[0]}`);
});
$("spawn").addEventListener("click", () => {
  setTimeout(() => {
    const late = document.createElement("p");
    late.id = "late";
    late.textContent = "Arrived late";
    document.body.insertBefore(late, $("spacer"));
  }, 300);
});

// -- web worker ------------------------------------------------------------
const worker = new Worker("worker.js", { type: "module" });
worker.addEventListener("message", (event) => show("worker-out", event.data));
$("worker-ping").addEventListener("click", () => worker.postMessage("ping"));
$("worker-error").addEventListener("click", () => worker.postMessage("console-error"));
$("worker-throw").addEventListener("click", () => worker.postMessage("throw"));

await loadData();
show("boot", "ready");
