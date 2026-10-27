import {
  adminBookingKeyboard, adminMenu, bookingTypeKeyboard, cancelConfirmationKeyboard,
  cancelKeyboard, catalogKeyboard, confirmationKeyboard, customSeatsKeyboard,
  inputNavigationKeyboard, mainMenu, phoneKeyboard,
  quoteKeyboard, regionsKeyboard, resumeKeyboard, routesKeyboard,
  originsKeyboard, destinationsKeyboard, datesKeyboard, tripsKeyboard, seatsKeyboard,
} from "./keyboards.mjs";
import { BookingError } from "./database.mjs";
import { REGIONS } from "./locations.mjs";
import { bookingText, escapeHtml, money, tripText } from "./text.mjs";
import { parseAdminDate, parsePassengerDateTime, showDateTime } from "./time.mjs";
import { normalizeUzPhone, validatePassengerName } from "./validation.mjs";

export class TicketBot {
  constructor({ telegram, database, config, logger = console }) {
    this.tg = telegram;
    this.db = database;
    this.config = config;
    this.logger = logger;
    this.running = true;
    this.updateFailures = new Map();
  }

  isAdmin(userId) { return this.config.adminIds.has(userId); }

  async initialize() {
    const me = await this.tg.call("getMe");
    await this.tg.call("deleteWebhook", { drop_pending_updates: false });
    await this.tg.call("setMyCommands", { commands: [
      { command: "start", description: "🏠 Bosh menyuni ochish" },
      { command: "mybookings", description: "📋 Buyurtmalarim" },
      { command: "help", description: "🆘 Yordam markazi" },
      { command: "cancel", description: "❌ Joriy jarayonni bekor qilish" },
      { command: "admin", description: "🛠 Boshqaruv paneli" },
    ] });
    this.logger.info(`@${me.username} ishga tushdi`);
    await this.flushNotifications();
    return me;
  }

  stop() { this.running = false; this.tg.close(); }

  async run() {
    let offset = await this.db.getBotOffset();
    let failures = 0;
    while (this.running) {
      try {
        const updates = await this.tg.poll(offset);
        failures = 0;
        for (const update of updates) {
          try {
            await this.handleUpdate(update);
            offset = update.update_id + 1;
            await this.db.setBotOffset(offset);
            this.updateFailures.delete(update.update_id);
          } catch (error) {
            this.logger.error("Update xatosi", error);
            const attempts = (this.updateFailures.get(update.update_id) ?? 0) + 1;
            this.updateFailures.set(update.update_id, attempts);
            if (attempts < 3) break;
            this.logger.error(`Update ${update.update_id} uch marta bajarilmadi va o‘tkazib yuborildi`);
            offset = update.update_id + 1;
            await this.db.setBotOffset(offset);
          }
        }
        await this.flushNotifications();
      } catch (error) {
        if (!this.running) break;
        failures += 1;
        const waitMs = Math.min(30_000, 1000 * 2 ** Math.min(failures, 5));
        this.logger.error(`Telegram ulanish xatosi; ${waitMs / 1000}s dan so‘ng qayta urinadi`, error);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      }
    }
  }

  async handleUpdate(update) {
    if (update.message) await this.handleMessage(update.message);
    else if (update.callback_query) await this.handleCallback(update.callback_query);
  }

  async handleMessage(message) {
    const user = message.from;
    if (!user || !message.chat) return;
    await this.db.upsertUser(user);
    const text = (message.text ?? "").trim();
    const command = text.startsWith("/") ? text.split(/\s/, 1)[0].split("@", 1)[0].toLowerCase() : "";

    if (command === "/start") return this.showStart(message);
    if (command === "/cancel") return this.cancelAction(message);
    if (command === "/help" || ["ℹ️ Yordam", "🆘 Yordam"].includes(text)) return this.showHelp(message.chat.id);
    if (command === "/mybookings" || ["📋 Mening buyurtmalarim", "📋 Buyurtmalarim"].includes(text)) {
      return this.showBookings(message.chat.id, user.id);
    }
    if (command === "/admin" || ["⚙️ Admin panel", "🛠 Boshqaruv paneli"].includes(text)) return this.showAdmin(message);
    if (["🎫 Chipta buyurtma qilish", "🧳 Safarni band qilish"].includes(text)) {
      return this.showBookingOptions(message.chat.id, user.id);
    }
    if (text === "🗺 Yo‘nalishlar va narxlar") return this.showRouteCatalog(message.chat.id);
    if (text === "❌ Bekor qilish") return this.cancelAction(message);

    const session = await this.db.getSession(user.id);
    if (text === "⬅️ Orqaga" && session?.step?.startsWith("booking:")) {
      return this.handleBookingBack(message, session);
    }
    if (session?.step?.startsWith("admin:")) return this.handleAdminInput(message, session);
    if (session?.step?.startsWith("booking:")) return this.handleBookingInput(message, session);

    return this.tg.send(message.chat.id, "Kerakli bo‘limni menyudan tanlang 👇", mainMenu(this.isAdmin(user.id)));
  }

  async showStart(message) {
    const session = await this.db.getSession(message.from.id);
    if (session?.step?.startsWith("booking:") || session?.step?.startsWith("scheduled:")) {
      return this.tg.send(message.chat.id,
        "👋 <b>Qaytganingizdan xursandmiz!</b>\n\nSizda tugallanmagan safar buyurtmasi bor. Uni davom ettirasizmi?",
        resumeKeyboard());
    }
    await this.db.deleteSession(message.from.id);
    await this.tg.send(message.chat.id,
      `👋 <b>Assalomu alaykum, ${escapeHtml(message.from.first_name)}!</b>\n\n` +
      "O‘zbekiston bo‘ylab safaringizni bir necha daqiqada rejalashtiring.\n\n" +
      "🚌 Tayyor reysdan joy band qiling\n" +
      "🚖 Yoki shaxsiy safar so‘rovini yuboring",
      mainMenu(this.isAdmin(message.from.id)));
  }

