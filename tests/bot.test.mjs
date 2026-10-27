import assert from "node:assert/strict";
import test from "node:test";

import { TicketBot } from "../src/bot.mjs";
import { REGIONS } from "../src/locations.mjs";

const booking = (overrides = {}) => ({
  id: 7, code: "ABCDEFGH", user_id: 100, type: "custom",
  origin: "Navoiy", destination: "Xorazm", departure_at: "2026-10-28T09:15:00",
  vehicle_name: "Buyurtma asosida", passenger_name: "Test User", phone: "+998901234567",
  seats: 2, total_price: 0, status: "pending_price", ...overrides,
});

class FakeTelegram {
  constructor() { this.calls = []; }
  async send(chatId, text, markup) { this.calls.push({ method: "send", chatId, text, markup }); return {}; }
  async edit(chatId, messageId, text, markup) { this.calls.push({ method: "edit", chatId, messageId, text, markup }); return {}; }
  async answer(id, text, alert) { this.calls.push({ method: "answer", id, text, alert }); return {}; }
  close() {}
}

class FakeDatabase {
  constructor() {
    this.sessions = new Map();
    this.notifications = [];
    this.created = null;
  }
  now() { return "2026-10-26T19:00:00"; }
  async upsertUser() {}
  async getSession(id) { return this.sessions.get(id) ?? null; }
  async setSession(id, value) { this.sessions.set(id, value); }
  async deleteSession(id) { this.sessions.delete(id); }
  async listOrigins() { return []; }
  async listRouteCatalog() { return []; }
  async getRoutePrice() { return { distanceKm: 310, unitPrice: 205000, source: "distance" }; }
  async setPhone() {}
  async createCustomBooking(value) {
    this.created = value;
    return booking({ status: "pending", unit_price: 205000, total_price: 410000 });
  }
  async createBooking(value) { this.created = value; return booking({ type: "scheduled", status: "pending", total_price: 240000 }); }
  async cancelBooking(id, userId) { this.cancelled = { id, userId }; return this.cancelAllowed ?? false; }
  async acceptQuote() { return true; }
  async rejectQuote() { return true; }
  async getBooking() { return booking({ status: "confirmed", total_price: 450000 }); }
  async quoteBooking(id, price) { this.quote = { id, price }; return true; }
  async enqueueNotification(chatId, text, markup) { this.notifications.push({ chatId, text, markup }); }
  async listNotifications() { return []; }
}

function fixture(adminIds = [999]) {
  const telegram = new FakeTelegram();
  const database = new FakeDatabase();
  const bot = new TicketBot({
    telegram, database,
    config: { adminIds: new Set(adminIds) },
    logger: { info() {}, warn() {}, error() {} },
  });
  return { bot, telegram, database };
}

test("booking menu offers an individual order when no scheduled trips exist", async () => {
  const { bot, telegram } = fixture();
  await bot.handleMessage({ from: { id: 100, first_name: "Test" }, chat: { id: 100 }, text: "🎫 Chipta buyurtma qilish" });
  const button = telegram.calls.at(-1).markup.inline_keyboard.flat().find((item) => item.callback_data === "booking:custom");
  assert.equal(button.text, "🚖 Shaxsiy safar buyurtmasi");
});

test("destination selection shows a predetermined route fare and asks for typed date-time", async () => {
  const { bot, telegram, database } = fixture();
  const originIndex = REGIONS.indexOf("Toshkent shahri");
  const destinationIndex = REGIONS.indexOf("Samarqand");
  await database.setSession(100, {
    step: "booking:destination", mode: "custom", originIndex, origin: REGIONS[originIndex],
  });

  await bot.handleUserCallback(
    { id: "price1", from: { id: 100 } },
    `destination:${destinationIndex}`,
    100,
    9,
  );

  const session = await database.getSession(100);
  assert.equal(session.step, "booking:datetime");
  assert.equal(session.unitPrice, 205000);
  assert.match(telegram.calls.find((call) => call.method === "edit").text, /205[\s\u00a0]?000 so‘m/);
  assert.match(telegram.calls.find((call) => call.method === "send").text, /17-noyabr soat 17:05/);
  assert.equal(
    telegram.calls.some((call) => call.markup?.inline_keyboard?.flat().some((button) => button.callback_data?.startsWith("hour:"))),
    false,
  );
});

