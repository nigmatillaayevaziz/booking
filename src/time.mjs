export function localIso(date = new Date(), timeZone = "Asia/Tashkent") {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}:${get("second")}`;
}

export function parseAdminDate(value) {
  const match = value.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})$/);
  if (!match) return null;
  const [, day, month, year, hour, minute] = match;
  const numbers = [year, month, day, hour, minute].map(Number);
  const [y, m, d, h, min] = numbers;
  if (m < 1 || m > 12 || d < 1 || d > 31 || h > 23 || min > 59) return null;
  const check = new Date(Date.UTC(y, m - 1, d, h, min));
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== m - 1 || check.getUTCDate() !== d) return null;
  return `${year}-${month}-${day}T${hour}:${minute}:00`;
}

const MONTHS = Object.freeze({
  yanvar: 1,
  fevral: 2,
  mart: 3,
  aprel: 4,
  may: 5,
  iyun: 6,
  iyul: 7,
  avgust: 8,
  sentabr: 9,
  sentyabr: 9,
  oktabr: 10,
  noyabr: 11,
  dekabr: 12,
});

export function parsePassengerDateTime(value, nowIso = localIso(), maximumDays = 30) {
  const text = String(value ?? "").trim().toLocaleLowerCase("uz-UZ").replace(/\s+/g, " ");
  let match = text.match(/^(\d{1,2})[.\/-](\d{1,2})(?:[.\/-](\d{2,4}))?\s+(?:soat\s+)?(\d{1,2}):(\d{2})$/u);
  let day;
  let month;
  let year;
  let hour;
  let minute;
  if (match) {
    [, day, month, year, hour, minute] = match;
  } else {
    match = text.match(/^(\d{1,2})[\s-]+([\p{L}‘’ʻʼ']+)(?:[\s-]+(\d{4}))?\s+(?:soat\s+)?(\d{1,2}):(\d{2})$/u);
    if (!match) return null;
    day = match[1];
    month = MONTHS[match[2]];
    year = match[3];
    hour = match[4];
    minute = match[5];
  }
  const [nowDate] = nowIso.split("T");
  const nowYear = Number(nowDate.slice(0, 4));
  let numericYear = year ? Number(year.length === 2 ? `20${year}` : year) : nowYear;
  const numericMonth = Number(month);
  const numericDay = Number(day);
  const numericHour = Number(hour);
  const numericMinute = Number(minute);
  const build = () => `${numericYear}-${String(numericMonth).padStart(2, "0")}-${String(numericDay).padStart(2, "0")}`
    + `T${String(numericHour).padStart(2, "0")}:${String(numericMinute).padStart(2, "0")}:00`;
  let candidate = build();
  if (!year && candidate <= nowIso) {
    numericYear += 1;
    candidate = build();
  }
  if (numericMonth < 1 || numericMonth > 12 || numericHour > 23 || numericMinute > 59) return null;
  const check = new Date(Date.UTC(numericYear, numericMonth - 1, numericDay, numericHour, numericMinute));
  if (check.getUTCFullYear() !== numericYear || check.getUTCMonth() !== numericMonth - 1
      || check.getUTCDate() !== numericDay) return null;
  const candidateTime = Date.parse(`${candidate}Z`);
  const nowTime = Date.parse(`${nowIso}Z`);
  if (candidateTime <= nowTime || candidateTime - nowTime > maximumDays * 86_400_000) return null;
  return candidate;
}

export function showDateTime(iso) {
  const [date, time = ""] = iso.split("T");
  const [year, month, day] = date.split("-");
  return `${day}.${month}.${year} ${time.slice(0, 5)}`;
}

