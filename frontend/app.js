async function start() {
    const btn = document.getElementById("btn");
    const status = document.getElementById("status");
    const emailInput = document.getElementById("email");

    const email = emailInput.value.trim();

    btn.disabled = true;
    status.innerText = "⏳ Przekierowanie...";

    try {
        const apiBaseUrl = window.APP_CONFIG?.apiBaseUrl;
        if (!apiBaseUrl) {
            throw new Error("Missing apiBaseUrl configuration");
        }

        const res = await fetch(`${apiBaseUrl}/create-payment`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({email})
        });

        if (res.ok) {
            const data = await res.json();
            window.location.href = data.redirectUrl;
            return;
        }

        if (res.status === 400) {
            let message = "Nieprawidłowe dane. Sprawdź adres e-mail.";
            try {
                const errorData = await res.json();
                if (errorData.error === "Invalid email parameter" || errorData.error === "Missing email parameter") {
                    message = "Podany adres e-mail jest nieprawidłowy.";
                }
            } catch (_) {
            }
            status.innerText = `❌ ${message}`;
        } else if (res.status === 409) {
            status.innerText = "🚿 Prysznic jest aktualnie używany. Spróbuj ponownie za chwilę.";
        } else if (res.status === 503) {
            status.innerText = "⚠️ Nie udało się połączyć z urządzeniem. Skontaktuj się z bosmanem.";
        } else {
            status.innerText = "❌ Brak połączenia. Skontaktuj się z bosmanem.";
        }

        btn.disabled = false;

    } catch (e) {
        status.innerText = "❌ Brak połączenia. Skontaktuj się z bosmanem.";
        btn.disabled = false;
    }
}

window.addEventListener("DOMContentLoaded", () => {
    const acceptAll = document.getElementById("acceptAll");
    const agreements = document.querySelectorAll(".agreement");
    const emailInput = document.getElementById("email");
    const btn = document.getElementById("btn");

    const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    const emailError = document.getElementById("emailError");
    const duration = window.APP_CONFIG?.showerDurationSeconds;
    const price = window.APP_CONFIG?.pricePln;

    document.getElementById("duration").innerText = duration
        ? `${Math.ceil(duration / 60)} minut`
        : "brak konfiguracji";
    document.getElementById("price").innerText = price ?? "brak konfiguracji";

    function isEmailValid() {
        return EMAIL_REGEX.test(emailInput.value.trim());
    }

    function refreshButton() {
        const allChecked = [...agreements].every(el => el.checked);
        acceptAll.checked = allChecked;
        btn.disabled = !(allChecked && isEmailValid());
    }

    function validateEmailField() {
        const value = emailInput.value.trim();
        const invalid = value.length > 0 && !isEmailValid();

        emailError.innerText = invalid ? "Podaj prawidłowy adres e-mail." : "";
        emailError.classList.toggle("visible", invalid);
        emailInput.classList.toggle("invalid", invalid);
    }

    acceptAll.addEventListener("change", () => {
        agreements.forEach(el => {
            el.checked = acceptAll.checked;
        });
        refreshButton();
    });
    agreements.forEach(el => el.addEventListener("change", refreshButton));
    emailInput.addEventListener("input", () => {
        validateEmailField();
        refreshButton();
    });
    emailInput.addEventListener("blur", validateEmailField);
});
