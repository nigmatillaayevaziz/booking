import { showDateTime } from "./time.mjs";

export const STATUS_LABELS = Object.freeze({
  pending_price: "🟠 Operator narxini kutmoqda",
  quoted: "🟡 Sizning tasdig‘ingiz kutilmoqda",
  pending: "🟠 Operator tasdig‘ini kutmoqda",
  confirmed: "✅ Tasdiqlangan",
  cancelled: "⚪ Bekor qilingan",
  rejected: "❌ Rad etilgan",
});

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function money(value) {
  return `${Number(value).toLocaleString("uz-UZ")} so‘m`;
}

function priceText(value) {
  return Number(value) > 0 ? money(value) : "administrator bilan kelishiladi";
}

export function tripText(trip) {
  return [
    `📍 <b>${escapeHtml(trip.origin)} → ${escapeHtml(trip.destination)}</b>`,
    `🗓 Jo‘nash: <b>${showDateTime(trip.departure_at)}</b>`,
    `🚐 Transport: ${escapeHtml(trip.vehicle_name)}`,
    `💺 Bo‘sh joylar: <b>${trip.available_seats} ta</b>`,
    `💳 1 yo‘lovchi: <b>${priceText(trip.price)}</b>`,
  ].join("\n");
}

export function bookingText(booking) {
  return [
    `🎫 <b>Buyurtma ${escapeHtml(booking.code)}</b>`,
    STATUS_LABELS[booking.status] ?? escapeHtml(booking.status),
    "",
    `📍 <b>${escapeHtml(booking.origin)} → ${escapeHtml(booking.destination)}</b>`,
    `🗓 Jo‘nash: ${showDateTime(booking.departure_at)}`,
    `🚐 Transport: ${escapeHtml(booking.vehicle_name ?? "Buyurtma asosida")}`,
    `👤 Yo‘lovchi: ${escapeHtml(booking.passenger_name)}`,
    `📱 Telefon: ${escapeHtml(booking.phone)}`,
    `💺 Joylar: <b>${booking.seats} ta</b>`,
    `💳 Jami: <b>${priceText(booking.total_price)}</b>`,
  ].join("\n");
}