  async cancelAction(message) {
    await this.db.deleteSession(message.from.id);
    await this.tg.send(message.chat.id,
      "✅ Joriy jarayon bekor qilindi. Hech qanday buyurtma yaratilmagan.",
      mainMenu(this.isAdmin(message.from.id)));
  }

  async showHelp(chatId) {
    await this.tg.send(chatId,
      "🆘 <b>Yordam markazi</b>\n\n" +
      "<b>Safarni qanday band qilaman?</b>\n" +
      "1️⃣ «🧳 Safarni band qilish»ni bosing\n" +
      "2️⃣ Tayyor reys yoki shaxsiy safarni tanlang\n" +
      "3️⃣ Yo‘nalish, sana, vaqt va joylar sonini kiriting\n" +
      "4️⃣ Ma’lumotlarni tekshirib tasdiqlang\n\n" +
      "📋 Holatni «Buyurtmalarim» bo‘limida kuzatishingiz mumkin.\n" +
      "↩️ Har bosqichda orqaga qaytish yoki jarayonni bekor qilish mumkin.\n\n" +
      "Buyruqlar: /start · /mybookings · /cancel");
  }

  async showRouteCatalog(chatId, editMessageId = null) {
    const routes = await this.db.listRouteCatalog();
    const text = routes.length
      ? "🗺 <b>Yaqin reyslar va boshlang‘ich narxlar</b>\n\n" + routes.map((route) =>
          `📍 <b>${escapeHtml(route.origin)} → ${escapeHtml(route.destination)}</b>\n` +
          `🚌 ${route.trips} ta reys · 💺 ${route.available_seats} ta joy\n` +
          `💳 ${money(route.minimum_price)} dan`).join("\n\n") +
        "\n\n<i>Narx bir yo‘lovchi uchun. Reysni tanlaganda yakuniy summa ko‘rsatiladi.</i>"
      : "🗺 <b>Yo‘nalishlar va narxlar</b>\n\nHozircha sotuvdagi tayyor reyslar yo‘q. Shaxsiy safar so‘rovini yuborishingiz mumkin.";
    return editMessageId
      ? this.safeEdit(chatId, editMessageId, text, catalogKeyboard())
      : this.tg.send(chatId, text, catalogKeyboard());
  }

  async showOrigins(chatId, userId, editMessageId = null) {
    await this.db.deleteSession(userId);
    return editMessageId
      ? this.safeEdit(chatId, editMessageId, "📍 <b>1/5 · Qayerdan jo‘naysiz?</b>\n\nViloyatni tanlang:", regionsKeyboard(REGIONS, "origin"))
      : this.tg.send(chatId, "📍 <b>1/5 · Qayerdan jo‘naysiz?</b>\n\nViloyatni tanlang:", regionsKeyboard(REGIONS, "origin"));
  }

  async showBookingOptions(chatId, userId, editMessageId = null) {
    await this.db.deleteSession(userId);
    const hasScheduledTrips = (await this.db.listOrigins()).length > 0;
    const text = "🧳 <b>Qanday safar qilmoqchisiz?</b>\n\n" +
      "🚌 <b>Tayyor reys</b> — vaqt va narx oldindan ma’lum\n" +
      "🚖 <b>Shaxsiy safar</b> — manzil va vaqtni o‘zingiz tanlaysiz, narx masofaga qarab oldindan chiqadi";
    return editMessageId
      ? this.safeEdit(chatId, editMessageId, text, bookingTypeKeyboard(hasScheduledTrips))
      : this.tg.send(chatId, text, bookingTypeKeyboard(hasScheduledTrips));
  }

  async showScheduledOrigins(chatId, userId, messageId) {
    const origins = await this.db.listOrigins();
    if (!origins.length) return this.safeAnswer(null, "Hozircha bo‘sh reyslar yo‘q.", true);
    await this.db.setSession(userId, { step: "scheduled:origin" });
    return this.safeEdit(chatId, messageId, "📍 <b>1/4 · Qayerdan jo‘naysiz?</b>\n\nFaqat bo‘sh joyi bor yo‘nalishlar ko‘rsatilgan:", originsKeyboard(origins));
  }

  async showBookings(chatId, userId) {
    const bookings = await this.db.listUserBookings(userId);
    if (!bookings.length) return this.tg.send(chatId,
      "📋 <b>Buyurtmalaringiz</b>\n\nSizda hali buyurtma yo‘q. Birinchi safaringizni band qilish uchun menyudan foydalaning.");
    await this.tg.send(chatId,
      `📋 <b>Buyurtmalaringiz</b>\n\nOxirgi ${bookings.length} ta buyurtma. Holat va amallar har bir kartada ko‘rsatilgan:`);
    for (const booking of bookings) {
      const keyboard = booking.status === "quoted"
        ? quoteKeyboard(booking.id)
        : ["pending", "pending_price", "confirmed"].includes(booking.status) ? cancelKeyboard(booking.id) : undefined;
      await this.tg.send(chatId, bookingText(booking), keyboard);
    }
  }

  async showAdmin(message) {
    if (!this.isAdmin(message.from.id)) return this.tg.send(message.chat.id, "⛔ Bu bo‘lim faqat administrator uchun.");
    await this.db.deleteSession(message.from.id);
    return this.tg.send(message.chat.id,
      "🛠 <b>Boshqaruv paneli</b>\n\nBuyurtmalar, reyslar va statistikani boshqaring:", adminMenu());
  }

