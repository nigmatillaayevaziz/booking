import { randomBytes } from "node:crypto";

import { localIso } from "./time.mjs";
import { calculateRouteFare } from "./pricing.mjs";

export class BookingError extends Error {}

const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase("uz-UZ");
const duplicateKey = (error) => error?.code === 11000;

export class Database {
  static async connect(uri, databaseName, timeZone = "Asia/Tashkent") {
    let driver;
    try {
      driver = await import("mongodb");
    } catch (error) {
      throw new Error("MongoDB drayveri o‘rnatilmagan. `npm.cmd install` buyrug‘ini bajaring.", { cause: error });
    }
    const { MongoClient, ServerApiVersion } = driver;
    const client = new MongoClient(uri, {
      serverApi: { version: ServerApiVersion.v1 },
      maxPoolSize: 10,
      serverSelectionTimeoutMS: 10_000,
      connectTimeoutMS: 10_000,
    });
    await client.connect();
    await client.db("admin").command({ ping: 1 });
    const database = new Database(client, client.db(databaseName), timeZone);
    await database.ensureIndexes();
    return database;
  }

  constructor(client, db, timeZone = "Asia/Tashkent") {
    this.client = client;
    this.db = db;
    this.timeZone = timeZone;
    this.users = db.collection("users");
    this.routes = db.collection("routes");
    this.routePrices = db.collection("route_prices");
    this.trips = db.collection("trips");
    this.bookings = db.collection("bookings");
    this.counters = db.collection("counters");
    this.sessions = db.collection("sessions");
    this.settings = db.collection("settings");
    this.outbox = db.collection("notification_outbox");
  }

  async ensureIndexes() {
    await Promise.all([
      this.routes.createIndex({ origin_key: 1, destination_key: 1 }, { unique: true }),
      this.routePrices.createIndex({ origin_key: 1, destination_key: 1 }, { unique: true }),
      this.trips.createIndex({ route_id: 1, departure_at: 1 }),
      this.bookings.createIndex({ code: 1 }, { unique: true }),
      this.bookings.createIndex({ user_id: 1, created_at: -1 }),
      this.bookings.createIndex({ status: 1, created_at: 1 }),
      this.sessions.createIndex({ updated_at: 1 }, { expireAfterSeconds: 86_400 }),
      this.outbox.createIndex({ status: 1, next_attempt_at: 1 }),
    ]);
  }

  async close() { await this.client.close(); }
  now() { return localIso(new Date(), this.timeZone); }

  async nextId(name, session = undefined) {
    const row = await this.counters.findOneAndUpdate(
      { _id: name }, { $inc: { value: 1 } },
      { upsert: true, returnDocument: "after", session },
    );
    return Number(row.value);
  }

  async seedDemoData() {
    if (await this.routes.estimatedDocumentCount() > 0) return;
    const samples = [["Toshkent", "Samarqand"], ["Toshkent", "Buxoro"], ["Samarqand", "Toshkent"]];
    for (const [origin, destination] of samples) {
      const routeId = await this.createRoute(origin, destination);
      for (const [day, hour] of [[1, 8], [2, 14], [3, 20]]) {
        const date = new Date(Date.now() + day * 86_400_000);
        const base = localIso(date, this.timeZone).slice(0, 10);
        await this.createTrip(routeId, `${base}T${String(hour).padStart(2, "0")}:00:00`, "Comfort Bus", 120_000, 45);
      }
    }
  }

  async upsertUser(user) {
    const now = new Date();
    await this.users.updateOne({ _id: user.id }, {
      $set: {
        full_name: [user.first_name, user.last_name].filter(Boolean).join(" "),
        username: user.username ?? null,
        updated_at: now,
      },
      $setOnInsert: { created_at: now },
    }, { upsert: true });
  }

  async setPhone(userId, phone) {
    await this.users.updateOne({ _id: userId }, { $set: { phone, updated_at: new Date() } });
  }

  async listOrigins() {
    const tripRoutes = await this.trips.distinct("route_id", {
      active: true, available_seats: { $gt: 0 }, departure_at: { $gt: this.now() }, type: "scheduled",
    });
    const rows = await this.routes.find({ _id: { $in: tripRoutes }, active: true }).sort({ origin: 1 }).toArray();
    const unique = new Map();
    for (const row of rows) if (!unique.has(row.origin_key)) unique.set(row.origin_key, { route_id: row._id, origin: row.origin });
    return [...unique.values()];
  }

