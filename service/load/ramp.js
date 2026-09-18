
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const ENDPOINT = __ENV.ENDPOINT || 'recommend';
const RATES = (__ENV.RATES || '100,200,300,500,1000').split(',').map(Number);
const STEP_SECONDS = Number(__ENV.STEP_SECONDS || 60);
const DRAIN_SECONDS = Number(__ENV.DRAIN_SECONDS || 15);
const WARMUP_SECONDS = Number(__ENV.WARMUP_SECONDS || 90);
const WARMUP_RATE = Number(__ENV.WARMUP_RATE || 50);

const P99_BUDGET_MS = Number(__ENV.P99_BUDGET_MS || 1000);
const ERROR_BUDGET = Number(__ENV.ERROR_BUDGET || 0.01);
const THROUGHPUT_FLOOR = Number(__ENV.THROUGHPUT_FLOOR || 0.95);
const BACKFILL_CEILING = Number(__ENV.BACKFILL_CEILING || 4);

const N_USERS = Number(__ENV.N_USERS || 3000);
const N_ITEMS = Number(__ENV.N_ITEMS || 20000);
const ZIPF_S = Number(__ENV.ZIPF_S || 1.1);

const MAX_VUS = Number(__ENV.MAX_VUS || 4000);

const candidates = new Trend('candidates_considered');
const backfilled = new Trend('backfilled_items');


function zipfItem() {
  const u = Math.random();
  const rank = Math.floor(Math.pow(u, ZIPF_S) * N_ITEMS);
  return 1 + Math.min(rank, N_ITEMS - 1);
}

function randomUser() {
  return 1 + Math.floor(Math.random() * N_USERS);
}

const KINDS = ['view', 'view', 'view', 'cart', 'purchase', 'dislike'];


function buildScenarios() {
  const scenarios = {
    warmup: {
      executor: 'constant-arrival-rate',
      rate: WARMUP_RATE,
      timeUnit: '1s',
      duration: `${WARMUP_SECONDS}s`,
      preAllocatedVUs: Math.max(50, WARMUP_RATE),
      maxVUs: MAX_VUS,
      exec: 'hit',
      tags: { phase: 'warmup' },
      startTime: '0s',
      gracefulStop: '10s',
    },
  };
  let at = WARMUP_SECONDS + DRAIN_SECONDS;
  for (const rate of RATES) {
    scenarios[`rate_${rate}`] = {
      executor: 'constant-arrival-rate',
      rate: rate,
      timeUnit: '1s',
      duration: `${STEP_SECONDS}s`,
      preAllocatedVUs: Math.min(MAX_VUS, Math.max(100, Math.ceil(rate * 1.5))),
      maxVUs: MAX_VUS,
      exec: 'hit',
      tags: { phase: 'measure', rate: String(rate) },
      startTime: `${at}s`,
      gracefulStop: '10s',
    };
    at += STEP_SECONDS + DRAIN_SECONDS;
  }
  return scenarios;
}

function buildThresholds() {
  const t = {
    'http_req_failed{phase:measure}': [
      { threshold: `rate<${ERROR_BUDGET}`, abortOnFail: false },
    ],
  };
  for (const rate of RATES) {
    t[`http_req_duration{phase:measure,rate:${rate}}`] = [
      { threshold: `p(99)<${P99_BUDGET_MS}`, abortOnFail: false },
    ];
    t[`http_req_failed{phase:measure,rate:${rate}}`] = [
      { threshold: `rate<${ERROR_BUDGET}`, abortOnFail: false },
    ];
    t[`dropped_iterations{phase:measure,rate:${rate}}`] = [
      { threshold: `count<${rate * STEP_SECONDS * (1 - THROUGHPUT_FLOOR)}`,
        abortOnFail: false },
    ];
    t[`http_reqs{phase:measure,rate:${rate}}`] = [
      { threshold: 'count>=0', abortOnFail: false },
    ];
    t[`backfilled_items{phase:measure,rate:${rate}}`] = [
      { threshold: `avg<${BACKFILL_CEILING}`, abortOnFail: false },
    ];
    t[`candidates_considered{phase:measure,rate:${rate}}`] = [
      { threshold: 'avg>=0', abortOnFail: false },
    ];
  }
  return t;
}

export const options = {
  scenarios: buildScenarios(),
  thresholds: buildThresholds(),
  discardResponseBodies: false,
  summaryTrendStats: ['min', 'med', 'p(90)', 'p(95)', 'p(99)', 'p(99.9)', 'max', 'avg'],
};


const JSON_HEADERS = { headers: { 'Content-Type': 'application/json' } };

export function hit() {
  let res;
  if (ENDPOINT === 'recommend') {
    res = http.post(`${BASE}/v1/recommendations`,
      JSON.stringify({ user_id: randomUser(), limit: 20 }), JSON_HEADERS);
  } else if (ENDPOINT === 'similar') {
    res = http.get(`${BASE}/v1/items/${zipfItem()}/similar?limit=20`);
  } else if (ENDPOINT === 'bundle') {
    res = http.get(`${BASE}/v1/items/${zipfItem()}/bundle?limit=24`);
  } else if (ENDPOINT === 'events') {
    res = http.post(`${BASE}/v1/events`, JSON.stringify({
      user_id: randomUser(),
      item_id: zipfItem(),
      kind: KINDS[Math.floor(Math.random() * KINDS.length)],
    }), JSON_HEADERS);
  } else {
    throw new Error(`unknown ENDPOINT ${ENDPOINT}`);
  }

  const ok = check(res, {
    'status ok': (r) => r.status === 200 || r.status === 201,
  });

  if (ok && ENDPOINT !== 'events' && res.body && res.body.length < 200000) {
    try {
      const meta = res.json('meta');
      if (meta) {
        if (meta.candidates_considered !== undefined) {
          candidates.add(meta.candidates_considered);
        }
        if (meta.backfilled !== undefined) backfilled.add(meta.backfilled);
      }
    } catch (_) {
    }
  }
}


