import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import { TicketBot } from "./bot.mjs";
import { loadConfig } from "./config.mjs";
import { Database } from "./database.mjs";
import { Telegram } from "./telegram.mjs";

const rootDir = process.cwd();
const levels = { debug: 10, info: 20, warn: 30, error: 40 };
function createLogger(minimumLevel) {
  const enabled = (level) => levels[level] >= levels[minimumLevel];
  return {
    debug: (...items) => enabled("debug") && console.debug(new Date().toISOString(), "DEBUG", ...items),
    info: (...items) => enabled("info") && console.log(new Date().toISOString(), "INFO", ...items),
    warn: (...items) => enabled("warn") && console.warn(new Date().toISOString(), "WARN", ...items),
    error: (...items) => enabled("error") && console.error(new Date().toISOString(), "ERROR", ...items),
  };
}

let database;
let bot;
let pidPath;
let logger = createLogger("info");

try {
  const config = loadConfig(rootDir);
  logger = createLogger(config.logLevel);
  database = await Database.connect(config.mongoUri, config.mongoDbName, config.timeZone);
  logger.info(`MongoDB bazasiga ulandi: ${config.mongoDbName}`);
  if (config.seedDemoData) await database.seedDemoData();

  pidPath = config.pidPath;
  fs.mkdirSync(path.dirname(pidPath), { recursive: true });
  fs.writeFileSync(pidPath, String(process.pid), "utf8");

  const telegram = new Telegram(config.token, logger);
  bot = new TicketBot({ telegram, database, config, logger });
  await bot.initialize();

  const shutdown = (signal) => {
    logger.info(`${signal} olindi, bot to‘xtatilmoqda`);
    bot.stop();
  };
  process.once("SIGINT", () => shutdown("SIGINT"));
  process.once("SIGTERM", () => shutdown("SIGTERM"));
  await bot.run();
} catch (error) {
  logger.error("Bot ishga tushmadi:", error?.message ?? error);
  process.exitCode = 1;
} finally {
  try { await database?.close(); } catch {}
  try { if (pidPath && fs.existsSync(pidPath)) fs.unlinkSync(pidPath); } catch {}
}
