import fs from "node:fs";
import path from "node:path";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (key.startsWith("--")) {
    const next = process.argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key.slice(2), "true");
    } else {
      args.set(key.slice(2), next);
      index += 1;
    }
  }
}

const state = args.get("state") || "";
const url = args.get("url") || "";
const htmlFile = args.get("html-file") || "";
const output = args.get("output") || "";
const summaryOnly = args.has("summary");

if (!url && !htmlFile) {
  console.error("Usage: node scripts/discover-state-sources.mjs --url URL [--html-file PATH] [--state CODE] [--output PATH]");
  process.exit(2);
}

function stripTags(value) {
  return String(value || "")
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function decodeHtml(value) {
  return String(value || "")
    .replace(/&amp;/g, "&")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, "\"")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function attributes(tag) {
  const attrs = {};
  for (const match of tag.matchAll(/([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
    attrs[match[1].toLowerCase()] = decodeHtml(match[3] ?? match[4] ?? match[5] ?? "");
  }
  return attrs;
}

function resolveUrl(candidate, baseUrl) {
  if (!candidate || candidate.startsWith("javascript:") || candidate.startsWith("#")) {
    return candidate || "";
  }
  try {
    return new URL(candidate, baseUrl || "https://example.invalid/").href;
  } catch {
    return candidate;
  }
}

function inferKind(candidate) {
  const text = candidate.toLowerCase();
  if (/\.(csv)(\?|#|$)/.test(text)) return "csv";
  if (/\.(xlsx|xls)(\?|#|$)/.test(text)) return "spreadsheet";
  if (/\.(zip)(\?|#|$)/.test(text)) return "zip";
  if (/\.(pdf)(\?|#|$)/.test(text)) return "pdf";
  if (/\.(txt|tsv)(\?|#|$)/.test(text)) return "text";
  if (/geojson|featureserver|mapserver|arcgis|tigerweb/.test(text)) return "geometry";
  if (/export|download|get[a-z0-9_]*file|resultsexport|voterturnout/.test(text)) return "export-endpoint";
  if (/\.(js)(\?|#|$)/.test(text)) return "script";
  if (/\.(css)(\?|#|$)/.test(text)) return "stylesheet";
  return "page";
}

function confidenceFor(candidate, context) {
  const text = `${candidate} ${context}`.toLowerCase();
  if (/\.(csv|xlsx|xls|zip|pdf|txt|tsv)(\?|#|$)/.test(text)) return "high";
  if (/export|download|get[a-z0-9_]*file|resultsexport/.test(text)) return "medium";
  if (/voterturnout|results|election|precinct|county/.test(text)) return "medium";
  return "low";
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const outputItems = [];
  for (const item of items) {
    const key = keyFn(item);
    if (seen.has(key)) continue;
    seen.add(key);
    outputItems.push(item);
  }
  return outputItems;
}

async function readHtml() {
  if (htmlFile) {
    return fs.readFileSync(htmlFile, "utf8");
  }
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 source-discovery",
    },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${url}`);
  }
  return response.text();
}

function collectLinkedResources(html, baseUrl) {
  const resources = [];
  const tagPatterns = [
    { tag: "a", attr: "href" },
    { tag: "script", attr: "src" },
    { tag: "link", attr: "href" },
    { tag: "iframe", attr: "src" },
  ];

  for (const pattern of tagPatterns) {
    const regex = new RegExp(`<${pattern.tag}\\b[^>]*>`, "gi");
    for (const match of html.matchAll(regex)) {
      const tag = match[0];
      const attrs = attributes(tag);
      const raw = attrs[pattern.attr];
      if (!raw) continue;
      resources.push({
        element: pattern.tag,
        text: stripTags(tag),
        rawUrl: raw,
        url: resolveUrl(raw, baseUrl),
        kind: inferKind(raw),
        confidence: confidenceFor(raw, tag),
      });
    }
  }

  const stringUrlPattern = /["']((?:https?:\/\/|\/|\.\/|\.\.\/)[^"']+\.(?:csv|xlsx?|zip|pdf|txt|tsv|json|geojson|aspx|ashx|php|js)(?:\?[^"']*)?)["']/gi;
  for (const match of html.matchAll(stringUrlPattern)) {
    const raw = decodeHtml(match[1]);
    resources.push({
      element: "script-string",
      text: "",
      rawUrl: raw,
      url: resolveUrl(raw, baseUrl),
      kind: inferKind(raw),
      confidence: confidenceFor(raw, ""),
    });
  }

  return uniqueBy(resources, (item) => `${item.element}:${item.url}`);
}

function collectForms(html, baseUrl) {
  const forms = [];
  for (const match of html.matchAll(/<form\b[^>]*>[\s\S]*?<\/form>/gi)) {
    const formHtml = match[0];
    const formAttrs = attributes(formHtml.match(/<form\b[^>]*>/i)?.[0] || "");
    const inputs = [];
    for (const inputMatch of formHtml.matchAll(/<(input|button|select)\b[^>]*>/gi)) {
      const attrs = attributes(inputMatch[0]);
      inputs.push({
        tag: inputMatch[1].toLowerCase(),
        type: attrs.type || "",
        name: attrs.name || "",
        id: attrs.id || "",
        value: attrs.value || "",
      });
    }
    forms.push({
      id: formAttrs.id || "",
      method: (formAttrs.method || "get").toUpperCase(),
      action: resolveUrl(formAttrs.action || baseUrl, baseUrl),
      hasViewState: inputs.some((input) => input.name === "__VIEWSTATE"),
      hiddenFields: inputs
        .filter((input) => input.type.toLowerCase() === "hidden")
        .map((input) => input.name || input.id)
        .filter(Boolean),
      submitControls: inputs
        .filter((input) => ["submit", "button", "image"].includes(input.type.toLowerCase()) || input.tag === "button")
        .map((input) => ({
          name: input.name,
          id: input.id,
          value: input.value,
        })),
    });
  }
  return forms;
}

function collectPostbacks(html) {
  return uniqueBy(
    [...html.matchAll(/__doPostBack\(&#39;([^&]+)&#39;,\s*&#39;([^&]*)&\#39;\)|__doPostBack\('([^']*)',\s*'([^']*)'\)/g)]
      .map((match) => ({
        target: decodeHtml(match[1] || match[3] || ""),
        argument: decodeHtml(match[2] || match[4] || ""),
      }))
      .filter((item) => item.target),
    (item) => `${item.target}:${item.argument}`,
  );
}

function likelyDownloads(resources, postbacks) {
  const linked = resources
    .filter((item) => ["csv", "spreadsheet", "zip", "pdf", "text", "geometry", "export-endpoint"].includes(item.kind))
    .map((item) => ({
      type: item.kind,
      url: item.url,
      source: item.element,
      confidence: item.confidence,
      note: item.rawUrl.startsWith("javascript:") ? "JavaScript/postback link; inspect form state or use browser download." : "",
    }));
  const postbackDownloads = postbacks
    .filter((item) => /export|download|result|turnout|file/i.test(item.target))
    .map((item) => ({
      type: "postback-export",
      url: "",
      source: item.target,
      confidence: "medium",
      note: "ASP.NET postback target; use a specialized postback downloader or browser automation.",
    }));
  return uniqueBy([...linked, ...postbackDownloads], (item) => `${item.type}:${item.url}:${item.source}`);
}

function summarize(report) {
  const hints = [];
  if (report.forms.some((form) => form.hasViewState)) {
    hints.push("ASP.NET viewstate form detected; direct downloads may need a postback downloader.");
  }
  if (report.likelyDownloads.some((item) => item.type === "zip")) {
    hints.push("ZIP candidate found; if it contains tabular lookup/vote files, try reviewCharts.format=tabDelimitedZipComparison.");
  }
  if (report.resources.some((item) => item.kind === "geometry")) {
    hints.push("Geometry candidate found; map it through the config geometry block.");
  }
  if (report.likelyDownloads.some((item) => item.note.includes("browser"))) {
    hints.push("Browser automation may be needed for JavaScript-triggered exports.");
  }
  return hints;
}

const html = await readHtml();
const baseUrl = url || (htmlFile ? `file://${path.resolve(htmlFile).replace(/\\/g, "/")}` : "");
const title = stripTags(html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1] || "");
const resources = collectLinkedResources(html, baseUrl);
const forms = collectForms(html, baseUrl);
const postbacks = collectPostbacks(html);
const report = {
  generatedAtUtc: new Date().toISOString(),
  state,
  input: {
    url,
    htmlFile,
  },
  page: {
    title,
    bytes: Buffer.byteLength(html, "utf8"),
  },
  resources,
  forms,
  postbacks,
  likelyDownloads: likelyDownloads(resources, postbacks),
};
report.pipelineHints = summarize(report);

const json = `${JSON.stringify(report, null, 2)}\n`;
const summary = {
  generatedAtUtc: report.generatedAtUtc,
  state: report.state,
  page: report.page,
  counts: {
    resources: report.resources.length,
    forms: report.forms.length,
    postbacks: report.postbacks.length,
    likelyDownloads: report.likelyDownloads.length,
  },
  likelyDownloads: report.likelyDownloads.slice(0, 12),
  pipelineHints: report.pipelineHints,
};
const body = summaryOnly ? `${JSON.stringify(summary, null, 2)}\n` : json;
if (output) {
  fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
  fs.writeFileSync(output, body, "utf8");
} else {
  process.stdout.write(body);
}