  async requestCustomDateTime(chatId, userId, session, messageId = null) {
    if (!session?.origin || !session?.destination) {
      await this.db.deleteSession(userId);
      return this.showOrigins(chatId, userId, messageId);
    }
    const fare = await this.db.getRoutePrice(session.origin, session.destination);
    Object.assign(session, {
      step: "booking:datetime",
      distanceKm: fare.distanceKm,
      unitPrice: fare.unitPrice,
    });
    delete session.date;
    delete session.hour;
    delete session.minute;
    delete session.departureAt;
    await this.db.setSession(userId, session);
    const summary = [
      `📍 <b>${escapeHtml(session.origin)} → ${escapeHtml(session.destination)}</b>`,
      `🛣 Taxminiy masofa: <b>${fare.distanceKm} km</b>`,
      `💳 1 yo‘lovchi uchun: <b>${money(fare.unitPrice)}</b>`,
    ].join("\n");
    if (messageId) await this.safeEdit(chatId, messageId, summary);
    return this.tg.send(chatId,
      "🗓 <b>3/5 · Safar sanasi va vaqtini yozing</b>\n\n" +
      "Masalan: <code>17-noyabr soat 17:05</code>\n" +
      "Yoki: <code>17.11.2026 17:05</code>\n\n" +
      "Safar bugundan boshlab 30 kun ichida bo‘lishi kerak.",
      inputNavigationKeyboard);
  }

  async ensureCustomFare(userId, session) {
    if (session?.mode !== "custom" || !session.origin || !session.destination) return session;
    if (Number(session.distanceKm) > 0 && Number(session.unitPrice) > 0) return session;
    const fare = await this.db.getRoutePrice(session.origin, session.destination);
    Object.assign(session, { distanceKm: fare.distanceKm, unitPrice: fare.unitPrice });
    await this.db.setSession(userId, session);
    return session;
  }

  async resumeBooking(chatId, userId, messageId) {
    let session = await this.db.getSession(userId);
    if (!session) return this.safeEdit(chatId, messageId,
      "Bu jarayon muddati tugagan. Yangi safar buyurtmasini boshlang.", bookingTypeKeyboard(false));
    session = await this.ensureCustomFare(userId, session);

    if (session.step === "scheduled:origin") {
      const origins = await this.db.listOrigins();
      return this.safeEdit(chatId, messageId,
        "📍 <b>1/4 · Qayerdan jo‘naysiz?</b>", originsKeyboard(origins));
    }
    if (session.step === "scheduled:destination") {
      const origins = await this.db.listOrigins();
      const selected = origins.find((item) => item.origin === session.origin);
      if (!selected) return this.showBookingOptions(chatId, userId, messageId);
      const destinations = await this.db.listDestinations(selected.route_id);
      return this.safeEdit(chatId, messageId,
        `📍 <b>2/4 · ${escapeHtml(session.origin)}dan qayerga borasiz?</b>`,
        destinationsKeyboard(destinations));
    }
    if (session.step === "scheduled:date" && session.routeId) {
      const dates = await this.db.listTripDates(session.routeId);
      return this.safeEdit(chatId, messageId,
        `📅 <b>3/4 · ${escapeHtml(session.origin)} → ${escapeHtml(session.destination)}</b>\n\nSanani tanlang:`,
        datesKeyboard(session.routeId, dates));
    }
    if (session.step === "scheduled:seats" && session.trip) {
      return this.safeEdit(chatId, messageId,
        `${tripText(session.trip)}\n\n💺 <b>4/4 · Nechta joy kerak?</b>`,
        seatsKeyboard(session.tripId, session.trip.available_seats));
    }
    if (session.step === "booking:destination") {
      return this.safeEdit(chatId, messageId,
        `📍 <b>2/5 · ${escapeHtml(session.origin)}dan qayerga borasiz?</b>`,
        regionsKeyboard(REGIONS, "destination", session.originIndex));
    }
    if (["booking:date", "booking:hour", "booking:minute", "booking:datetime"].includes(session.step)
        && session.destination) {
      return this.requestCustomDateTime(chatId, userId, session, messageId);
    }
    if (session.step === "booking:seats") {
      return this.safeEdit(chatId, messageId,
        `${this.sessionTripText(session)}\n\n💺 <b>4/5 · Nechta joy kerak?</b>`, customSeatsKeyboard());
    }
    if (session.step === "booking:name") {
      await this.safeEdit(chatId, messageId, "▶️ Buyurtma jarayoni davom ettirildi.");
      return this.tg.send(chatId, "👤 <b>5/5 · Yo‘lovchining ism-familiyasini kiriting:</b>", inputNavigationKeyboard);
    }
    if (session.step === "booking:phone") {
      await this.safeEdit(chatId, messageId, "▶️ Buyurtma jarayoni davom ettirildi.");
      return this.tg.send(chatId, "📱 <b>Telefon raqamingizni yuboring:</b>", phoneKeyboard);
    }
    if (session.step === "booking:confirm") {
      return this.safeEdit(chatId, messageId,
        "🔎 <b>Yakuniy tekshiruv</b>\n\n" + this.sessionTripText(session) +
        `\n\n👤 Yo‘lovchi: ${escapeHtml(session.passengerName)}\n📱 Telefon: ${escapeHtml(session.phone)}` +
        `\n💺 Joylar: <b>${session.seats} ta</b>`, confirmationKeyboard());
    }
    await this.db.deleteSession(userId);
    return this.showBookingOptions(chatId, userId, messageId);
  }

