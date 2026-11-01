import { spawn } from "node:child_process";
import { createServer, request as createRequest } from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiPort = Number(process.env.FRESHFIRST_INTERNAL_API_PORT ?? 8001);
const ssrPort = Number(process.env.FRESHFIRST_INTERNAL_SSR_PORT ?? 3001);
const publicPort = Number(process.env.PORT ?? 8000);
const python = process.env.FRESHFIRST_PYTHON ?? "/opt/venv/bin/python";
const dataDirectory = path.resolve(process.env.FRESHFIRST_DATA_DIR ?? "/data");
const shuttingDown = { value: false };

for (const name of ["DATABASE_URL", "FRESHFIRST_AUTH_SECRET", "FRESHFIRST_TRUSTED_ORIGINS"]) {
  if (!process.env[name]) {
    console.error(`${name} must be set at container runtime.`);
    process.exit(1);
  }
}

if (Buffer.byteLength(process.env.FRESHFIRST_AUTH_SECRET, "utf8") < 32) {
  console.error("FRESHFIRST_AUTH_SECRET must contain at least 32 bytes.");
  process.exit(1);
}

const dataDirectoryUrl = dataDirectory.replaceAll("\\", "/").replace(/\/+$/, "");
if (!process.env.DATABASE_URL.startsWith(`sqlite:///${dataDirectoryUrl}/`)) {
  console.error("DATABASE_URL must point to a SQLite file under the configured data directory.");
  process.exit(1);
}

const api = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(apiPort)],
  { cwd: path.join(appRoot, "backend"), stdio: "inherit" },
);
const ssr = spawn(process.execPath, [".output/server/index.mjs"], {
  cwd: path.join(appRoot, "frontend"),
  env: {
    ...process.env,
    NITRO_HOST: "127.0.0.1",
    NITRO_PORT: String(ssrPort),
    PORT: String(ssrPort),
  },
  stdio: "inherit",
});

const children = [api, ssr];

function stop(code = 0) {
  if (shuttingDown.value) return;
  shuttingDown.value = true;
  if (server.listening) server.close();
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill("SIGTERM");
  }
  const forceStop = setTimeout(() => {
    for (const child of children) {
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
    }
  }, 5000);
  forceStop.unref();
  process.exitCode = code;
}

for (const child of children) {
  child.once("error", (error) => {
    console.error("Failed to start a required FreshFirst server.", error);
    stop(1);
  });
  child.once("exit", (code, signal) => {
    if (!shuttingDown.value) {
      console.error(`A required FreshFirst server exited (code=${code}, signal=${signal}).`);
      stop(code ?? 1);
    }
  });
}

function proxy(request, response, destinationPort) {
  const headers = { ...request.headers, host: `127.0.0.1:${destinationPort}` };
  headers["x-forwarded-host"] = request.headers.host ?? "";
  headers["x-forwarded-proto"] = "http";
  const upstream = createRequest(
    {
      hostname: "127.0.0.1",
      port: destinationPort,
      method: request.method,
      path: request.url,
      headers,
    },
    (upstreamResponse) => {
      response.writeHead(upstreamResponse.statusCode ?? 502, upstreamResponse.headers);
      upstreamResponse.pipe(response);
    },
  );
  upstream.once("error", () => {
    if (!response.headersSent) {
      response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
      response.end("FreshFirst service is unavailable.");
    } else {
      response.destroy();
    }
  });
  request.pipe(upstream);
}

const server = createServer((request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  if (pathname === "/healthz") {
    void healthCheck().then((healthy) => {
      response.writeHead(healthy ? 200 : 503, { "content-type": "text/plain; charset=utf-8" });
      response.end(healthy ? "ok" : "unavailable");
    });
    return;
  }
  proxy(request, response, pathname === "/api" || pathname.startsWith("/api/") ? apiPort : ssrPort);
});

async function healthCheck() {
  try {
    const [apiResponse, webResponse] = await Promise.all([
      fetch(`http://127.0.0.1:${apiPort}/api/ingredients`, {
        signal: AbortSignal.timeout(2500),
      }),
      fetch(`http://127.0.0.1:${ssrPort}/`, { signal: AbortSignal.timeout(2500) }),
    ]);
    return apiResponse.ok && webResponse.ok;
  } catch {
    return false;
  }
}

server.once("error", (error) => {
  console.error("Failed to bind FreshFirst's public port.", error);
  stop(1);
});
server.listen(publicPort, "0.0.0.0");
process.once("SIGTERM", () => stop());
process.once("SIGINT", () => stop());
