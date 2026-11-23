const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const message = document.getElementById("authMessage");

function showMessage(text, isError = true) {
    message.textContent = text;
    message.style.color = isError ? "#c0392b" : "#21865b";
}

function showLogin() {
    loginForm.hidden = false;
    registerForm.hidden = true;
    loginTab.classList.add("active");
    registerTab.classList.remove("active");
    showMessage("");
}

function showRegister() {
    loginForm.hidden = true;
    registerForm.hidden = false;
    loginTab.classList.remove("active");
    registerTab.classList.add("active");
    showMessage("");
}

async function checkSession() {
    try {
        const response = await fetch("/auth/me", {
            credentials: "same-origin"
        });
        if (response.ok) {
            window.location.replace("/dashboard");
        }
    } catch (error) {
        console.error("Session check failed:", error);
    }
}

loginTab.addEventListener("click", showLogin);
registerTab.addEventListener("click", showRegister);

loginForm.addEventListener("submit", async event => {
    event.preventDefault();
    showMessage("Signing in...", false);

    try {
        const response = await fetch("/auth/login", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: document.getElementById("loginEmail").value.trim(),
                password: document.getElementById("loginPassword").value
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Login failed.");
        }

        window.location.replace("/dashboard");
    } catch (error) {
        showMessage(error.message);
    }
});

registerForm.addEventListener("submit", async event => {
    event.preventDefault();

    const password = document.getElementById("registerPassword").value;
    const confirmation = document.getElementById("confirmPassword").value;

    if (password !== confirmation) {
        showMessage("Passwords do not match.");
        return;
    }

    if (!document.getElementById("ownershipNotice").checked) {
        showMessage("Please confirm your website monitoring authorization.");
        return;
    }

    showMessage("Creating your account...", false);

    try {
        const response = await fetch("/auth/register", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: document.getElementById("registerEmail").value.trim(),
                password
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Registration failed.");
        }

        window.location.replace("/dashboard");
    } catch (error) {
        showMessage(error.message);
    }
});

checkSession();