  async handleBookingInput(message, session) {
    session = await this.ensureCustomFare(message.from.id, session);
    if (session.step === "booking:datetime") {
      const departureAt = parsePassengerDateTime(message.text, this.db.now(), 30);
      if (!departureAt) return this.tg.send(message.chat.id,
        "⚠️ Sana yoki vaqtni tushunmadim. Kelajakdagi sanani quyidagidek yozing:\n\n" +
        "<code>17-noyabr soat 17:05</code>\n" +
        "<code>17.11.2026 17:05</code>\n\n" +
        "Safar 30 kun ichida bo‘lishi kerak.", inputNavigationKeyboard);
      Object.assign(session, { step: "booking:seats", departureAt });
      await this.db.setSession(message.from.id, session);
      return this.tg.send(message.chat.id,
        `${this.customTripText(session)}\n\n💺 <b>4/5 · Nechta joy kerak?</b>`, customSeatsKeyboard());
    }
    if (session.step === "booking:name") {
      const name = validatePassengerName(message.text);
      if (!name) return this.tg.send(message.chat.id,
        "⚠️ Ism-familiyani to‘liq kiriting. Masalan: <b>Ali Valiyev</b>", inputNavigationKeyboard);
      session.passengerName = name;
      session.step = "booking:phone";
      await this.db.setSession(message.from.id, session);
      return this.tg.send(message.chat.id,
        "📱 <b>Telefon raqamingiz</b>\n\nPastdagi tugma orqali o‘z kontaktingizni yuboring yoki <code>+998 90 123 45 67</code> shaklida yozing:",
        phoneKeyboard);
    }

    if (session.step === "booking:phone") {
      if (message.contact?.user_id && message.contact.user_id !== message.from.id) {
        return this.tg.send(message.chat.id,
          "⚠️ Xavfsizlik uchun faqat o‘zingizning Telegram kontaktingizni yuboring.", phoneKeyboard);
      }
      const phone = normalizeUzPhone(message.contact?.phone_number ?? message.text);
      if (!phone) return this.tg.send(message.chat.id,
        "⚠️ Telefon raqami noto‘g‘ri. To‘g‘ri namuna: <code>+998 90 123 45 67</code>", phoneKeyboard);
      await this.db.setPhone(message.from.id, phone);
      session.phone = phone;
      session.step = "booking:confirm";
      await this.db.setSession(message.from.id, session);
      return this.tg.send(message.chat.id,
        "🔎 <b>Yakuniy tekshiruv</b>\n\n" + this.sessionTripText(session) +
        `\n\n👤 Yo‘lovchi: ${escapeHtml(session.passengerName)}\n📱 Telefon: ${escapeHtml(phone)}` +
        `\n💺 Joylar: <b>${session.seats} ta</b>` +
        "\n\n<i>Ma’lumotlar to‘g‘ri bo‘lsa, buyurtmani tasdiqlang.</i>",
        confirmationKeyboard());
    }
    return this.tg.send(message.chat.id, "👇 Davom etish uchun ekrandagi tugmalardan birini tanlang.");
  }

  async handleBookingBack(message, session) {
    const { id: userId } = message.from;
    if (session.step === "booking:phone") {
      session.step = "booking:name";
      await this.db.setSession(userId, session);
      return this.tg.send(message.chat.id,
        "👤 <b>Yo‘lovchining ism-familiyasini qayta kiriting:</b>", inputNavigationKeyboard);
    }
    if (session.step === "booking:name") {
      session.step = "booking:seats";
      await this.db.setSession(userId, session);
      const text = `${this.sessionTripText(session)}\n\n💺 <b>Nechta joy kerak?</b>`;
      const keyboard = session.mode === "scheduled"
        ? seatsKeyboard(session.tripId, session.trip?.available_seats ?? 1)
        : customSeatsKeyboard();
      return this.tg.send(message.chat.id, text, keyboard);
    }
    if (session.step === "booking:datetime") {
      session.step = "booking:destination";
      await this.db.setSession(userId, session);
      return this.tg.send(message.chat.id,
        `📍 <b>2/5 · ${escapeHtml(session.origin)}dan qayerga borasiz?</b>`,
        regionsKeyboard(REGIONS, "destination", session.originIndex));
    }
    return this.tg.send(message.chat.id,
      "Bu bosqichda orqaga qaytish uchun xabardagi inline tugmadan foydalaning.");
  }