  async listDestinations(routeId) {
    const selected = await this.routes.findOne({ _id: Number(routeId), active: true });
    if (!selected) return [];
    const routes = await this.routes.find({ origin_key: selected.origin_key, active: true }).sort({ destination: 1 }).toArray();
    const ids = routes.map((route) => route._id);
    const liveIds = new Set(await this.trips.distinct("route_id", {
      route_id: { $in: ids }, active: true, available_seats: { $gt: 0 }, departure_at: { $gt: this.now() }, type: "scheduled",
    }));
    return routes.filter((route) => liveIds.has(route._id)).map((route) => ({ id: route._id, destination: route.destination }));
  }

  async getRoute(id) {
    const route = await this.routes.findOne({ _id: Number(id) });
    return route ? { ...route, id: route._id } : null;
  }

  async listRoutes() {
    return (await this.routes.find({ active: true }).sort({ origin: 1, destination: 1 }).toArray())
      .map((route) => ({ ...route, id: route._id }));
  }

  async listRouteCatalog(limit = 20) {
    const summaries = await this.trips.aggregate([
      {
        $match: {
          type: "scheduled",
          active: true,
          available_seats: { $gt: 0 },
          departure_at: { $gt: this.now() },
        },
      },
      {
        $group: {
          _id: "$route_id",
          trips: { $sum: 1 },
          available_seats: { $sum: "$available_seats" },
          minimum_price: { $min: "$price" },
          nearest_departure: { $min: "$departure_at" },
        },
      },
      { $sort: { nearest_departure: 1 } },
      { $limit: Math.max(1, Math.min(Number(limit) || 20, 50)) },
    ]).toArray();
    if (!summaries.length) return [];
    const routes = await this.routes.find({
      _id: { $in: summaries.map((item) => item._id) },
      active: true,
    }).toArray();
    const routeById = new Map(routes.map((route) => [route._id, route]));
    return summaries.flatMap((item) => {
      const route = routeById.get(item._id);
      return route ? [{
        id: route._id,
        origin: route.origin,
        destination: route.destination,
        trips: item.trips,
        available_seats: item.available_seats,
        minimum_price: item.minimum_price,
        nearest_departure: item.nearest_departure,
      }] : [];
    });
  }

  async getRoutePrice(origin, destination) {
    const originKey = normalize(origin);
    const destinationKey = normalize(destination);
    const override = await this.routePrices.findOne({
      $or: [
        { origin_key: originKey, destination_key: destinationKey },
        { origin_key: destinationKey, destination_key: originKey },
      ],
      active: { $ne: false },
    });
    if (override) {
      return {
        distanceKm: Number(override.distance_km),
        unitPrice: Number(override.unit_price),
        source: "configured",
      };
    }
    const calculated = calculateRouteFare(origin, destination);
    if (!calculated) throw new BookingError("Bu yo‘nalish uchun narx hisoblab bo‘lmadi.");
    return { ...calculated, source: "distance" };
  }

  async listTripDates(routeId) {
    const dates = await this.trips.distinct("trip_date", {
      route_id: Number(routeId), type: "scheduled", active: true,
      available_seats: { $gt: 0 }, departure_at: { $gt: this.now() },
    });
    return dates.sort().slice(0, 14);
  }

  async listTrips(routeId, date) {
    return (await this.trips.find({
      route_id: Number(routeId), trip_date: date, type: "scheduled", active: true,
      available_seats: { $gt: 0 }, departure_at: { $gt: this.now() },
    }).sort({ departure_at: 1 }).toArray()).map((trip) => ({ ...trip, id: trip._id }));
  }

  async getTrip(id, session = undefined) {
    const trip = await this.trips.findOne({ _id: Number(id) }, { session });
    if (!trip) return null;
    const route = await this.routes.findOne({ _id: trip.route_id }, { session });
    return { ...trip, id: trip._id, origin: route?.origin, destination: route?.destination };
  }

  async createRoute(origin, destination) {
    origin = String(origin).trim();
    destination = String(destination).trim();
    if (!origin || !destination || normalize(origin) === normalize(destination)) throw new BookingError("Yo‘nalish noto‘g‘ri.");
    const id = await this.nextId("routes");
    try {
      await this.routes.insertOne({
        _id: id, origin, destination, origin_key: normalize(origin), destination_key: normalize(destination),
        active: true, created_at: new Date(),
      });
      return id;
    } catch (error) {
      if (duplicateKey(error)) throw new BookingError("Bu yo‘nalish allaqachon mavjud.");
      throw error;
    }
  }

