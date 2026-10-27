import fs from "node:fs";
import path from "node:path";

function loadDotEnv(filePath) {
  if (!fs.existsSync(filePath)) return;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator < 1) continue;
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

function booleanValue(value, fallback) {
  if (value == null || value === "") return fallback;
  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

export function loadConfig(rootDir = process.cwd()) {
  loadDotEnv(path.join(rootDir, ".env"));
  const token = (process.env.BOT_TOKEN ?? "").trim();
  if (!/^\d{8,12}:[A-Za-z0-9_-]{30,}$/.test(token)) {
    throw new Error("BOT_TOKEN topilmadi yoki noto‘g‘ri. .env fayliga BotFather bergan tokenni yozing.");
  }

  const adminIds = new Set(
    (process.env.ADMIN_IDS ?? "")
      .split(",")
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isSafeInteger(value) && value > 0),
  );
  if (adminIds.size === 0) throw new Error("ADMIN_IDS ichida kamida bitta Telegram ID bo‘lishi kerak.");

  const timeZone = (process.env.TIMEZONE ?? "Asia/Tashkent").trim();
  try {
    new Intl.DateTimeFormat("uz-UZ", { timeZone }).format(new Date());
  } catch {
    throw new Error(`TIMEZONE noto‘g‘ri: ${timeZone}`);
  }

  const mongoUri = (process.env.MONGODB_URI ?? "").trim();
  if (!/^mongodb(?:\+srv)?:\/\//i.test(mongoUri) || /<db_(?:username|password)>/.test(mongoUri)) {
    throw new Error("MONGODB_URI topilmadi yoki to‘liq sozlanmagan.");
  }
  const mongoDbName = (process.env.MONGODB_DB ?? "booking_bot").trim();
  if (!/^[A-Za-z0-9_-]{1,63}$/.test(mongoDbName)) {
    throw new Error("MONGODB_DB nomi noto‘g‘ri.");
  }
  const logLevel = (process.env.LOG_LEVEL ?? "info").toLowerCase();
  if (!["debug", "info", "warn", "error"].includes(logLevel)) {
    throw new Error("LOG_LEVEL debug, info, warn yoki error bo‘lishi kerak.");
  }
  const webhookBaseUrl = (process.env.WEBHOOK_URL ?? process.env.RENDER_EXTERNAL_URL ?? "").trim().replace(/\/$/, "");
  if (webhookBaseUrl && !/^https:\/\/[A-Za-z0-9.-]+(?::\d+)?(?:\/.*)?$/.test(webhookBaseUrl)) {
    throw new Error("WEBHOOK_URL HTTPS manzil bo‘lishi kerak.");
  }
  const port = Number(process.env.PORT ?? 10_000);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) throw new Error("PORT noto‘g‘ri.");

  return Object.freeze({
    token,
    adminIds,
    timeZone,
    mongoUri,
    mongoDbName,
    seedDemoData: booleanValue(process.env.SEED_DEMO_DATA, true),
    logLevel,
    pidPath: path.resolve(rootDir, process.env.PID_PATH ?? "data/bot.pid"),
    webhookBaseUrl,
    port,
    forcePolling: booleanValue(process.env.FORCE_POLLING, false),
  });
}
