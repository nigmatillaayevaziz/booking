const inline = (inline_keyboard) => ({ inline_keyboard });
const cancelRow = [{ text: "❌ Jarayonni bekor qilish", callback_data: "booking:abort" }];

export const bookingTypeKeyboard = (hasScheduledTrips) => inline([
  ...(hasScheduledTrips ? [[{ text: "🚌 Tayyor reysdan joy band qilish", callback_data: "booking:scheduled" }]] : []),
  [{ text: "🚖 Shaxsiy safar buyurtmasi", callback_data: "booking:custom" }],
  [
    { text: "🗺 Yo‘nalishlar", callback_data: "catalog:routes" },
    { text: "❌ Yopish", callback_data: "booking:abort" },
  ],
]);

export function mainMenu(isAdmin = false) {
  const keyboard = [
    [{ text: "🧳 Safarni band qilish" }, { text: "📋 Buyurtmalarim" }],
    [{ text: "🗺 Yo‘nalishlar va narxlar" }, { text: "🆘 Yordam" }],
  ];
  if (isAdmin) keyboard.push([{ text: "🛠 Boshqaruv paneli" }]);
  return { keyboard, resize_keyboard: true, is_persistent: true, input_field_placeholder: "Kerakli bo‘limni tanlang" };
}

export const removeKeyboard = { remove_keyboard: true };
export const phoneKeyboard = {
  keyboard: [
    [{ text: "📱 Telefon raqamimni yuborish", request_contact: true }],
    [{ text: "⬅️ Orqaga" }, { text: "❌ Bekor qilish" }],
  ],
  resize_keyboard: true,
  one_time_keyboard: true,
  input_field_placeholder: "+998 90 123 45 67",
};

export const inputNavigationKeyboard = {
  keyboard: [[{ text: "⬅️ Orqaga" }, { text: "❌ Bekor qilish" }]],
  resize_keyboard: true,
  one_time_keyboard: false,
  input_field_placeholder: "Ma’lumotni kiriting",
};

export const resumeKeyboard = () => inline([[
  { text: "▶️ Davom ettirish", callback_data: "session:resume" },
  { text: "🔄 Qaytadan boshlash", callback_data: "session:restart" },
]]);

export const originsKeyboard = (items) => inline([
  ...chunk(items.map((item) => ({ text: item.origin, callback_data: `scheduled_origin:${item.route_id}` })), 2),
  [{ text: "⬅️ Orqaga", callback_data: "booking:start" }],
  cancelRow,
]);

export const regionsKeyboard = (regions, prefix, excludedIndex = -1) => inline([
  ...chunk(regions.flatMap((name, index) => index === excludedIndex ? [] : [{
    text: name,
    callback_data: `${prefix}:${index}`,
  }]), 2),
  ...(prefix === "destination"
    ? [[{ text: "⬅️ Orqaga", callback_data: "booking:custom" }]]
    : [[{ text: "⬅️ Orqaga", callback_data: "booking:start" }]]),
  cancelRow,
]);

export function calendarKeyboard(year, month, todayIso) {
  const monthNames = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
  ];
  const firstDay = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const rows = [
    [{ text: `📅 ${monthNames[month - 1]} ${year}`, callback_data: "noop" }],
    ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"].map((text) => ({ text, callback_data: "noop" })),
  ];
  let row = Array(firstDay).fill({ text: " ", callback_data: "noop" });
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    row.push({ text: iso < todayIso ? "·" : String(day), callback_data: iso < todayIso ? "noop" : `caldate:${iso}` });
    if (row.length === 7) { rows.push(row); row = []; }
  }
  if (row.length) rows.push([...row, ...Array(7 - row.length).fill({ text: " ", callback_data: "noop" })]);

  const currentMonth = todayIso.slice(0, 7);
  const shownMonth = `${year}-${String(month).padStart(2, "0")}`;
  const previous = new Date(Date.UTC(year, month - 2, 1));
  const next = new Date(Date.UTC(year, month, 1));
  rows.push([
    shownMonth > currentMonth
      ? { text: "⬅️", callback_data: `calnav:${previous.getUTCFullYear()}-${String(previous.getUTCMonth() + 1).padStart(2, "0")}` }
      : { text: " ", callback_data: "noop" },
    { text: "⬅️ Manzillar", callback_data: "booking:destinations" },
    { text: "➡️", callback_data: `calnav:${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, "0")}` },
  ]);
  rows.push(cancelRow);
  return inline(rows);
}

export const hoursKeyboard = (minimumHour = 0) => inline([
  ...chunk(Array.from({ length: 24 }, (_, hour) => hour)
    .filter((hour) => hour >= minimumHour)
    .map((hour) => ({ text: `${String(hour).padStart(2, "0")}:00`, callback_data: `hour:${hour}` })), 4),
  [{ text: "⬅️ Sanaga qaytish", callback_data: "booking:calendar" }],
  cancelRow,
]);

