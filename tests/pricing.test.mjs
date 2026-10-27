import assert from "node:assert/strict";
import test from "node:test";

import { calculateRouteFare } from "../src/pricing.mjs";

test("route fares are deterministic and symmetric", () => {
  assert.deepEqual(
    calculateRouteFare("Toshkent shahri", "Samarqand"),
    calculateRouteFare("Samarqand", "Toshkent shahri"),
  );
});

test("farther destinations cost more than nearby destinations", () => {
  const nearby = calculateRouteFare("Toshkent shahri", "Sirdaryo");
  const far = calculateRouteFare("Toshkent shahri", "Xorazm");

  assert.ok(far.distanceKm > nearby.distanceKm);
  assert.ok(far.unitPrice > nearby.unitPrice);
  assert.equal(far.unitPrice % 5_000, 0);
});

test("equal or unknown locations do not produce a fare", () => {
  assert.equal(calculateRouteFare("Navoiy", "Navoiy"), null);
  assert.equal(calculateRouteFare("Unknown", "Navoiy"), null);
});
