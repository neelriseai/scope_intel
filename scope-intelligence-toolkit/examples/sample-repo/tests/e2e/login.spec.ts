import { test, expect } from "@playwright/test";

test("user can log in via the form", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", "alice@example.com");
    await page.fill("#password", "password");
    await page.click("button[type=submit]");
    await expect(page.locator(".welcome")).toBeVisible();
});

test("login form rejects empty password", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", "alice@example.com");
    await page.click("button[type=submit]");
    await expect(page.locator(".error")).toBeVisible();
});