  async handleAdminInput(message, session) {
    if (!this.isAdmin(message.from.id)) { await this.db.deleteSession(message.from.id); return; }
    const text = (message.text ?? "").trim();
    if (!text) return this.tg.send(message.chat.id, "Matn yuboring.");
    if (session.step === "admin:route_origin") {
      if (text.length < 2 || text.length > 60) return this.tg.send(message.chat.id, "Shahar nomi 2–60 ta belgidan iborat bo‘lsin.");
      session.origin = text;
      session.step = "admin:route_destination";
      await this.db.setSession(message.from.id, session);
      return this.tg.send(message.chat.id, "📍 Borish shahrini yozing:");
    }
    if (session.step === "admin:route_destination") {
      if (text.length < 2 || text.length > 60 || text.toLocaleLowerCase("uz") === session.origin.toLocaleLowerCase("uz")) {
        return this.tg.send(message.chat.id, "Borish shahri to‘g‘ri kiritilmadi.");
      }
      try {
        const id = Number(await this.db.createRoute(session.origin, text));
        await this.db.deleteSession(message.from.id);
        return this.tg.send(message.chat.id, `✅ Yo‘nalish qo‘shildi: <b>${escapeHtml(session.origin)} → ${escapeHtml(text)}</b>\nID: <code>${id}</code>`, adminMenu());
      } catch (error) {
        if (error instanceof BookingError) return this.tg.send(message.chat.id, error.message);
        throw error;
      }
    }
    if (session.step === "admin:trip_details") {
      const parts = text.split("|").map((part) => part.trim());
      if (parts.length !== 4) return this.tg.send(message.chat.id, "Format noto‘g‘ri. To‘rtta qiymatni | belgisi bilan ajrating.");
      const departure = parseAdminDate(parts[0]);
      const price = Number(parts[2].replaceAll(" ", ""));
      const seats = Number(parts[3]);
      if (!departure || departure <= this.db.now()) return this.tg.send(message.chat.id, "Sana-vaqt noto‘g‘ri yoki o‘tib ketgan.");
      if (!Number.isInteger(price) || price < 0 || price > 100_000_000 || !Number.isInteger(seats) || seats < 1 || seats > 100) {
        return this.tg.send(message.chat.id, "Narx 0–100 mln, joylar soni 1–100 oralig‘ida bo‘lsin.");
      }
      if (parts[1].length < 2 || parts[1].length > 100) return this.tg.send(message.chat.id, "Transport nomi 2–100 ta belgidan iborat bo‘lsin.");
      const id = Number(await this.db.createTrip(session.routeId, departure, parts[1], price, seats));
      await this.db.deleteSession(message.from.id);
      return this.tg.send(message.chat.id,
        `✅ Reys qo‘shildi. ID: <code>${id}</code>\n📅 ${showDateTime(departure)}\n💳 ${money(price)} · 💺 ${seats} joy`, adminMenu());
    }
    if (session.step === "admin:quote_price") {
      const price = Number(text.replaceAll(" ", ""));
      try {
        if (!await this.db.quoteBooking(session.bookingId, price)) {
          await this.db.deleteSession(message.from.id);
          return this.tg.send(message.chat.id, "Buyurtmaga narx belgilab bo‘lmaydi. U ko‘rib chiqilgan yoki muddati o‘tgan.", adminMenu());
        }
      } catch (error) {
        if (error instanceof BookingError) return this.tg.send(message.chat.id, error.message);
        throw error;
      }
      await this.db.deleteSession(message.from.id);
      const booking = await this.db.getBooking(session.bookingId);
      await this.sendOrQueue(booking.user_id,
        `💳 <b>Buyurtmangiz uchun narx taklif qilindi</b>\n\n${bookingText(booking)}\n\nNarxni qabul qilasizmi?`, quoteKeyboard(booking.id));
      return this.tg.send(message.chat.id, `✅ Narx mijozga yuborildi: <b>${money(price)}</b>`, adminMenu());
    }
  }

  async handleCallback(query) {
    const data = query.data ?? "";
    const userId = query.from.id;
    const chatId = query.message?.chat?.id;
    const messageId = query.message?.message_id;
    if (!chatId || !messageId) return this.safeAnswer(query.id);
    try {
      await this.db.upsertUser(query.from);
      if (data.startsWith("admin:")) {
        if (!this.isAdmin(userId)) return this.safeAnswer(query.id, "Ruxsat yo‘q.", true);
        await this.handleAdminCallback(query, data, chatId, messageId);
      } else {
        await this.handleUserCallback(query, data, chatId, messageId);
      }
    } catch (error) {
      this.logger.error("Callback xatosi", error);
      await this.safeAnswer(query.id, "Xatolik yuz berdi. Qayta urinib ko‘ring.", true);
    }
  }

