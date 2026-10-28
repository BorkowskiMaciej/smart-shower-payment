const LAMBDA_URL = window.APP_CONFIG?.apiBaseUrl;

let countdownInterval;

window.addEventListener("DOMContentLoaded", () => {
    init();
});

function showReturnButton() {
    const wrapper = document.getElementById("returnBtnWrapper");
    if (wrapper) {
        wrapper.style.display = "block";
    }
}

async function init() {
    const timer = document.getElementById("timer");
    const status = document.getElementById("status");

    if (!LAMBDA_URL) {
        timer.innerText = "—";
        status.innerText = "Brak konfiguracji API.";
        showReturnButton();
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("sessionId");

    if (!sessionId) {
        timer.innerText = "—";
        status.innerText = "Brak identyfikatora sesji.";
        showReturnButton();
        return;
    }

    try {
        const res = await fetch(`${LAMBDA_URL}/status?sessionId=${encodeURIComponent(sessionId)}`);

        if (!res.ok) {
            timer.innerText = "—";
            status.innerText = "Nie udało się pobrać statusu płatności.";
            showReturnButton();
            return;
        }

        const data = await res.json();

        if (data.status !== "active" || !data.showerEndsAt) {
            timer.innerText = "—";
            status.innerText = "Brak danych o trwającym prysznicu.";
            showReturnButton();
            return;
        }

        const endsAtMs = data.showerEndsAt * 1000;
        startTimer(endsAtMs);

    } catch (e) {
        timer.innerText = "—";
        status.innerText = "Błąd połączenia. Skontaktuj się z bosmanem.";
        showReturnButton();
    }
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;

    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function startTimer(endsAtMs) {
    const timer = document.getElementById("timer");
    const status = document.getElementById("status");

    function tick() {
        const remainingMs = endsAtMs - Date.now();
        const timeLeft = Math.max(0, Math.ceil(remainingMs / 1000));

        timer.innerText = formatTime(timeLeft);

        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            status.innerText = "Zakończono.";
            showReturnButton();
        }
    }

    tick();
    countdownInterval = setInterval(tick, 1000);
}