export const minutesKeyboard = (minimumMinute = 0) => inline([
  [0, 15, 30, 45].filter((minute) => minute >= minimumMinute).map((minute) => ({
    text: String(minute).padStart(2, "0"), callback_data: `minute:${minute}`,
  })) ,
  [{ text: "⬅️ Soatga qaytish", callback_data: "booking:hours" }],
  cancelRow,
]);

export const customSeatsKeyboard = () => inline([
  ...chunk(Array.from({ length: 10 }, (_, index) => ({
    text: String(index + 1), callback_data: `customseats:${index + 1}`,
  })), 5),
  [{ text: "⬅️ Sana-vaqtni o‘zgartirish", callback_data: "booking:datetime_input" }],
  cancelRow,
]);

export const destinationsKeyboard = (items) => inline([
  ...chunk(items.map((item) => ({ text: item.destination, callback_data: `route:${item.id}` })), 2),
  [{ text: "⬅️ Orqaga", callback_data: "booking:scheduled" }],
  cancelRow,
]);

export const datesKeyboard = (routeId, dates) => inline([
  ...chunk(dates.map((date) => {
    const [year, month, day] = date.split("-");
    return { text: `${day}.${month}.${year}`, callback_data: `date:${routeId}:${date}` };
  }), 2),
  [{ text: "⬅️ Yo‘nalishlarga", callback_data: "booking:scheduled" }],
  cancelRow,
]);

export const tripsKeyboard = (trips, routeId) => inline([
  ...trips.map((trip) => [{
    text: `🕐 ${trip.departure_at.slice(11, 16)} · 💺 ${trip.available_seats} · 💳 ${Number(trip.price).toLocaleString("uz-UZ")}`,
    callback_data: `trip:${trip.id}`,
  }]),
  [{ text: "⬅️ Sanalarga", callback_data: `route:${routeId}` }],
  cancelRow,
]);

export const seatsKeyboard = (tripId, maximum) => inline([
  ...chunk(Array.from({ length: Math.min(maximum, 10) }, (_, index) => ({
    text: String(index + 1), callback_data: `seats:${tripId}:${index + 1}`,
  })), 5),
  [{ text: "⬅️ Reyslarga", callback_data: `booking:trip_back:${tripId}` }],
  cancelRow,
]);

export const confirmationKeyboard = () => inline([
  [{ text: "✅ Tasdiqlash va yuborish", callback_data: "booking:confirm" }],
  [
    { text: "✏️ Ma’lumotlarni o‘zgartirish", callback_data: "booking:edit_details" },
    { text: "❌ Bekor qilish", callback_data: "booking:abort" },
  ],
]);

export const quoteKeyboard = (bookingId) => inline([[
  { text: "✅ Narxni qabul qilish", callback_data: `quote:accept:${bookingId}` },
  { text: "❌ Rad etish", callback_data: `quote:reject:${bookingId}` },
]]);

export const cancelKeyboard = (bookingId) => inline([
  [{ text: "❌ Buyurtmani bekor qilish", callback_data: `cancel:ask:${bookingId}` }],
]);

export const cancelConfirmationKeyboard = (bookingId) => inline([
  [{ text: "✅ Yo‘q, buyurtma qolsin", callback_data: `cancel:back:${bookingId}` }],
  [{ text: "❌ Ha, bekor qilaman", callback_data: `cancel:confirm:${bookingId}` }],
]);

export const catalogKeyboard = () => inline([[
  { text: "🧳 Safarni band qilish", callback_data: "booking:start" },
  { text: "❌ Yopish", callback_data: "booking:abort" },
]]);

export const adminMenu = () => inline([
  [
    { text: "📊 Statistika", callback_data: "admin:stats" },
    { text: "🕐 Kutilayotganlar", callback_data: "admin:pending" },
  ],
  [
    { text: "➕ Yo‘nalish", callback_data: "admin:add_route" },
    { text: "➕ Reys", callback_data: "admin:add_trip" },
  ],
  [{ text: "🏠 Bosh menyu", callback_data: "admin:home" }],
]);

export const adminBookingKeyboard = (booking) => booking.status === "pending_price"
  ? inline([[
      { text: "💳 Narx belgilash", callback_data: `admin:quote:${booking.id}` },
      { text: "❌ Rad etish", callback_data: `admin:reject:${booking.id}` },
    ]])
  : inline([[
      { text: "✅ Tasdiqlash", callback_data: `admin:approve:${booking.id}` },
      { text: "❌ Rad etish", callback_data: `admin:reject:${booking.id}` },
    ]]);

export const routesKeyboard = (routes) => inline(routes.map((route) => [{
  text: `${route.origin} → ${route.destination}`,
  callback_data: `admin:trip_route:${route.id}`,
}]));

function chunk(items, size) {
  const rows = [];
  for (let index = 0; index < items.length; index += size) rows.push(items.slice(index, index + size));
  return rows;
}
