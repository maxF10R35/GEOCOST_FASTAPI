// Genera casos de paridad ejecutando el motor JS actual (fuente de verdad durante la migración).
// Uso (desde la raíz del repo):  node tools/generar_golden.js legacy/imt-cost-model.js backend/tests/golden/quote_cases.json
const fs = require('fs');
const path = require('path');
const G = require(path.resolve(process.argv[2]));
const out = path.resolve(process.argv[3]);
let s = 20261029;
const rnd = () => { s |= 0; s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const pick = a => a[Math.floor(rnd() * a.length)];
const between = (a, b) => a + rnd() * (b - a);
const types = ['Camioneta', 'Rabón', 'Torton', 'Tráiler', 'Full'];
const caps = { Camioneta: 5, 'Rabón': 9, Torton: 18, 'Tráiler': 28, Full: 50 };
const classes = ['urbano', 'autopista_sin', 'autopista_con', 'pavimento_sin', 'pavimento_con', 'terraceria_sin', 'terraceria_con'];
const cases = [];
const add = (name, input) => {
  let expected;
  try { expected = G.quote(input); } catch (e) { expected = { error: e.message }; }
  cases.push({ name, input, expected });
};
for (let i = 0; i < 260; i++) {
  const type = i % 40 === 39 ? 'Desconocido' : types[i % 5];
  const cap = caps[type] || 9;
  const km = Math.round(between(5, 900) * 10) / 10;
  const inp = { type, km, loadTons: Math.round(between(0.1, 1) * cap * 100) / 100, year: pick([2000, 2008, 2015, 2019, 2022, 2026, 2015.6]),
    cargoType: pick(['sacos', 'granel', undefined]), dieselPrice: Math.round(between(22, 32) * 100) / 100 };
  if (rnd() < .6) {
    let left = km * (rnd() < .06 ? 1.3 : between(.4, 1)); const rows = [];
    for (const c of classes) { if (rnd() < .5) { const k = Math.round(left * rnd() * 100) / 100; left -= k; rows.push({ id: c, km: k }); } }
    inp.rows = rows;
  }
  if (rnd() < .65) { inp.elevationAvailable = true; inp.ascent = Math.round(between(0, km * 25)); inp.descent = Math.round(between(0, km * 25)); }
  else if (rnd() < .2) { inp.elevationAvailable = true; inp.ascent = null; inp.descent = 120; }
  if (rnd() < .5) inp.travelHours = Math.round(between(.5, km / 40) * 100) / 100;
  if (rnd() < .4) inp.dieselPriceIncludesIVA = pick([true, false, 'true']);
  if (rnd() < .5) { inp.tollsOneWay = Math.round(between(0, 1500)); inp.tollsPriceIncludesIVA = pick([true, false]); inp.tollStatus = pick(['ok', 'partial', 'pending', 'no-registrado']); }
  if (rnd() < .4) { inp.operatorMode = 'variable'; inp.operatorPerKm = Math.round(between(0, 6) * 100) / 100; }
  if (rnd() < .5) inp.utility = pick([0, .05, .08, .15, .6, -1]);
  if (rnd() < .35) { inp.carrierAdminFactor = pick([.7, 1, 1.28]); inp.carrierPatioFactor = pick([.65, 1, 1.35]); inp.carrierUtilizationFactor = pick([.88, 1, 1.08, .05]); }
  if (rnd() < .2) inp.carrierFactor = 1.1;
  if (rnd() < .4) inp.tierPremiums = { CP: pick([4, 5, null]), B: pick([9, 12]), SPOT: pick([20, 150, -5]) };
  if (rnd() < .35) Object.assign(inp, { handlingHours: pick([0, 2, 4.5]), extraWaitHours: pick([0, 1.5]), idleEnabled: pick([0, 1]), hillSensitivity: pick([6, 12, 20]), maintenanceRate: pick([1.5, 3]), suspensionShare: pick([0, .18, .9]), defFraction: pick([0, .03]), lubricantsRate: .5, viaticoDia: 400, viaticoUmbralHrs: pick([6, 8]), maniobras: pick([0, 180]), custodia: pick([0, 500]), lavado: 60, riskExpense: pick([0, 250]), fixedWorkshopLabor: pick([0, 3000]), kmMonth: pick([5000, 8000]), daysMonth: 24, hoursPerDay: 9 });
  if (rnd() < .3) { const m = {}; for (const k of ['fixed', 'diesel', 'maintenance', 'suspension', 'tires', 'lubricants', 'def', 'tolls', 'serviceMisc', 'riskCost', 'inexistente']) if (rnd() < .2) m[k] = pick([0, 850.5, '', null, '300']); inp.manualCosts = m; }
  add('aleatorio_' + i, inp);
}
const base = { type: 'Rabón', km: 53.4, loadTons: 9, year: 2022, dieselPrice: 26.99 };
add('error_km_cero', { ...base, km: 0 });
add('error_sobrecarga', { ...base, loadTons: 12 });
add('error_anio_1999', { ...base, year: 1999 });
add('error_anio_2027', { ...base, year: 2027 });
add('error_diesel_bajo', { ...base, dieselPrice: 5 });
add('error_diesel_ausente', { type: 'Rabón', km: 10, loadTons: 5, year: 2022 });
add('error_manual_negativo', { ...base, manualCosts: { tolls: -5 } });
add('error_manual_texto', { ...base, manualCosts: { tolls: 'abc' } });
add('error_clases_exceden', { ...base, rows: [{ id: 'urbano', km: 60 }] });
add('referencia_rabon_53km', { ...base, travelHours: 1, rows: [{ id: 'autopista_sin', km: 40 }, { id: 'pavimento_sin', km: 13.4 }] });
add('referencia_trailer_250km', { type: 'Tráiler', km: 250, loadTons: 28, year: 2022, dieselPrice: 26.99, travelHours: 3.9, tollsOneWay: 680, ascent: 1800, descent: 900, elevationAvailable: true, rows: [{ id: 'autopista_sin', km: 150 }, { id: 'autopista_con', km: 80 }, { id: 'urbano', km: 20 }] });
fs.writeFileSync(out, JSON.stringify(cases));
const errs = cases.filter(c => c.expected.error).length;
console.log(`casos: ${cases.length} (con error esperado: ${errs}) -> ${out} (${(fs.statSync(out).size / 1e6).toFixed(2)} MB)`);
