// Worker half of the selfcheck page. The harness must capture what a worker logs
// or throws exactly as it captures the page's own errors.
self.addEventListener("message", (event) => {
  if (event.data === "ping") {
    postMessage("pong from the worker");
  } else if (event.data === "console-error") {
    console.error("deliberate worker console error");
    postMessage("logged");
  } else if (event.data === "throw") {
    throw new Error("deliberate worker exception");
  }
});
