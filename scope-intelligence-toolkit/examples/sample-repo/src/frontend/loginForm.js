import { postJson } from "./apiClient.js";

export class LoginForm {
    constructor(root) {
        this.root = root;
    }

    async submit(email, password) {
        return await postJson("/api/login", { email, password });
    }
}

export function renderLoginForm(target) {
    return new LoginForm(target);
}
