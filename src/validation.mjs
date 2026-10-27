const UZ_PHONE = /^\+998\d{9}$/;

export function normalizeUzPhone(value) {
  let phone = String(value ?? "").replace(/[\s()\-]/g, "");
  if (/^998\d{9}$/.test(phone)) phone = `+${phone}`;
  else if (/^\d{9}$/.test(phone)) phone = `+998${phone}`;
  if (!UZ_PHONE.test(phone)) return null;
  return phone;
}

export function validatePassengerName(value) {
  const name = String(value ?? "").trim().replace(/\s+/g, " ");
  if (name.length < 3 || name.length > 100) return null;
  if (!/[\p{L}]/u.test(name) || /[<>]/.test(name)) return null;
  return name;
}
