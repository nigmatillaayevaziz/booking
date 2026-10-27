import assert from "node:assert/strict";
import test from "node:test";

import { createWebhookServer, deriveWebhookSecret } from "../src/webhook.mjs";

async function listen(server) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return `http://127.0.0.1:${server.address().port}`;
}

test("webhook health and Telegram secret validation work", async (context) => {
  const updates = [];
  const secret = deriveWebhookSecret("123456789:example-token-value");
  const server = createWebhookServer({
    getBot: () => ({ handleUpdate: async (update) => updates.push(update) }),
    isReady: () => true,
    secret,
    logger: { error() {} },
  });
  context.after(() => server.close());
  const baseUrl = await listen(server);

  assert.equal((await fetch(`${baseUrl}/health`)).status, 200);
  assert.equal((await fetch(`${baseUrl}/telegram/webhook`, {
    method: "POST", headers: { "content-type": "application/json" }, body: "{}",
  })).status, 401);
  const response = await fetch(`${baseUrl}/telegram/webhook`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-telegram-bot-api-secret-token": secret },
    body: JSON.stringify({ update_id: 42 }),
  });
  assert.equal(response.status, 200);
  assert.deepEqual(updates, [{ update_id: 42 }]);
});

test("health endpoint reports startup readiness", async (context) => {
  const server = createWebhookServer({
    getBot: () => null,
    isReady: () => false,
    secret: deriveWebhookSecret("token"),
    logger: { error() {} },
  });
  context.after(() => server.close());
  const baseUrl = await listen(server);
  assert.equal((await fetch(`${baseUrl}/`)).status, 503);
});