  async createTrip(routeId, departureAt, vehicle, price, seats) {
    if (departureAt <= this.now()) throw new BookingError("Safar vaqti kelajakda bo‘lishi kerak.");
    if (!Number.isInteger(price) || price < 0 || !Number.isInteger(seats) || seats < 1 || seats > 100) throw new BookingError("Reys ma’lumotlari noto‘g‘ri.");
    if (!await this.routes.findOne({ _id: Number(routeId), active: true })) throw new BookingError("Yo‘nalish topilmadi.");
    const id = await this.nextId("trips");
    await this.trips.insertOne({
      _id: id, route_id: Number(routeId), departure_at: departureAt, trip_date: departureAt.slice(0, 10),
      vehicle_name: String(vehicle).trim(), price, total_seats: seats, available_seats: seats,
      type: "scheduled", active: true, created_at: new Date(),
    });
    return id;
  }

  async createCustomBooking({ userId, origin, destination, departureAt, seats, passengerName, phone }) {
    this.validateBooking(origin, destination, departureAt, seats);
    const fare = await this.getRoutePrice(origin, destination);
    const id = await this.nextId("bookings");
    const booking = {
      _id: id, code: await this.uniqueCode(), user_id: userId, trip_id: null, type: "custom",
      origin, destination, departure_at: departureAt, vehicle_name: "Shaxsiy taxi",
      seats, passenger_name: passengerName, phone,
      distance_km: fare.distanceKm, unit_price: fare.unitPrice, total_price: fare.unitPrice * seats,
      price_source: fare.source, status: "pending", created_at: new Date(), updated_at: new Date(),
    };
    await this.bookings.insertOne(booking);
    return this.formatBooking(booking);
  }

  validateBooking(origin, destination, departureAt, seats) {
    if (normalize(origin) === normalize(destination)) throw new BookingError("Jo‘nash va borish manzili bir xil bo‘lmasligi kerak.");
    if (departureAt <= this.now()) throw new BookingError("Safar vaqti kelajakda bo‘lishi kerak.");
    if (!Number.isInteger(seats) || seats < 1 || seats > 10) throw new BookingError("Bir buyurtmada 1–10 ta joy tanlash mumkin.");
  }

  async createBooking({ userId, tripId, seats, passengerName, phone }) {
    if (!Number.isInteger(seats) || seats < 1 || seats > 10) throw new BookingError("Bir buyurtmada 1–10 ta joy tanlash mumkin.");
    const session = this.client.startSession();
    let created;
    try {
      await session.withTransaction(async () => {
        const trip = await this.getTrip(tripId, session);
        if (!trip || !trip.active || trip.type !== "scheduled") throw new BookingError("Reys topilmadi yoki savdodan olib tashlangan.");
        if (trip.departure_at <= this.now()) throw new BookingError("Bu reys jo‘nab ketgan.");
        const update = await this.trips.updateOne(
          { _id: Number(tripId), available_seats: { $gte: seats }, active: true },
          { $inc: { available_seats: -seats } }, { session },
        );
        if (update.modifiedCount !== 1) throw new BookingError("Yetarli bo‘sh joy qolmadi.");
        const id = await this.nextId("bookings", session);
        created = {
          _id: id, code: await this.uniqueCode(session), user_id: userId, trip_id: Number(tripId), type: "scheduled",
          origin: trip.origin, destination: trip.destination, departure_at: trip.departure_at,
          vehicle_name: trip.vehicle_name, seats, passenger_name: passengerName, phone,
          unit_price: trip.price, total_price: trip.price * seats, status: "pending",
          created_at: new Date(), updated_at: new Date(),
        };
        await this.bookings.insertOne(created, { session });
      });
      return this.formatBooking(created);
    } finally {
      await session.endSession();
    }
  }

  async getBooking(id, session = undefined) {
    return this.formatBooking(await this.bookings.findOne({ _id: Number(id) }, { session }));
  }

  async listUserBookings(userId, limit = 10) {
    return (await this.bookings.find({ user_id: userId }).sort({ created_at: -1 }).limit(limit).toArray()).map((row) => this.formatBooking(row));
  }

  async listPending(limit = 20) {
    return (await this.bookings.find({ status: { $in: ["pending", "pending_price"] }, departure_at: { $gt: this.now() } })
      .sort({ created_at: 1 }).limit(limit).toArray()).map((row) => this.formatBooking(row));
  }

  async cancelBooking(id, userId) {
    return this.changeStatus(id, "cancelled", ["pending", "pending_price", "quoted", "confirmed"], userId);
  }

  async setBookingStatus(id, status) {
    if (status === "confirmed") return this.changeStatus(id, status, ["pending"]);
    if (status === "rejected") return this.changeStatus(id, status, ["pending", "pending_price"]);
    throw new Error("Noto‘g‘ri status");
  }

