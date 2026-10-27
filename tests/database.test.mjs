import assert from "node:assert/strict";
import test from "node:test";

import { BookingError, Database } from "../src/database.mjs";

function validator(now = "2026-10-26T19:00:00") {
  const database = Object.create(Database.prototype);
  database.now = () => now;
  return database;
}

test("custom booking validation accepts a future interregional trip", () => {
  assert.doesNotThrow(() => validator().validateBooking(
    "Toshkent shahri", "Samarqand", "2026-10-27T09:15:00", 3,
  ));
});

test("custom booking validation rejects equal locations", () => {
  assert.throws(
    () => validator().validateBooking("Navoiy", " navoiy ", "2026-10-27T09:15:00", 1),
    BookingError,
  );
});

test("custom booking validation rejects an expired departure", () => {
  assert.throws(
    () => validator().validateBooking("Navoiy", "Xorazm", "2026-10-26T18:59:59", 1),
    /kelajakda/,
  );
});

test("custom booking validation enforces the 1-10 seat limit", () => {
  assert.throws(
    () => validator().validateBooking("Navoiy", "Xorazm", "2026-10-27T09:15:00", 11),
    /1–10/,
  );
});
