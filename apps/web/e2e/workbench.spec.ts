import { expect, test } from "@playwright/test";

test("real local ranking workbench journey", async ({ page }) => {
  await page.goto("/");

  await page.waitForLoadState('networkidle');
await page.getByRole("button", { name: "Run example search" }).click();
  await page.waitForSelector('.provider', { state: 'visible', timeout: 60000 });
  await expect(page.locator('.provider').first()).toBeVisible();
  await page.locator(".provider").first().click();
  await expect(page.locator(".inspector h2")).toBeVisible();
  await expect(page.getByText("MODEL SCORE · NOT A PROBABILITY")).toBeVisible();
  await page.getByRole("button", { name: "Close provider inspector" }).click();

  await page.getByRole("button", { name: "Ranking Comparison" }).click();
  await page.getByRole("button", { name: "Compare strategies" }).click();
  await expect(page.locator(".comparison-grid")).toContainText("lambdamart");
  await expect(
    page.locator(".comparison-grid .compare-row").first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "Evaluation Lab" }).click();
  await expect(
    page.getByRole("heading", { name: "Strategy performance" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Query level NDCG@10 changes" }),
  ).toBeVisible();
  await expect(page.getByText(/Synthetic held-out evaluation/)).toBeVisible();
  await page.getByLabel("Labeled held-out query").selectOption({ index: 1 });
  await expect(
    page.getByRole("heading", { name: /Held-out query inspection/ }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Experiment Lab" }).click();
  await page.getByLabel("EXPERIMENT ID").fill("browser-e2e");
  await page
    .getByRole("button", { name: "Create persistent experiment" })
    .click();
  await expect(page.getByText(/Created browser-e2e/)).toBeVisible();
  await page.getByLabel("SESSIONS (MAX 10,000)").fill("20");
  await page
    .getByRole("button", { name: "Run deterministic simulation" })
    .click();
  await expect(
    page.getByText(/Simulated experiments validate instrumentation/),
  ).toBeVisible();
  await expect(page.getByText(/Event counts:/)).toBeVisible();
  await expect(page.getByText("Recent simulated event timeline")).toBeVisible();
  await page.getByRole("button", { name: "Reset simulated data" }).click();
  await expect(page.getByText(/Event counts:/)).toHaveCount(0);

  await page.getByRole("button", { name: "Data & Models" }).click();
  await expect(
    page.getByRole("heading", { name: "Pipeline status" }),
  ).toBeVisible();
  await expect(
    page.getByText(/LambdaMART: loaded and schema checked/),
  ).toBeVisible();
});
