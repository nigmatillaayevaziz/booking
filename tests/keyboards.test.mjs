import assert from "node:assert/strict";
import test from "node:test";

import { calendarKeyboard, hoursKeyboard, mainMenu, minutesKeyboard, regionsKeyboard } from "../src/keyboards.mjs";
import { REGIONS } from "../src/locations.mjs";

const buttons = (keyboard) => keyboard.inline_keyboard.flat();

test("all Uzbekistan regions are available and the origin is excluded from destinations", () => {
  assert.equal(REGIONS.length, 14);
  assert.equal(
    buttons(regionsKeyboard(REGIONS, "origin")).filter((button) => button.callback_data.startsWith("origin:")).length,
    14,
  );

  const destinations = buttons(regionsKeyboard(REGIONS, "destination", 7));
  assert.equal(destinations.filter((button) => button.callback_data.startsWith("destination:")).length, 13);
  assert.equal(destinations.some((button) => button.text === "Navoiy"), false);
});

test("main menu is compact, understandable and role-aware", () => {
  const passenger = mainMenu(false).keyboard.flat().map((button) => button.text);
  assert.deepEqual(passenger, [
    "🧳 Safarni band qilish",
    "📋 Buyurtmalarim",
    "🗺 Yo‘nalishlar va narxlar",
    "🆘 Yordam",
  ]);
  assert.equal(mainMenu(true).keyboard.at(-1)[0].text, "🛠 Boshqaruv paneli");
});

test("calendar allows future dates and month navigation", () => {
  const calendar = buttons(calendarKeyboard(2026, 10, "2026-10-26"));
  assert.equal(calendar.some((button) => button.callback_data === "caldate:2026-10-29"), true);
  assert.equal(calendar.some((button) => button.callback_data === "caldate:2026-10-01"), false);
  assert.equal(calendar.some((button) => button.callback_data === "calnav:2026-11"), true);
});

test("customers can choose any hour and a quarter-hour minute", () => {
  assert.equal(buttons(hoursKeyboard()).filter((button) => button.callback_data.startsWith("hour:")).length, 24);
  assert.deepEqual(
    buttons(minutesKeyboard()).filter((button) => button.callback_data.startsWith("minute:")).map((button) => button.text),
    ["00", "15", "30", "45"],
  );
});

test("selection screens always expose cancellation", () => {
  for (const keyboard of [
    regionsKeyboard(REGIONS, "origin"),
    calendarKeyboard(2026, 10, "2026-10-26"),
    hoursKeyboard(),
    minutesKeyboard(),
  ]) {
    assert.equal(buttons(keyboard).some((button) => button.callback_data === "booking:abort"), true);
  }
});
