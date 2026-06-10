import { chromium } from "@playwright/test";
import { promises as fs } from "fs";

const SCREENSHOTS_DIR = "/tmp/dclaw_gallery_test";

async function ensureDir(dir) {
  try { await fs.mkdir(dir, { recursive: true }); } catch {}
}

async function main() {
  await ensureDir(SCREENSHOTS_DIR);

  const consoleMessages = [];
  const networkErrors = [];
  const networkRequests = [];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  const page = await context.newPage();

  // Capture console messages
  page.on("console", (msg) => {
    const type = msg.type();
    const text = msg.text();
    consoleMessages.push({ type, text });
    if (type === "error" || type === "warning") {
      console.log(`[CONSOLE ${type.toUpperCase()}] ${text}`);
    }
  });

  page.on("pageerror", (err) => {
    consoleMessages.push({ type: "pageerror", text: err.message });
    console.log(`[PAGE ERROR] ${err.message}`);
  });

  page.on("requestfailed", (req) => {
    const failure = req.failure();
    networkErrors.push({
      url: req.url(),
      method: req.method(),
      failure: failure?.errorText,
    });
    console.log(`[NET FAIL] ${req.method()} ${req.url()} => ${failure?.errorText}`);
  });

  page.on("response", (resp) => {
    const status = resp.status();
    const url = resp.url();
    if (status >= 400) {
      networkErrors.push({ url, status, method: resp.request().method() });
      console.log(`[NET ${status}] ${resp.request().method()} ${url}`);
    }
    if (url.includes("localhost:8090") || url.includes("/api/")) {
      networkRequests.push({ url, status, method: resp.request().method() });
    }
  });

  // ── STEP 1: Navigate to http://localhost:3000 ──────────────────────────
  console.log("\n=== STEP 1: Navigate to http://localhost:3000 ===");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/01_home.png`, fullPage: true });
  console.log("Page title:", await page.title());
  console.log("URL:", page.url());

  // ── STEP 2: Click the "Channels" tab to enter messaging view ──────────
  console.log("\n=== STEP 2: Click Channels tab ===");
  const channelsTab = page.locator('button:has-text("Channels")').first();
  const channelsTabCount = await channelsTab.count();
  console.log(`Found ${channelsTabCount} 'Channels' tab button(s)`);

  if (channelsTabCount > 0) {
    await channelsTab.click();
    await page.waitForTimeout(2000);
    console.log("Clicked Channels tab");
  } else {
    console.log("WARNING: Channels tab not found!");
    const allBtns = await page.locator("button").all();
    for (const b of allBtns) {
      const txt = await b.textContent();
      console.log(`  Button: "${txt?.trim()}"`);
    }
  }

  await page.screenshot({ path: `${SCREENSHOTS_DIR}/02_channels_tab.png`, fullPage: true });
  console.log("Screenshot: 02_channels_tab.png");
  console.log("API calls so far:", networkRequests.map(r => `${r.method} ${r.url} => ${r.status}`));

  // ── STEP 3: Select "general" channel ──────────────────────────────────
  console.log("\n=== STEP 3: Select 'general' channel ===");
  await page.waitForTimeout(1000);

  const allSidebarBtns = await page.locator("aside button").all();
  console.log(`Buttons in sidebar: ${allSidebarBtns.length}`);
  for (const btn of allSidebarBtns) {
    const txt = await btn.textContent();
    console.log(`  Sidebar button: "${txt?.trim()}"`);
  }

  let generalChannel = page.locator('button:has-text("general")').first();
  let generalCount = await generalChannel.count();
  console.log(`'general' channel button found: ${generalCount}`);

  if (generalCount > 0) {
    await generalChannel.click();
    await page.waitForTimeout(1500);
    console.log("Clicked 'general' channel");
  } else if (allSidebarBtns.length > 1) {
    await allSidebarBtns[1].click();
    await page.waitForTimeout(1500);
    const txt = await allSidebarBtns[1].textContent();
    console.log(`Clicked first channel: "${txt?.trim()}"`);
  }

  await page.screenshot({ path: `${SCREENSHOTS_DIR}/03_general_channel.png`, fullPage: true });
  console.log("Screenshot: 03_general_channel.png");

  // ── STEP 4: Click the Gallery button ──────────────────────────────────
  console.log("\n=== STEP 4: Click the Gallery button ===");

  // Find header-area Gallery button
  let galleryClicked = false;
  const galleryByTitle = page.locator('[title="Media gallery"]').first();
  if (await galleryByTitle.count() > 0) {
    await galleryByTitle.click();
    galleryClicked = true;
    console.log("Clicked gallery via title attribute");
  } else {
    const galleryByText = page.locator('button:has-text("Gallery")').first();
    if (await galleryByText.count() > 0) {
      await galleryByText.click();
      galleryClicked = true;
      console.log("Clicked gallery via text");
    } else {
      console.log("WARNING: Gallery button not found! Listing all buttons:");
      const allBtns = await page.locator("button").all();
      for (const btn of allBtns) {
        const txt = await btn.textContent();
        const title = await btn.getAttribute("title");
        if (txt?.trim() || title) {
          console.log(`  Button text="${txt?.trim()}" title="${title}"`);
        }
      }
    }
  }

  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/04_gallery_clicked.png`, fullPage: true });
  console.log("Screenshot: 04_gallery_clicked.png");

  // ── STEP 5: Check if gallery panel opened ─────────────────────────────
  console.log("\n=== STEP 5: Check gallery panel status ===");

  const galleryPanelVisible = await page.locator('text=Media Gallery').isVisible().catch(() => false);
  console.log(`Gallery panel opened: ${galleryPanelVisible}`);

  const noImagesVisible = await page.locator('text=No images shared yet').isVisible().catch(() => false);
  console.log(`"No images shared yet" visible: ${noImagesVisible}`);

  const imgCountEl = page.locator('span').filter({ hasText: /\(\d+ images?\)/ }).first();
  if (await imgCountEl.isVisible().catch(() => false)) {
    console.log(`Image count: "${await imgCountEl.textContent()}"`);
  }

  const allImgsStep5 = await page.locator("img").all();
  console.log(`All <img> elements on page: ${allImgsStep5.length}`);
  for (const img of allImgsStep5) {
    const src = await img.getAttribute("src");
    const alt = await img.getAttribute("alt");
    const nw = await img.evaluate((el) => el.naturalWidth).catch(() => -1);
    const nh = await img.evaluate((el) => el.naturalHeight).catch(() => -1);
    const complete = await img.evaluate((el) => el.complete).catch(() => false);
    console.log(`  src="${src}" alt="${alt}" ${nw}x${nh} complete=${complete}`);
  }

  // ── STEP 6: Close gallery and upload image ─────────────────────────────
  console.log("\n=== STEP 6: Close gallery and upload test image ===");

  if (galleryPanelVisible) {
    // Close the gallery: look for X button within gallery panel
    const gallerySection = page.locator('div').filter({ has: page.locator('text=Media Gallery') }).first();
    const closeBtns = await gallerySection.locator('button').all();
    console.log(`Buttons in gallery section: ${closeBtns.length}`);
    if (closeBtns.length > 0) {
      // Last button in gallery header should be the X close button
      await closeBtns[closeBtns.length - 1].click();
      await page.waitForTimeout(500);
      console.log("Closed gallery");
    }
  }

  // Find file input
  const fileInput = page.locator('input[type="file"]');
  const fileInputCount = await fileInput.count();
  console.log(`File input found: ${fileInputCount}`);

  if (fileInputCount > 0) {
    // Set the file directly on the hidden input
    await fileInput.setInputFiles("/tmp/test_image.png");
    await page.waitForTimeout(3000);
    console.log("File set on input, waiting for upload...");
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/05_after_upload.png`, fullPage: true });
    console.log("Screenshot: 05_after_upload.png");

    // Now try to send the message
    // Find the send button (icon-only or text)
    const allBtnsForSend = await page.locator("button").all();
    let foundSend = false;
    for (const btn of allBtnsForSend) {
      const title = await btn.getAttribute("title");
      const txt = await btn.textContent();
      if (title?.toLowerCase().includes("send") || txt?.trim() === "Send") {
        const disabled = await btn.isDisabled().catch(() => true);
        console.log(`Found send button: title="${title}" text="${txt?.trim()}" disabled=${disabled}`);
        if (!disabled) {
          await btn.click();
          foundSend = true;
          console.log("Send button clicked!");
          break;
        }
      }
    }

    if (!foundSend) {
      // Try pressing Enter in input
      const msgInput = page.locator('input[placeholder]').last();
      if (await msgInput.count() > 0) {
        const ph = await msgInput.getAttribute("placeholder");
        console.log(`Trying Enter on input with placeholder="${ph}"`);
        await msgInput.press("Enter");
        foundSend = true;
      }
    }

    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/06_after_send.png`, fullPage: true });
    console.log("Screenshot: 06_after_send.png");
  } else {
    console.log("WARNING: No file input found!");
    // List all inputs on page
    const allInputs = await page.locator("input").all();
    for (const inp of allInputs) {
      const type = await inp.getAttribute("type");
      const placeholder = await inp.getAttribute("placeholder");
      console.log(`  input type="${type}" placeholder="${placeholder}"`);
    }
  }

  // ── STEP 7: Open gallery again ─────────────────────────────────────────
  console.log("\n=== STEP 7: Open gallery again after upload ===");

  // Close any open lightbox overlay first (click the backdrop)
  const lightbox = page.locator('div.fixed.inset-0').first();
  if (await lightbox.count() > 0 && await lightbox.isVisible().catch(() => false)) {
    console.log("Lightbox overlay detected — closing it");
    await lightbox.click({ position: { x: 10, y: 10 } }); // click top-left corner (backdrop)
    await page.waitForTimeout(500);
  }

  // Also try pressing Escape
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  const galleryByTitle2 = page.locator('[title="Media gallery"]').first();
  if (await galleryByTitle2.count() > 0) {
    await galleryByTitle2.click({ force: true });
  } else {
    const galleryByText2 = page.locator('button:has-text("Gallery")').first();
    if (await galleryByText2.count() > 0) await galleryByText2.click({ force: true });
  }

  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/07_gallery_after_upload.png`, fullPage: true });
  console.log("Screenshot: 07_gallery_after_upload.png");

  // ── STEP 8: Inspect gallery images ────────────────────────────────────
  console.log("\n=== STEP 8: Inspect gallery images after upload ===");

  const galleryPanelVisible2 = await page.locator('text=Media Gallery').isVisible().catch(() => false);
  console.log(`Gallery panel visible: ${galleryPanelVisible2}`);

  const noImagesVisible2 = await page.locator('text=No images shared yet').isVisible().catch(() => false);
  console.log(`"No images shared yet" visible: ${noImagesVisible2}`);

  const imgCountEl2 = page.locator('span').filter({ hasText: /\(\d+ images?\)/ }).first();
  if (await imgCountEl2.isVisible().catch(() => false)) {
    console.log(`Image count: "${await imgCountEl2.textContent()}"`);
  }

  const allImgs = await page.locator("img").all();
  console.log(`\nAll <img> elements: ${allImgs.length}`);
  for (const img of allImgs) {
    const src = await img.getAttribute("src");
    const alt = await img.getAttribute("alt");
    const nw = await img.evaluate((el) => el.naturalWidth).catch(() => -1);
    const nh = await img.evaluate((el) => el.naturalHeight).catch(() => -1);
    const complete = await img.evaluate((el) => el.complete).catch(() => false);
    const status = nw > 0 ? "RENDERS OK" : "BROKEN (0x0)";
    console.log(`  [${status}] src="${src}" alt="${alt}" ${nw}x${nh} complete=${complete}`);
  }

  // ── FINAL SUMMARY ─────────────────────────────────────────────────────
  console.log("\n\n========== FINAL SUMMARY ==========\n");

  const errors = consoleMessages.filter((m) => m.type === "error" || m.type === "pageerror");
  const warnings = consoleMessages.filter((m) => m.type === "warning");

  console.log(`--- Console Errors (${errors.length}) ---`);
  errors.forEach((e) => console.log(`  [${e.type}] ${e.text}`));

  console.log(`\n--- Console Warnings (${warnings.length}) ---`);
  warnings.forEach((w) => console.log(`  [warning] ${w.text}`));

  console.log(`\n--- Network Errors / 4xx / 5xx (${networkErrors.length}) ---`);
  networkErrors.forEach((e) => console.log(`  ${e.method || "?"} ${e.url} => ${e.status || e.failure}`));

  console.log("\n--- All API Requests (localhost:8090) ---");
  networkRequests.forEach((r) => console.log(`  ${r.method} ${r.url} => ${r.status}`));

  console.log("\n--- Gallery Status ---");
  console.log(`  Before upload: ${galleryPanelVisible ? "OPENED" : "DID NOT OPEN"}`);
  console.log(`  After upload:  ${galleryPanelVisible2 ? "OPENED" : "DID NOT OPEN"}`);

  console.log(`\nScreenshots saved to: ${SCREENSHOTS_DIR}/`);

  await browser.close();
}

main().catch((err) => {
  console.error("Test failed:", err.message);
  console.error(err.stack);
  process.exit(1);
});
