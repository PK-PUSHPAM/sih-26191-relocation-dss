export function reportToMarkdown(report) {
  const lines = [
    "# SIH 26191 Relocation Decision Report",
    "",
    `Run ID: ${report?.run_id ?? "Unavailable"}`,
    `Generated from backend report endpoint; frontend does not recalculate authoritative metrics.`,
    "",
    "## Report Data",
    "",
    "```json",
    JSON.stringify(report ?? {}, null, 2),
    "```",
  ];
  return lines.join("\n");
}

export function downloadMarkdown(report) {
  const blob = new Blob([reportToMarkdown(report)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `relocation-report-${report?.run_id ?? "unknown"}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function printReport(report) {
  const markdown = reportToMarkdown(report)
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>")
    .replace(/\n/g, "<br>");
  const popup = window.open("", "_blank", "noopener,noreferrer");
  if (!popup) return false;
  popup.document.write(`<!doctype html><html><head><title>Relocation Report</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.5}pre{white-space:pre-wrap}</style></head><body>${markdown}</body></html>`);
  popup.document.close();
  popup.focus();
  popup.print();
  return true;
}
