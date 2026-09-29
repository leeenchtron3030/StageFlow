import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { NextRequest } from "next/server.js";
import { proxy as middleware, config } from "../../proxy.ts";
import * as proxyModule from "../../proxy.ts";
import { isAllowedUiHost } from "./ui-host-policy.server.ts";

const originalPort = process.env.PORT;
const originalHosts = process.env.STAGEFLOW_UI_ALLOWED_HOSTS;
afterEach(() => {
  if (originalPort === undefined) delete process.env.PORT; else process.env.PORT = originalPort;
  if (originalHosts === undefined) delete process.env.STAGEFLOW_UI_ALLOWED_HOSTS; else process.env.STAGEFLOW_UI_ALLOWED_HOSTS = originalHosts;
});

test("all loopback aliases use the actual server port, with exact optional LAN authorities", () => {
  for (const port of ["3000", "3001", "4173", "65535"]) {
    for (const host of ["localhost", "127.0.0.1", "[::1]"]) {
      assert.equal(isAllowedUiHost(`${host}:${port}`, port), true);
      assert.equal(isAllowedUiHost(`${host}:9999`, port), false);
    }
  }
  for (const host of ["producer.lan:3000", "192.168.1.20:4173", "[fd00::1]:3000"]) {
    assert.equal(isAllowedUiHost(host, "3000", ` , ${host}, `), true);
    assert.equal(isAllowedUiHost(host, "3000"), false);
  }
  assert.equal(isAllowedUiHost("PRODUCER.lan:3000", "3000", "producer.lan:3000"), true);
  assert.equal(isAllowedUiHost("producer.lan:3001", "3000", "producer.lan:3000"), false);
  assert.equal(isAllowedUiHost("sub.producer.lan:3000", "3000", "producer.lan:3000"), false);
});

test("untrusted or malformed hosts and invalid server ports fail closed", () => {
  for (const host of [null, "", "evil.example:3000", "localhost:3001", "127.0.0.2:3000", "127.1:3000", "2130706433:3000", "localhost", "localhost.:3000", "localhost:03000", "localhost:0", "localhost:65536", "localhost:3000,evil.example:3000", "localhost:3000@evil.example", "http://localhost:3000", " localhost:3000", "localhost:3000/", "[::1%lo]:3000"]) {
    assert.equal(isAllowedUiHost(host, "3000"), false, String(host));
  }
  for (const port of [undefined, "", "0", "3000x", "03000", "65536"]) {
    assert.equal(isAllowedUiHost("localhost:3000", port, "localhost:3000"), false);
  }
});

test("malformed configured entries grant no access and cannot widen valid entries", () => {
  for (const entry of ["*", "*.example:3000", "http://evil.example:3000", "evil.example", "evil.example:0", "evil.example:65536", "evil.example:03000", "evil.example:3000/path", "user@evil.example:3000", "evil.example:3000?x", "evil.example:3000#x", "evil..example:3000", "-evil.example:3000", "[:::]:3000"]) {
    const configured = `${entry}, producer.lan:3000`;
    assert.equal(isAllowedUiHost("evil.example:3000", "3000", configured), false, entry);
    assert.equal(isAllowedUiHost("producer.lan:3000", "3000", configured), true);
  }
});

test("middleware guards pages, all capability routes and static assets with empty 421 responses", async () => {
  process.env.PORT = "4173";
  process.env.STAGEFLOW_UI_ALLOWED_HOSTS = "producer.lan:4173";
  assert.deepEqual(config, { matcher: "/:path*" });
  assert.equal(Object.hasOwn(proxyModule, "runtime"), false);
  for (const path of ["/", "/sessions/example", "/api/stageflow/demo/sessions/start", "/api/stageflow/assembly/templates", "/api/stageflow/rendering/requests", "/api/stageflow/editorial/events/example/phrase-lists", "/api/stageflow/media-timing/assets/example/latest", "/_next/static/chunks/app.js", "/favicon.ico"]) {
    for (const method of ["GET", "POST", "HEAD", "OPTIONS"]) {
      for (const host of ["localhost:4173", "127.0.0.1:4173", "[::1]:4173", "producer.lan:4173", "evil.example:4173", "localhost:3000", null]) {
        const headers = new Headers({ "x-forwarded-host": "localhost:4173", "x-forwarded-port": "4173", "origin": "http://localhost:4173", "next-router-prefetch": "1" });
        if (host !== null) headers.set("host", host);
        const response = middleware(new NextRequest(`http://localhost:4173${path}`, { headers, method }));
        const allowed = host !== null && ["localhost:4173", "127.0.0.1:4173", "[::1]:4173", "producer.lan:4173"].includes(host);
        assert.equal(response.status, allowed ? 200 : 421, `${method} ${path} ${host}`);
        assert.equal(response.headers.get("x-middleware-next"), allowed ? "1" : null);
        assert.equal(await response.text(), "");
      }
    }
  }
  process.env.PORT = "3001";
  assert.equal(middleware(new NextRequest("http://evil.example:4173/", { headers: { host: "localhost:3001" } })).status, 200);
  delete process.env.PORT;
  assert.equal(middleware(new NextRequest("http://localhost:4173/", { headers: { host: "localhost:4173" } })).status, 421);
});