  async handleUserCallback(query, data, chatId, messageId) {
    const userId = query.from.id;
    if (data === "noop") return this.safeAnswer(query.id);
    if (data === "catalog:routes") {
      await this.showRouteCatalog(chatId, messageId);
      return this.safeAnswer(query.id);
    }
    if (data === "session:resume") {
      await this.resumeBooking(chatId, userId, messageId);
      return this.safeAnswer(query.id, "Jarayon davom ettirildi");
    }
    if (data === "session:restart") {
      await this.db.deleteSession(userId);
      await this.showBookingOptions(chatId, userId, messageId);
      return this.safeAnswer(query.id, "Yangi buyurtma boshlandi");
    }
    if (data === "booking:start") { await this.showBookingOptions(chatId, userId, messageId); return this.safeAnswer(query.id); }
    if (data === "booking:custom") { await this.showOrigins(chatId, userId, messageId); return this.safeAnswer(query.id); }
    if (data === "booking:scheduled") {
      const origins = await this.db.listOrigins();
      if (!origins.length) return this.safeAnswer(query.id, "Hozircha bo‘sh reyslar yo‘q.", true);
      await this.db.setSession(userId, { step: "scheduled:origin" });
      await this.safeEdit(chatId, messageId,
        "📍 <b>1/4 · Qayerdan jo‘naysiz?</b>\n\nFaqat bo‘sh joyi bor yo‘nalishlar ko‘rsatilgan:",
        originsKeyboard(origins));
      return this.safeAnswer(query.id);
    }
    if (data === "booking:abort") {
      await this.db.deleteSession(userId);
      await this.safeEdit(chatId, messageId,
        "✅ Jarayon bekor qilindi. Hech qanday buyurtma yaratilmagan.");
      await this.tg.send(chatId, "🏠 <b>Bosh menyu</b>", mainMenu(this.isAdmin(userId)));
      return this.safeAnswer(query.id, "Jarayon bekor qilindi");
    }
    if (data.startsWith("scheduled_origin:")) {
      const routeId = Number(data.split(":")[1]);
      const route = await this.db.getRoute(routeId);
      const destinations = await this.db.listDestinations(routeId);
      if (!route || !destinations.length) return this.safeAnswer(query.id, "Bu yo‘nalishda bo‘sh reys topilmadi.", true);
      await this.db.setSession(userId, { step: "scheduled:destination", origin: route.origin });
      await this.safeEdit(chatId, messageId,
        `📍 <b>2/4 · ${escapeHtml(route.origin)}dan qayerga borasiz?</b>`,
        destinationsKeyboard(destinations));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("route:")) {
      const routeId = Number(data.split(":")[1]);
      const route = await this.db.getRoute(routeId);
      const dates = await this.db.listTripDates(routeId);
      if (!route || !dates.length) return this.safeAnswer(query.id, "Bo‘sh reys sanalari topilmadi.", true);
      await this.db.setSession(userId, { step: "scheduled:date", mode: "scheduled", routeId, origin: route.origin, destination: route.destination });
      await this.safeEdit(chatId, messageId,
        `📅 <b>3/4 · ${escapeHtml(route.origin)} → ${escapeHtml(route.destination)}</b>\n\nSanani tanlang:`,
        datesKeyboard(routeId, dates));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("date:")) {
      const [, routeValue, date] = data.split(":");
      const routeId = Number(routeValue);
      const trips = await this.db.listTrips(routeId, date);
      if (!trips.length) return this.safeAnswer(query.id, "Bu sanadagi joylar tugagan.", true);
      await this.safeEdit(chatId, messageId,
        "🚌 <b>4/4 · Reysni tanlang</b>\n\nTugmada vaqt, bo‘sh joy va bir kishilik narx ko‘rsatilgan:",
        tripsKeyboard(trips, routeId));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("trip:")) {
      const trip = await this.db.getTrip(Number(data.split(":")[1]));
      if (!trip || trip.departure_at <= this.db.now() || trip.available_seats < 1) return this.safeAnswer(query.id, "Bu reys endi mavjud emas.", true);
      await this.db.setSession(userId, { step: "scheduled:seats", mode: "scheduled", tripId: trip.id, trip });
      await this.safeEdit(chatId, messageId,
        `${tripText(trip)}\n\n💺 <b>Nechta joy kerak?</b>`,
        seatsKeyboard(trip.id, trip.available_seats));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("booking:trip_back:")) {
      const trip = await this.db.getTrip(Number(data.split(":")[2]));
      if (!trip) return this.safeAnswer(query.id, "Reys topilmadi.", true);
      const trips = await this.db.listTrips(trip.route_id, trip.trip_date);
      await this.safeEdit(chatId, messageId,
        "🚌 <b>Reysni tanlang</b>\n\nTugmada vaqt, bo‘sh joy va bir kishilik narx ko‘rsatilgan:",
        tripsKeyboard(trips, trip.route_id));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("seats:")) {
      const [, tripValue, seatsValue] = data.split(":");
      const tripId = Number(tripValue), seats = Number(seatsValue);
      const trip = await this.db.getTrip(tripId);
      if (!trip || !Number.isInteger(seats) || seats < 1 || seats > Math.min(10, trip.available_seats)) return this.safeAnswer(query.id, "Joylar soni noto‘g‘ri.", true);
      const session = { step: "booking:name", mode: "scheduled", tripId, trip, seats };
      await this.db.setSession(userId, session);
      await this.safeEdit(chatId, messageId,
        `${tripText(trip)}\n\n✅ Tanlandi: <b>${seats} ta joy</b>`);
      await this.tg.send(chatId,
        "👤 <b>Yo‘lovchining ism-familiyasini kiriting</b>\n\nMasalan: <i>Ali Valiyev</i>",
        inputNavigationKeyboard);
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("origin:")) {
      const originIndex = Number(data.split(":")[1]);
      const origin = REGIONS[originIndex];
      if (!origin) return this.safeAnswer(query.id, "Manzil topilmadi.", true);
      await this.db.setSession(userId, { step: "booking:destination", mode: "custom", originIndex, origin });
      await this.safeEdit(chatId, messageId,
        `📍 <b>2/5 · ${escapeHtml(origin)}dan qayerga borasiz?</b>\n\nViloyatni tanlang:`,
        regionsKeyboard(REGIONS, "destination", originIndex));
      return this.safeAnswer(query.id);
    }
    if (data === "booking:destinations") {
      const session = await this.db.getSession(userId);
      if (!session?.origin) return this.showOrigins(chatId, userId, messageId);
      await this.safeEdit(chatId, messageId,
        `📍 <b>2/5 · ${escapeHtml(session.origin)}dan qayerga borasiz?</b>`,
        regionsKeyboard(REGIONS, "destination", session.originIndex));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("destination:")) {
      const session = await this.db.getSession(userId);
      const destinationIndex = Number(data.split(":")[1]);
      const destination = REGIONS[destinationIndex];
      if (!session?.origin || !destination || destinationIndex === session.originIndex) return this.safeAnswer(query.id, "Manzil noto‘g‘ri.", true);
      Object.assign(session, { destinationIndex, destination });
      await this.requestCustomDateTime(chatId, userId, session, messageId);
      return this.safeAnswer(query.id);
    }
    if (["booking:calendar", "booking:hours", "booking:minutes", "booking:datetime_input"].includes(data)
        || data.startsWith("calnav:") || data.startsWith("caldate:")
        || data.startsWith("hour:") || data.startsWith("minute:")) {
      const session = await this.db.getSession(userId);
      if (!session?.destination) return this.safeAnswer(query.id, "Jarayon eskirgan. Qaytadan boshlang.", true);
      await this.requestCustomDateTime(chatId, userId, session, messageId);
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("customseats:")) {
      let session = await this.db.getSession(userId);
      session = await this.ensureCustomFare(userId, session);
      const seats = Number(data.split(":")[1]);
      if (!session?.departureAt || !Number.isInteger(seats) || seats < 1 || seats > 10) return this.safeAnswer(query.id, "Joylar soni noto‘g‘ri.", true);
      Object.assign(session, { step: "booking:name", seats });
      await this.db.setSession(userId, session);
      await this.safeEdit(chatId, messageId,
        `${this.customTripText(session)}\n\n✅ Tanlandi: <b>${seats} ta joy</b>`);
      await this.tg.send(chatId,
        "👤 <b>5/5 · Yo‘lovchining ism-familiyasini kiriting</b>\n\nMasalan: <i>Ali Valiyev</i>",
        inputNavigationKeyboard);
      return this.safeAnswer(query.id);
    }
    if (data === "booking:edit_details") {
      const session = await this.db.getSession(userId);
      if (session?.step !== "booking:confirm") {
        return this.safeAnswer(query.id, "Jarayon eskirgan. Qaytadan boshlang.", true);
      }
      session.step = "booking:name";
      await this.db.setSession(userId, session);
      await this.safeEdit(chatId, messageId, "✏️ Ma’lumotlarni o‘zgartirish rejimi yoqildi.");
      await this.tg.send(chatId,
        "👤 Yo‘lovchining ism-familiyasini qayta kiriting:", inputNavigationKeyboard);
      return this.safeAnswer(query.id);
    }
    if (data === "booking:confirm") {
      const session = await this.db.getSession(userId);
      if (session?.step !== "booking:confirm") return this.safeAnswer(query.id, "Jarayon eskirgan. Qaytadan boshlang.", true);
      try {
        const booking = session.mode === "scheduled"
          ? await this.db.createBooking({ userId, tripId: session.tripId, seats: session.seats, passengerName: session.passengerName, phone: session.phone })
          : await this.db.createCustomBooking({ userId, origin: session.origin, destination: session.destination, departureAt: session.departureAt, seats: session.seats, passengerName: session.passengerName, phone: session.phone });
        await this.db.deleteSession(userId);
        const nextStep = booking.status === "pending_price"
          ? "Operator safar narxini hisoblab yuboradi. Taklifni qabul qilishdan oldin buyurtma tasdiqlanmaydi."
          : "Operator buyurtmani tekshiradi va tasdiqlanganda sizga xabar yuboramiz.";
        const successText = `✅ <b>Buyurtmangiz qabul qilindi</b>\n\n${bookingText(booking)}\n\n📌 <b>Keyingi qadam:</b> ${nextStep}`;
        try { await this.safeEdit(chatId, messageId, successText); }
        catch { await this.sendOrQueue(chatId, successText); }
        await this.tg.send(chatId, "🏠 <b>Bosh menyu</b>", mainMenu(this.isAdmin(userId)));
        for (const adminId of this.config.adminIds) {
          await this.sendOrQueue(adminId, `🔔 <b>Yangi buyurtma</b>\n\n${bookingText(booking)}`, adminBookingKeyboard(booking));
        }
        return this.safeAnswer(query.id, "Buyurtma yaratildi!");
      } catch (error) {
        await this.db.deleteSession(userId);
        if (error instanceof BookingError) return this.safeAnswer(query.id, error.message, true);
        throw error;
      }
    }
    if (data.startsWith("cancel:ask:")) {
      const id = Number(data.split(":")[2]);
      const booking = await this.db.getBooking(id);
      if (!booking || booking.user_id !== userId || !["pending", "pending_price", "quoted", "confirmed"].includes(booking.status)) {
        return this.safeAnswer(query.id, "Bu buyurtmani bekor qilib bo‘lmaydi.", true);
      }
      await this.safeEdit(chatId, messageId,
        `⚠️ <b>Buyurtmani bekor qilmoqchimisiz?</b>\n\n${bookingText(booking)}\n\nBu amalni keyin ortga qaytarib bo‘lmaydi.`,
        cancelConfirmationKeyboard(id));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("cancel:back:")) {
      const id = Number(data.split(":")[2]);
      const booking = await this.db.getBooking(id);
      if (!booking || booking.user_id !== userId) return this.safeAnswer(query.id, "Buyurtma topilmadi.", true);
      await this.safeEdit(chatId, messageId, bookingText(booking), cancelKeyboard(id));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("cancel:confirm:") || /^cancel:\d+$/.test(data)) {
      const id = Number(data.split(":").at(-1));
      if (!await this.db.cancelBooking(id, userId)) {
        return this.safeAnswer(query.id, "Buyurtmani bekor qilib bo‘lmaydi yoki safar boshlangan.", true);
      }
      await this.safeEdit(chatId, messageId,
        `✅ <b>Buyurtma bekor qilindi</b>\n\n${bookingText(await this.db.getBooking(id))}`);
      return this.safeAnswer(query.id, "Buyurtma bekor qilindi");
    }
    if (data.startsWith("quote:accept:") || data.startsWith("quote:reject:")) {
      const id = Number(data.split(":")[2]);
      const accepted = data.includes(":accept:");
      const changed = accepted ? await this.db.acceptQuote(id, userId) : await this.db.rejectQuote(id, userId);
      if (!changed) return this.safeAnswer(query.id, "Taklif eskirgan yoki safar vaqti o‘tgan.", true);
      const booking = await this.db.getBooking(id);
      await this.safeEdit(chatId, messageId, bookingText(booking));
      for (const adminId of this.config.adminIds) await this.sendOrQueue(adminId,
        `${accepted ? "✅ Mijoz narxni qabul qildi" : "❌ Mijoz narxni rad etdi"}\n\n${bookingText(booking)}`);
      return this.safeAnswer(query.id, accepted ? "Buyurtma tasdiqlandi." : "Taklif rad etildi.");
    }
    return this.safeAnswer(query.id, "Tugma eskirgan.", true);
  }

