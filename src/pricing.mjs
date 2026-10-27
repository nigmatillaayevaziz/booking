const REGION_CENTERS = Object.freeze({
  "Toshkent shahri": [41.2995, 69.2401],
  "Toshkent viloyati": [41.047, 69.356],
  Andijon: [40.7821, 72.3442],
  Buxoro: [39.7681, 64.4556],
  "Farg‘ona": [40.3894, 71.787],
  Jizzax: [40.1158, 67.8422],
  Qashqadaryo: [38.8606, 65.789],
  Navoiy: [40.1039, 65.3688],
  Namangan: [40.9983, 71.6726],
  Samarqand: [39.6542, 66.9597],
  Sirdaryo: [40.4897, 68.7842],
  Surxondaryo: [37.2242, 67.2783],
  Xorazm: [41.55, 60.633],
  "Qoraqalpog‘iston Respublikasi": [42.4619, 59.6166],
});

const radians = (degrees) => degrees * Math.PI / 180;

export function routeDistanceKm(origin, destination) {
  const from = REGION_CENTERS[origin];
  const to = REGION_CENTERS[destination];
  if (!from || !to || origin === destination) return null;
  const [lat1, lon1] = from.map(radians);
  const [lat2, lon2] = to.map(radians);
  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;
  const value = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  const straightLine = 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
  return Math.max(20, Math.round(straightLine * 1.22 / 10) * 10);
}

export function calculateRouteFare(origin, destination) {
  const distanceKm = routeDistanceKm(origin, destination);
  if (distanceKm == null) return null;
  const rawPrice = Math.max(70_000, 30_000 + distanceKm * 550);
  const unitPrice = Math.ceil(rawPrice / 5_000) * 5_000;
  return Object.freeze({ distanceKm, unitPrice });
}
