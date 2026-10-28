const LAMBDA_URL = window.APP_CONFIG?.apiBaseUrl;
const INITIAL_WAIT_SECONDS = 60;
const POLL_INTERVAL_MS = 1000;
const SLOW_POLL_INTERVAL_MS = 5000;

const timerEl = document.getElementById("timer");
const statusEl = document.getElementById("status");

const params = new URLSearchParams(window.location.search);
const sessionId = params.get("sessionId");

if (!LAMBDA_URL) {
    statusEl.innerText = "❌ Brak konfiguracji API.";
    timerEl.innerText = "—";
} else if (!sessionId) {
    statusEl.innerText = "❌ Brak identyfikatora sesji.";
    timerEl.innerText = "—";
}

let secondsLeft = INITIAL_WAIT_SECONDS;
let pollInterval = null;
let countdownInterval = null;

function formatTime(s) {
    const m = String(Math.floor(s / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${m}:${sec}`;
}

function stopAll() {
    clearInterval(pollInterval);
    clearInterval(countdownInterval);
}

function onSuccess() {
    stopAll();
    window.location.href = `success.html?sessionId=${encodeURIComponent(sessionId)}`;
}

function startPolling(intervalMs) {
    clearInterval(pollInterval);
    pollInterval = setInterval(checkStatus, intervalMs);
}

async function checkStatus() {
    try {
        const res = await fetch(`${LAMBDA_URL}/status?sessionId=${encodeURIComponent(sessionId)}`);

        if (!res.ok) {
            statusEl.innerText = "⚠️ Błąd połączenia, próbuję ponownie...";
            return;
        }

        const data = await res.json();

        if (data.status === "active") {
            statusEl.innerText = "✅ Płatność potwierdzona!";
            onSuccess();
        } else if (data.status === "activation_failed") {
            statusEl.innerText = "⚠️ Płatność przyjęta. Ponawiamy uruchomienie prysznica...";
        }

    } catch (e) {
        statusEl.innerText = "⚠️ Błąd połączenia, próbuję ponownie...";
    }
}

if (LAMBDA_URL && sessionId) {
    countdownInterval = setInterval(() => {
        secondsLeft--;
        timerEl.innerText = formatTime(secondsLeft);

        if (secondsLeft <= 0) {
            clearInterval(countdownInterval);
            timerEl.innerText = "—";
            statusEl.innerText = "⏳ Potwierdzenie trwa dłużej. Nadal sprawdzamy płatność...";
            startPolling(SLOW_POLL_INTERVAL_MS);
        }
    }, POLL_INTERVAL_MS);

    startPolling(POLL_INTERVAL_MS);

    checkStatus();
}