  async handleAdminCallback(query, data, chatId, messageId) {
    const userId = query.from.id;
    if (data === "admin:home") {
      await this.db.deleteSession(userId);
      await this.safeEdit(chatId, messageId, "✅ Boshqaruv paneli yopildi.");
      await this.tg.send(chatId, "🏠 <b>Bosh menyu</b>", mainMenu(true));
      return this.safeAnswer(query.id);
    }
    if (data === "admin:stats") {
      const stats = await this.db.stats();
      await this.tg.send(chatId, `📊 <b>Bot statistikasi</b>\n\n👥 Foydalanuvchilar: <b>${stats.users}</b>\n🚌 Faol reyslar: <b>${stats.active_trips}</b>\n🕐 Kutilayotganlar: <b>${stats.pending}</b>\n✅ Tasdiqlanganlar: <b>${stats.confirmed}</b>\n💰 Savdo: <b>${money(stats.revenue)}</b>`);
      return this.safeAnswer(query.id);
    }
    if (data === "admin:pending") {
      const items = await this.db.listPending();
      if (!items.length) return this.safeAnswer(query.id, "Kutilayotgan buyurtmalar yo‘q.", true);
      await this.tg.send(chatId, `🕐 <b>${items.length} ta buyurtma kutilmoqda:</b>`);
      for (const item of items) await this.tg.send(chatId, bookingText(item), adminBookingKeyboard(item));
      return this.safeAnswer(query.id);
    }
    if (data === "admin:add_route") {
      await this.db.setSession(userId, { step: "admin:route_origin" });
      await this.tg.send(chatId, "📍 Jo‘nash shahrini yozing (masalan, Toshkent):");
      return this.safeAnswer(query.id);
    }
    if (data === "admin:add_trip") {
      const routes = await this.db.listRoutes();
      if (!routes.length) return this.safeAnswer(query.id, "Avval yo‘nalish qo‘shing.", true);
      await this.tg.send(chatId, "🚌 Reys uchun yo‘nalishni tanlang:", routesKeyboard(routes));
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("admin:trip_route:")) {
      const routeId = Number(data.split(":")[2]), route = await this.db.getRoute(routeId);
      if (!route) return this.safeAnswer(query.id, "Yo‘nalish topilmadi.", true);
      await this.db.setSession(userId, { step: "admin:trip_details", routeId });
      await this.tg.send(chatId,
        `🚌 <b>${escapeHtml(route.origin)} → ${escapeHtml(route.destination)}</b>\n\n` +
        "Format:\n<code>31.12.2026 18:30 | Mercedes Sprinter | 150000 | 20</code>\n\n" +
        "Tartib: sana-vaqt | transport | narx | joylar soni");
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("admin:quote:")) {
      const id = Number(data.split(":")[2]);
      const booking = await this.db.getBooking(id);
      if (!booking || booking.status !== "pending_price" || booking.departure_at <= this.db.now()) {
        return this.safeAnswer(query.id, "Buyurtmaga narx belgilab bo‘lmaydi.", true);
      }
      await this.db.setSession(userId, { step: "admin:quote_price", bookingId: id });
      await this.tg.send(chatId, `💳 <b>Buyurtma #${escapeHtml(booking.code)}</b> uchun jami narxni so‘mda kiriting:\nMasalan: <code>450000</code>`);
      return this.safeAnswer(query.id);
    }
    if (data.startsWith("admin:approve:") || data.startsWith("admin:reject:")) {
      const id = Number(data.split(":")[2]);
      const status = data.includes(":approve:") ? "confirmed" : "rejected";
      if (!await this.db.setBookingStatus(id, status)) return this.safeAnswer(query.id, "Buyurtma avval ko‘rib chiqilgan yoki muddati o‘tgan.", true);
      const booking = await this.db.getBooking(id);
      await this.safeEdit(chatId, messageId, bookingText(booking));
      const heading = status === "confirmed" ? "✅ <b>Buyurtmangiz tasdiqlandi!</b>" : "❌ <b>Buyurtmangiz rad etildi.</b>";
      await this.sendOrQueue(booking.user_id, `${heading}\n\n${bookingText(booking)}`);
      return this.safeAnswer(query.id, "Holat yangilandi.");
    }
    return this.safeAnswer(query.id, "Tugma eskirgan.", true);
  }

