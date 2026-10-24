import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = path.resolve(__dirname, '../fixtures/minimal_transcript.txt');

test.describe('Meeting workflows', () => {
  test('UI upload shows transcript evidence (speakers, timestamps, text)', async ({ page }) => {
    await page.goto('/');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText('or click to browse').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(FIXTURE_PATH);

    await page.getByPlaceholder('Meeting title (optional)').fill('E2E Upload Test');

    await page.getByRole('button', { name: 'Upload & Analyze' }).click();

    await expect(page.getByText("Let's finalize the launch date.")).toBeVisible();
    await expect(page.getByText('Alice').first()).toBeVisible();
    await expect(page.getByText('0:00').first()).toBeVisible();
    await expect(page.getByText('0:04').first()).toBeVisible();
  });

  test('Extraction and confirmed status persistence', async ({ page }) => {
    await page.goto('/');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText('or click to browse').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(FIXTURE_PATH);

    await page.getByPlaceholder('Meeting title (optional)').fill('E2E Extract Persistence');

    await page.getByRole('button', { name: 'Upload & Analyze' }).click();

    await expect(page.getByText("Let's finalize the launch date.")).toBeVisible();

    await page.getByRole('button', { name: 'Run Extraction' }).click();

    await expect(page.getByText('launch date is 2026-08-01')).toBeVisible();

    const confirmButton = page.getByRole('button', { name: 'Confirm' }).first();
    await confirmButton.click();

    await expect(page.getByText('CONFIRMED')).toBeVisible();

    await page.getByRole('button', { name: 'Run Extraction' }).click();

    await expect(page.getByText('CONFIRMED')).toBeVisible();
  });

  test('Grounded chat citation click behavior and unsupported refusal with no citations', async ({ page }) => {
    test.setTimeout(45000);
    await page.goto('/');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText('or click to browse').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(FIXTURE_PATH);

    await page.getByPlaceholder('Meeting title (optional)').fill('E2E Chat Test');
    await page.getByRole('button', { name: 'Upload & Analyze' }).click();

    await expect(page.getByText("Let's finalize the launch date.")).toBeVisible();

    const chatInput = page.getByPlaceholder('Ask a question about this meeting...');

    await chatInput.fill('What is the launch date?');
    await chatInput.press('Enter');

    const citation = page.getByRole('button', { name: /Alice @/ }).first();
    await expect(citation).toBeVisible();

    await citation.click();

    await expect(page.getByText('Agreed. Decision: launch date is 2026-08-01.')).toBeVisible();

    const citationCountBefore = await page.getByRole('button', { name: /@ \d/ }).count();

    await chatInput.fill('What is the weather forecast for next Friday?');
    await chatInput.press('Enter');

    await expect(page.getByText("I don't have enough information in this meeting to answer that.")).toBeVisible();
    await expect(page.getByText('Citations')).not.toBeVisible();

    const citationCountAfter = await page.getByRole('button', { name: /@ \d/ }).count();
    expect(citationCountAfter).toBe(0);
  });
});