  async quoteBooking(id, totalPrice) {
    if (!Number.isInteger(totalPrice) || totalPrice < 1 || totalPrice > 1_000_000_000) throw new BookingError("Narx 1–1 000 000 000 so‘m oralig‘ida bo‘lsin.");
    const result = await this.bookings.updateOne(
      { _id: Number(id), type: "custom", status: "pending_price", departure_at: { $gt: this.now() } },
      { $set: { total_price: totalPrice, status: "quoted", updated_at: new Date() } },
    );
    return result.modifiedCount === 1;
  }

  async acceptQuote(id, userId) { return this.changeStatus(id, "confirmed", ["quoted"], userId); }
  async rejectQuote(id, userId) { return this.changeStatus(id, "cancelled", ["quoted"], userId); }

  async changeStatus(id, status, allowed, userId = null) {
    const session = this.client.startSession();
    let changed = false;
    try {
      await session.withTransaction(async () => {
        const filter = {
          _id: Number(id), status: { $in: allowed }, departure_at: { $gt: this.now() },
          ...(userId == null ? {} : { user_id: userId }),
        };
        const booking = await this.bookings.findOne(filter, { session });
        if (!booking) return;
        const update = await this.bookings.updateOne(filter, { $set: { status, updated_at: new Date() } }, { session });
        if (update.modifiedCount !== 1) return;
        if (booking.type === "scheduled" && ["cancelled", "rejected"].includes(status)) {
          await this.trips.updateOne({ _id: booking.trip_id }, { $inc: { available_seats: booking.seats } }, { session });
        }
        changed = true;
      });
      return changed;
    } finally {
      await session.endSession();
    }
  }

  async stats() {
    const now = this.now();
    const [users, activeTrips, pending, confirmed, revenueRows] = await Promise.all([
      this.users.estimatedDocumentCount(),
      this.trips.countDocuments({ type: "scheduled", active: true, departure_at: { $gt: now } }),
      this.bookings.countDocuments({ status: { $in: ["pending", "pending_price", "quoted"] }, departure_at: { $gt: now } }),
      this.bookings.countDocuments({ status: "confirmed" }),
      this.bookings.aggregate([{ $match: { status: "confirmed" } }, { $group: { _id: null, total: { $sum: "$total_price" } } }]).toArray(),
    ]);
    return { users, active_trips: activeTrips, pending, confirmed, revenue: revenueRows[0]?.total ?? 0 };
  }

  async uniqueCode(session = undefined) {
    const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const code = Array.from(randomBytes(8), (byte) => alphabet[byte % alphabet.length]).join("");
      if (!await this.bookings.findOne({ code }, { projection: { _id: 1 }, session })) return code;
    }
    throw new BookingError("Buyurtma kodi yaratilmadi. Qayta urinib ko‘ring.");
  }

  formatBooking(row) { return row ? { ...row, id: row._id } : null; }

  async getSession(userId) { return (await this.sessions.findOne({ _id: userId }))?.data ?? null; }
  async setSession(userId, data) {
    await this.sessions.updateOne({ _id: userId }, { $set: { data, updated_at: new Date() } }, { upsert: true });
    return data;
  }
  async deleteSession(userId) { await this.sessions.deleteOne({ _id: userId }); }

  async getBotOffset() { return Number((await this.settings.findOne({ _id: "telegram_offset" }))?.value ?? 0); }
  async setBotOffset(value) {
    await this.settings.updateOne({ _id: "telegram_offset" }, { $set: { value, updated_at: new Date() } }, { upsert: true });
  }

  async enqueueNotification(chatId, text, replyMarkup = undefined) {
    await this.outbox.insertOne({
      chat_id: chatId, text, reply_markup: replyMarkup ?? null, status: "pending", attempts: 0,
      next_attempt_at: new Date(), created_at: new Date(),
    });
  }
  async listNotifications(limit = 20) {
    return this.outbox.find({ status: "pending", next_attempt_at: { $lte: new Date() } }).sort({ created_at: 1 }).limit(limit).toArray();
  }
  async completeNotification(id) { await this.outbox.updateOne({ _id: id }, { $set: { status: "sent", sent_at: new Date() } }); }
  async retryNotification(id, attempts) {
    const delay = Math.min(3_600_000, 5000 * 2 ** Math.min(attempts, 8));
    await this.outbox.updateOne({ _id: id }, {
      $set: { status: attempts >= 10 ? "failed" : "pending", next_attempt_at: new Date(Date.now() + delay) },
      $inc: { attempts: 1 },
    });
  }
}
