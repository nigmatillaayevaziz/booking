import { createHash, timingSafeEqual } from "node:crypto";
import http from "node:http";

const MAX_BODY_BYTES = 1_000_000;

export function deriveWebhookSecret(token) {
  return createHash("sha256").update(`telegram-webhook:${token}`).digest("hex");
}

function secretsMatch(actual, expected) {
  const left = Buffer.from(String(actual ?? ""));
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw Object.assign(new Error("Payload too large"), { statusCode: 413 });
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export function createWebhookServer({ getBot, isReady, secret, logger = console }) {
  let queue = Promise.resolve();
  return http.createServer(async (request, response) => {
    response.setHeader("content-type", "application/json; charset=utf-8");
    if (request.method === "GET" && ["/", "/health"].includes(request.url)) {
      response.statusCode = isReady() ? 200 : 503;
      response.end(JSON.stringify({ ok: isReady(), service: "telegram-booking-bot" }));
      return;
    }
    if (request.method !== "POST" || request.url !== "/telegram/webhook") {
      response.statusCode = 404;
      response.end(JSON.stringify({ ok: false }));
      return;
    }
    if (!secretsMatch(request.headers["x-telegram-bot-api-secret-token"], secret)) {
      response.statusCode = 401;
      response.end(JSON.stringify({ ok: false }));
      return;
    }
    const bot = getBot();
    if (!isReady() || !bot) {
      response.statusCode = 503;
      response.end(JSON.stringify({ ok: false, retry: true }));
      return;
    }
    try {
      const update = await readJson(request);
      const task = queue.then(() => bot.handleUpdate(update));
      queue = task.catch(() => {});
      await task;
      response.statusCode = 200;
      response.end(JSON.stringify({ ok: true }));
    } catch (error) {
      logger.error("Webhook xatosi", error);
      response.statusCode = error?.statusCode ?? 500;
      response.end(JSON.stringify({ ok: false }));
    }
  });
}
