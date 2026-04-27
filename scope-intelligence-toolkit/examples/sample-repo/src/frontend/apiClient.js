const API_BASE = process.env.API_BASE || "http://localhost:3000";
const API_TIMEOUT = process.env.API_TIMEOUT_MS || "5000";

export async function postJson(url, payload) {
    const res = await fetch(`${API_BASE}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return res.json();
}

export async function getJson(url) {
    const res = await fetch(`${API_BASE}${url}`);
    return res.json();
}
