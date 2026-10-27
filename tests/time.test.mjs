import assert from "node:assert/strict";
import test from "node:test";

import { parsePassengerDateTime } from "../src/time.mjs";

const NOW = "2026-10-27T09:00:00";

test("passenger date accepts natural Uzbek formats", () => {
  assert.equal(parsePassengerDateTime("17-yanvar soat 17:05", NOW, 100), "2027-01-17T17:05:00");
  assert.equal(parsePassengerDateTime("29 oktabr 18:30", NOW), "2026-10-29T18:30:00");
  assert.equal(parsePassengerDateTime("29.10.2026 18:30", NOW), "2026-10-29T18:30:00");
  assert.equal(parsePassengerDateTime("29-10-26 soat 18:30", NOW), "2026-10-29T18:30:00");
});

test("passenger date rejects invalid, past and overly distant values", () => {
  assert.equal(parsePassengerDateTime("31-fevral soat 17:05", NOW), null);
  assert.equal(parsePassengerDateTime("26.10.2026 18:30", NOW), null);
  assert.equal(parsePassengerDateTime("17-yanvar soat 17:05", NOW), null);
  assert.equal(parsePassengerDateTime("29 oktabr 25:00", NOW), null);
});
