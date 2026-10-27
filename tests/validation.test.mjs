import assert from "node:assert/strict";
import test from "node:test";

import { normalizeUzPhone, validatePassengerName } from "../src/validation.mjs";

test("Uzbek phone numbers are normalized consistently", () => {
  assert.equal(normalizeUzPhone("+998 90 123-45-67"), "+998901234567");
  assert.equal(normalizeUzPhone("998901234567"), "+998901234567");
  assert.equal(normalizeUzPhone("90 123 45 67"), "+998901234567");
});

test("foreign and malformed phone numbers are rejected", () => {
  assert.equal(normalizeUzPhone("+79991234567"), null);
  assert.equal(normalizeUzPhone("123"), null);
  assert.equal(normalizeUzPhone("phone"), null);
});

test("passenger names are trimmed and validated", () => {
  assert.equal(validatePassengerName("  Ali   Valiyev  "), "Ali Valiyev");
  assert.equal(validatePassengerName("<>"), null);
  assert.equal(validatePassengerName("12"), null);
});