export function handleSummary(data) {
  const steps = [];
  for (const rate of RATES) {
    const dur = data.metrics[`http_req_duration{phase:measure,rate:${rate}}`];
    const failed = data.metrics[`http_req_failed{phase:measure,rate:${rate}}`];
    const dropped = data.metrics[`dropped_iterations{phase:measure,rate:${rate}}`];
    const reqs = data.metrics[`http_reqs{phase:measure,rate:${rate}}`];
    const backfill = data.metrics[`backfilled_items{phase:measure,rate:${rate}}`];

    const completed = reqs ? reqs.values.count : 0;
    const wanted = rate * STEP_SECONDS;
    const delivered = wanted > 0 ? completed / wanted : 0;
    const droppedCount = dropped ? dropped.values.count : 0;

    const reasons = [];
    if (completed === 0) {
      reasons.push('no completed requests in the window');
    }
    const p99 = dur && completed > 0 ? dur.values['p(99)'] : null;
    const errorRate = failed ? failed.values.rate : 0;
    if (p99 !== null && p99 >= P99_BUDGET_MS) reasons.push(`p99=${p99.toFixed(1)}ms`);
    if (errorRate >= ERROR_BUDGET) reasons.push(`errors=${(errorRate * 100).toFixed(2)}%`);
    if (delivered < THROUGHPUT_FLOOR) {
      reasons.push(`delivered=${(delivered * 100).toFixed(1)}%`);
    }
    const backfillAvg = backfill && completed > 0 ? backfill.values.avg : null;
    if (backfillAvg !== null && backfillAvg >= BACKFILL_CEILING) {
      reasons.push(`backfill=${backfillAvg.toFixed(1)}/page`);
    }

    steps.push({
      rate, passed: reasons.length === 0, reasons,
      completed, offered: wanted,
      p50: dur && completed > 0 ? dur.values.med : null,
      p90: dur && completed > 0 ? dur.values['p(90)'] : null,
      p99,
      p999: dur && completed > 0 ? dur.values['p(99.9)'] : null,
      mean: dur && completed > 0 ? dur.values.avg : null,
      max: dur && completed > 0 ? dur.values.max : null,
      error_rate: errorRate, dropped: droppedCount, delivered_share: delivered,
      backfill_per_page: backfillAvg,
      candidates_considered: (() => {
        const c = data.metrics[`candidates_considered{phase:measure,rate:${rate}}`];
        return c && completed > 0 ? c.values.avg : null;
      })(),
    });
  }

  let capacity = 0;
  for (const s of steps) {
    if (!s.passed) break;
    capacity = s.rate;
  }
  const nonMonotonic = steps.some((s, i) => !s.passed && steps.slice(i + 1).some(x => x.passed));

  const verdict = {
    endpoint: ENDPOINT,
    base_url: BASE,
    criterion: {
      p99_budget_ms: P99_BUDGET_MS,
      error_budget: ERROR_BUDGET,
      throughput_floor: THROUGHPUT_FLOOR,
      backfill_ceiling: BACKFILL_CEILING,
      declared: 'before any number existed',
    },
    profile: {
      rates: RATES, step_seconds: STEP_SECONDS, drain_seconds: DRAIN_SECONDS,
      warmup_seconds: WARMUP_SECONDS, warmup_rate: WARMUP_RATE,
      zipf_s: ZIPF_S, n_users: N_USERS, n_items: N_ITEMS,
      model: 'open (constant-arrival-rate)',
    },
    capacity_rps: capacity,
    non_monotonic: nonMonotonic,
    steps,
  };

  const lines = [`\n=== ${ENDPOINT}: capacity ${capacity} rps ===`];
  const fmt = (v, w) => (v === null ? '-'.padStart(w) : v.toFixed(1).padStart(w));
  for (const s of steps) {
    lines.push(
      `  ${String(s.rate).padStart(6)} rps  ` +
      `p50=${fmt(s.p50, 7)}ms  p99=${fmt(s.p99, 8)}ms  ` +
      `p999=${fmt(s.p999, 8)}ms  ` +
      `err=${(s.error_rate * 100).toFixed(2).padStart(5)}%  ` +
      `done=${String(s.completed).padStart(5)}/${String(s.offered).padEnd(5)}  ` +
      `bf=${s.backfill_per_page === null ? '-' : s.backfill_per_page.toFixed(1)}  ` +
      (s.passed ? 'pass' : `FAIL ${s.reasons.join(' ')}`));
  }
  if (nonMonotonic) {
    lines.push('  NOTE: a later step passed after an earlier one failed; ' +
               'this service is not monotonic in offered load');
  }

  return {
    stdout: lines.join('\n') + '\n',
    [`${__ENV.OUT_DIR || 'load/results'}/${__ENV.RUN_TAG || 'run'}-${ENDPOINT}.json`]:
      JSON.stringify(verdict, null, 1),
  };
}