  async safeEdit(chatId, messageId, text, keyboard) {
    try { return await this.tg.edit(chatId, messageId, text, keyboard); }
    catch (error) {
      if (String(error.message).includes("message is not modified")) return null;
      throw error;
    }
  }

  customTripText(session) {
    const rows = [
      `📍 <b>${escapeHtml(session.origin)} → ${escapeHtml(session.destination)}</b>`,
      `🗓 Jo‘nash: <b>${showDateTime(session.departureAt)}</b>`,
      "🚖 Transport: shaxsiy taxi",
      `🛣 Taxminiy masofa: <b>${Number(session.distanceKm)} km</b>`,
      `💳 1 yo‘lovchi: <b>${money(session.unitPrice)}</b>`,
    ];
    if (Number.isInteger(session.seats) && session.seats > 0) {
      rows.push(`💰 Jami: <b>${money(session.unitPrice * session.seats)}</b>`);
    }
    return rows.join("\n");
  }

  sessionTripText(session) {
    return session.mode === "scheduled" && session.trip ? tripText(session.trip) : this.customTripText(session);
  }

  async sendOrQueue(chatId, text, keyboard) {
    try { return await this.tg.send(chatId, text, keyboard); }
    catch (error) {
      this.logger.warn("Telegram xabari navbatga saqlandi", error.message);
      await this.db.enqueueNotification(chatId, text, keyboard);
      return null;
    }
  }

  async flushNotifications() {
    const items = await this.db.listNotifications();
    for (const item of items) {
      try {
        await this.tg.send(item.chat_id, item.text, item.reply_markup ?? undefined);
        await this.db.completeNotification(item._id);
      } catch (error) {
        await this.db.retryNotification(item._id, item.attempts ?? 0);
        this.logger.warn("Navbatdagi xabar yuborilmadi", error.message);
      }
    }
  }

  async safeAnswer(id, text = "", alert = false) {
    if (!id) return null;
    try { return await this.tg.answer(id, text, alert); }
    catch (error) { this.logger.warn("Callback javobi yuborilmadi", error.message); return null; }
  }
}
