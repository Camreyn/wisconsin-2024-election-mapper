import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (key.startsWith("--")) {
    args.set(key.slice(2), process.argv[index + 1]);
    index += 1;
  }
}

const url = args.get("url");
const output = args.get("output");
const browserPath =
  args.get("browser") ||
  process.env.BROWSER_DOWNLOAD_BROWSER ||
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const timeoutMs = Number(args.get("timeout-ms") || 90000);
const headless = args.get("headless") !== "false";

if (!url || !output) {
  console.error("Usage: node scripts/browser-download.mjs --url URL --output PATH [--browser PATH] [--timeout-ms MS] [--headless false]");
  process.exit(2);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(targetUrl) {
  const response = await fetch(targetUrl);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${targetUrl}`);
  }
  return response.json();
}

async function waitForVersion(port, deadline) {
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      return await fetchJson(`http://127.0.0.1:${port}/json/version`);
    } catch (error) {
      lastError = error;
      await sleep(250);
    }
  }
  throw new Error(`Browser did not expose DevTools endpoint: ${lastError?.message || "timed out"}`);
}

function connect(wsUrl) {
  const socket = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();
  const listeners = [];

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message || JSON.stringify(message.error)));
      } else {
        resolve(message.result || {});
      }
      return;
    }
    for (const listener of listeners) {
      listener(message);
    }
  });

  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => {
      resolve({
        send(method, params = {}, sessionId = undefined) {
          const id = nextId;
          nextId += 1;
          const payload = { id, method, params };
          if (sessionId) {
            payload.sessionId = sessionId;
          }
          socket.send(JSON.stringify(payload));
          return new Promise((innerResolve, innerReject) => {
            pending.set(id, { resolve: innerResolve, reject: innerReject });
          });
        },
        onEvent(listener) {
          listeners.push(listener);
        },
        close() {
          socket.close();
        },
      });
    });
    socket.addEventListener("error", () => reject(new Error("WebSocket connection failed")));
  });
}

async function main() {
  const resolvedOutput = path.resolve(output);
  const downloadDir = path.dirname(resolvedOutput);
  fs.mkdirSync(downloadDir, { recursive: true });
  if (fs.existsSync(resolvedOutput)) {
    fs.rmSync(resolvedOutput);
  }

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "state-browser-download-"));
  const port = 9223 + Math.floor(Math.random() * 2000);
  const deadline = Date.now() + timeoutMs;
  const browserArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-component-update",
  ];
  if (headless) {
    browserArgs.push("--headless=new", "--disable-gpu");
  }
  browserArgs.push("about:blank");

  const browser = spawn(browserPath, browserArgs, { stdio: ["ignore", "ignore", "pipe"] });
  const stderr = [];
  browser.stderr.on("data", (chunk) => stderr.push(chunk.toString()));

  try {
    const version = await waitForVersion(port, deadline);
    const cdp = await connect(version.webSocketDebuggerUrl);
    const downloadPromise = new Promise((resolve, reject) => {
      cdp.onEvent((message) => {
        if (message.method === "Browser.downloadProgress" && message.params.state === "completed") {
          resolve(message.params);
        }
        if (message.method === "Browser.downloadProgress" && message.params.state === "canceled") {
          reject(new Error(`Browser download canceled: ${message.params.guid}`));
        }
      });
    });

    await cdp.send("Browser.setDownloadBehavior", {
      behavior: "allow",
      downloadPath: downloadDir,
      eventsEnabled: true,
    });
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Page.navigate", { url }, sessionId);

    await Promise.race([
      downloadPromise,
      sleep(Math.max(0, deadline - Date.now())).then(() => {
        throw new Error("Timed out waiting for browser download");
      }),
    ]);

    const candidates = fs
      .readdirSync(downloadDir)
      .map((name) => path.join(downloadDir, name))
      .filter((file) => file !== resolvedOutput && fs.statSync(file).isFile())
      .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);

    if (!candidates.length) {
      throw new Error("Browser reported a completed download, but no downloaded file was found");
    }
    fs.renameSync(candidates[0], resolvedOutput);
    cdp.close();
  } catch (error) {
    const tail = stderr.join("").split(/\r?\n/).slice(-10).join("\n");
    throw new Error(`${error.message}${tail ? `\nBrowser stderr:\n${tail}` : ""}`);
  } finally {
    browser.kill();
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true });
    } catch {
      // Best effort cleanup; Windows can hold browser profile files briefly.
    }
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
