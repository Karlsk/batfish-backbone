import { expect, type Page, type TestInfo } from "@playwright/test";
import { readFileSync } from "node:fs";
export async function verifyDownloads(
  page: Page,
  testInfo: TestInfo,
  kind: "table" | "traces",
) {
  const resultId = new URL(page.url()).pathname.split("/").pop()!;
  const metadata = await (
    await page.request.get(`/api/v1/results/${resultId}`)
  ).json();
  const formats = kind === "table" ? ["json", "csv"] : ["json"];
  for (const format of formats) {
    const pending = page.waitForEvent("download");
    await page
      .getByRole("button", {
        name: `下载 ${format.toUpperCase()}`,
        exact: true,
      })
      .click();
    const download = await pending;
    expect(download.suggestedFilename()).toBe(`batfish-${resultId}.${format}`);
    const file = testInfo.outputPath(`download-${resultId}.${format}`);
    await download.saveAs(file);
    expect(await download.failure()).toBeNull();
    const text = readFileSync(file, "utf8");
    if (format === "json") {
      const value = JSON.parse(text);
      expect(value.metadata).toEqual(metadata);
      expect(
        value.data[kind === "table" ? "rows" : "flows"].length,
      ).toBeGreaterThan(0);
      if (kind === "traces")
        expect(value.data.flows[0].traces[0].disposition).toBeTruthy();
    } else {
      expect(text).toContain("record_type,metadata_json,data:");
      expect(text).toContain(resultId);
      expect(text).toContain(metadata.context.snapshot_id);
      expect(text).toContain("data,,");
    }
  }
  if (kind === "traces")
    await expect(
      page.getByRole("button", { name: "下载 CSV", exact: true }),
    ).toHaveCount(0);
  await page
    .getByRole("button", { name: "下载 JSON", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath(`${kind}-export.png`),
    animations: "disabled",
  });
}