test("typed Uzbek date-time continues directly to seat selection", async () => {
  const { bot, telegram, database } = fixture();
  await database.setSession(100, {
    step: "booking:datetime", mode: "custom", origin: "Toshkent shahri", destination: "Samarqand",
    distanceKm: 310, unitPrice: 205000,
  });

  await bot.handleMessage({
    from: { id: 100, first_name: "Test" }, chat: { id: 100 }, text: "29-oktabr soat 17:05",
  });

  const session = await database.getSession(100);
  assert.equal(session.step, "booking:seats");
  assert.equal(session.departureAt, "2026-10-29T17:05:00");
  assert.match(telegram.calls.at(-1).text, /4\/5 · Nechta joy kerak/);
});

test("custom confirmation creates a custom booking and notifies admins", async () => {
  const { bot, telegram, database } = fixture();
  await database.setSession(100, {
    step: "booking:confirm", mode: "custom", origin: "Navoiy", destination: "Xorazm",
    departureAt: "2026-10-28T09:15:00", seats: 2, passengerName: "Test User", phone: "+998901234567",
  });
  await bot.handleUserCallback({ id: "q1", from: { id: 100 } }, "booking:confirm", 100, 10);
  assert.equal(database.created.origin, "Navoiy");
  assert.equal(await database.getSession(100), null);
  assert.equal(telegram.calls.some((call) => call.chatId === 999 && call.text.includes("Yangi buyurtma")), true);
});

test("scheduled confirmation reserves the selected trip", async () => {
  const { bot, database } = fixture();
  await database.setSession(100, {
    step: "booking:confirm", mode: "scheduled", tripId: 12, seats: 1,
    passengerName: "Test User", phone: "+998901234567",
  });
  await bot.handleUserCallback({ id: "q2", from: { id: 100 } }, "booking:confirm", 100, 11);
  assert.equal(database.created.tripId, 12);
});

test("admin price input stores the quote and sends customer approval buttons", async () => {
  const { bot, telegram, database } = fixture();
  await bot.handleAdminInput(
    { from: { id: 999 }, chat: { id: 999 }, text: "450 000" },
    { step: "admin:quote_price", bookingId: 7 },
  );
  assert.deepEqual(database.quote, { id: 7, price: 450000 });
  const customerMessage = telegram.calls.find((call) => call.chatId === 100);
  assert.equal(customerMessage.markup.inline_keyboard[0][0].callback_data, "quote:accept:7");
});

test("customer can accept an administrator quote", async () => {
  const { bot, telegram } = fixture();
  await bot.handleUserCallback({ id: "q3", from: { id: 100 } }, "quote:accept:7", 100, 12);
  assert.equal(telegram.calls.some((call) => call.method === "edit" && call.text.includes("Tasdiqlangan")), true);
  assert.equal(telegram.calls.some((call) => call.chatId === 999 && call.text.includes("qabul qildi")), true);
});

test("an expired or otherwise invalid cancellation is rejected", async () => {
  const { bot, telegram } = fixture();
  await bot.handleUserCallback({ id: "q4", from: { id: 100 } }, "cancel:7", 100, 13);
  const answer = telegram.calls.find((call) => call.method === "answer");
  assert.equal(answer.alert, true);
  assert.match(answer.text, /safar boshlangan/);
});

test("cancellation requires a second explicit confirmation", async () => {
  const { bot, telegram, database } = fixture();

  await bot.handleUserCallback({ id: "q5", from: { id: 100 } }, "cancel:ask:7", 100, 14);

  assert.equal(database.cancelled, undefined);
  const preview = telegram.calls.find((call) => call.method === "edit");
  assert.match(preview.text, /bekor qilmoqchimisiz/);
  assert.equal(preview.markup.inline_keyboard[1][0].callback_data, "cancel:confirm:7");

  database.cancelAllowed = true;
  await bot.handleUserCallback({ id: "q6", from: { id: 100 } }, "cancel:confirm:7", 100, 14);
  assert.deepEqual(database.cancelled, { id: 7, userId: 100 });
  assert.equal(telegram.calls.some((call) => call.method === "edit" && call.text.includes("bekor qilindi")), true);
});

test("route catalog explains when scheduled trips are unavailable", async () => {
  const { bot, telegram } = fixture();

  await bot.showRouteCatalog(100);

  assert.match(telegram.calls.at(-1).text, /sotuvdagi tayyor reyslar yo‘q/);
  assert.equal(telegram.calls.at(-1).markup.inline_keyboard[0][0].callback_data, "booking:start");
});
