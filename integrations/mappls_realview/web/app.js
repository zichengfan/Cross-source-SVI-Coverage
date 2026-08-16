(() => {
  "use strict";

  const DEFAULT_CENTER = { lat: 28.6335, lng: 77.2165 };
  const DEFAULT_ZOOM = 14;
  const statusBox = document.getElementById("status");
  const statusText = document.getElementById("status-text");

  window.captureReady = false;
  window.captureError = null;
  window.captureState = {
    sdkLoaded: false,
    mapLoaded: false,
    realviewRequested: false,
    realviewSourceDetected: false,
  };

  function setStatus(message, level = "info") {
    statusText.textContent = message;
    statusBox.dataset.level = level;
  }

  function fail(message) {
    window.captureError = message;
    setStatus(message, "error");
    throw new Error(message);
  }

  function numberParam(params, name, fallback) {
    const raw = params.get(name);
    if (raw === null) return fallback;
    const value = Number(raw);
    return Number.isFinite(value) ? value : fallback;
  }

  function initialView() {
    const params = new URLSearchParams(window.location.search);
    const west = numberParam(params, "west", NaN);
    const south = numberParam(params, "south", NaN);
    const east = numberParam(params, "east", NaN);
    const north = numberParam(params, "north", NaN);
    const hasBbox = [west, south, east, north].every(Number.isFinite);
    return {
      center: hasBbox
        ? { lat: (south + north) / 2, lng: (west + east) / 2 }
        : DEFAULT_CENTER,
      zoom: numberParam(params, "zoom", DEFAULT_ZOOM),
    };
  }

  function waitForRealViewSource(map, timeoutMs = 30000) {
    const started = Date.now();
    const poll = () => {
      try {
        if (typeof map.getSource === "function" && map.getSource("realview")) {
          window.captureState.realviewSourceDetected = true;
          window.captureReady = true;
          setStatus("RealView source ready; waiting for capture controller.");
          return;
        }
      } catch (error) {
        // The SDK may be updating its style while the source is being added.
      }
      if (Date.now() - started >= timeoutMs) {
        fail(
          "RealView source was not detected. Confirm that RealView is enabled for this Mappls project."
        );
        return;
      }
      window.setTimeout(poll, 250);
    };
    poll();
  }

  function initializeMap() {
    const view = initialView();
    const map = new mappls.Map("map", {
      center: view.center,
      zoom: view.zoom,
    });
    window.map = map;

    window.realviewCapture = {
      goTo(lon, lat, zoom) {
        map.jumpTo({ center: [lon, lat], zoom });
      },
      state() {
        return { ...window.captureState };
      },
    };

    map.on("load", () => {
      window.captureState.mapLoaded = true;
      setStatus("Base map ready; enabling RealView…");
      try {
        map.realview(true);
        window.captureState.realviewRequested = true;
        waitForRealViewSource(map);
      } catch (error) {
        fail(`Unable to enable RealView: ${error.message || error}`);
      }
    });

    map.on("error", (event) => {
      const detail = event && event.error ? event.error.message || String(event.error) : "Map SDK error";
      console.error("Mappls map error:", detail);
    });
  }

  const config = window.MAPPLS_CONFIG || {};
  const key = String(config.accessToken || "").trim();
  if (!key || key.includes("PASTE_YOUR_")) {
    fail("Missing key: copy config.example.js to config.local.js and add your Mappls static key.");
  }

  setStatus("Loading the authorized Mappls Web Maps JS SDK…");
  const sdk = document.createElement("script");
  sdk.src = `https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=${encodeURIComponent(key)}`;
  sdk.async = true;
  sdk.onload = () => {
    window.captureState.sdkLoaded = true;
    initializeMap();
  };
  sdk.onerror = () => fail("Mappls SDK failed to load. Check the key, whitelist and network access.");
  document.head.appendChild(sdk);
})();
