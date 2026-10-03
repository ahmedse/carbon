// Drift guard — the Progress canvas must mirror the committed evidence under
// docs/pulse/evidence/, never an invented number. This test reads those files
// and fails the moment the mirror in pulseProgressEvidence.js falls behind.
import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { buildPulseProgress, PULSE_LADDER_LEVELS } from '../pulseProgressEvidence';

// Walk up from the test process cwd to the repo's committed evidence dir. Vite
// rewrites `import.meta.url` to a `/@fs/...` URL, so fs paths must not rely on it.
function evidenceDir() {
  let dir = process.cwd();
  for (let i = 0; i < 6; i += 1) {
    const candidate = join(dir, 'docs', 'pulse', 'evidence');
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error(`docs/pulse/evidence not found from ${process.cwd()}`);
}

const readEvidence = (name) => JSON.parse(readFileSync(join(evidenceDir(), name), 'utf8'));

describe('pulseProgressEvidence drift guard', () => {
  it('mirrors the latest gauge-series ladder row (L0–L5)', () => {
    const gauge = readEvidence('PV2-gauge-series.json');
    const latest = gauge.rows[gauge.rows.length - 1];
    const { ladder } = buildPulseProgress();

    expect(ladder.measuredAt).toBe(latest.date);
    expect(ladder.instance).toBe(latest.instance);
    PULSE_LADDER_LEVELS.forEach((id) => {
      expect(ladder.levels.find((level) => level.id === id).status).toBe(latest.levels[id]);
    });
    expect(ladder.metrics.g6Accuracy).toBe(latest.g6_accuracy);
    expect(ladder.metrics.g6Parity).toBe(latest.g6_parity);
    expect(ladder.metrics.g5Turns).toBe(latest.g5_turns);
    expect(ladder.metrics.sixBStreak).toBe(latest.six_b_streak);
    expect(ladder.metrics.packsOk).toBe(latest.packs_ok);
    expect(ladder.metrics.agentPlan).toBe(latest.agent_plan);
    // ADR-0049: L6/L7 are never claimed here.
    expect(ladder.levels.map((level) => level.id)).not.toContain('L6');
    expect(ladder.beyond).toEqual(['L6', 'L7']);
  });

  it('mirrors the IB-04 / IB-05 intention banks thread-for-thread', () => {
    const { intention, intentionTotals } = buildPulseProgress();

    intention.forEach((bank) => {
      const src = readEvidence(bank.source.split('/').pop());
      expect(bank.bank).toBe(src.bank);
      expect(bank.runAt).toBe(src.run_at);
      expect(bank.passed).toBe(src.passed);
      expect(bank.total).toBe(src.total);
      expect(bank.pass).toBe(src.pass);
      expect(bank.latency.p50Ms).toBe(src.latency.p50_ms);
      expect(bank.latency.over4s).toBe(src.latency.over_4s);
      expect(bank.latency.llmCallsP50).toBe(src.latency.llm_calls_p50);
      expect(bank.threads.map((thread) => thread.id)).toEqual(src.threads.map((thread) => thread.id));
      expect(bank.threads.map((thread) => thread.pass)).toEqual(src.threads.map((thread) => thread.pass));
      expect(bank.threads.map((thread) => thread.decision)).toEqual(
        src.threads.map((thread) => thread.turns[0].turn_decision),
      );
    });

    const srcTotals = intention.reduce((acc, bank) => {
      const src = readEvidence(bank.source.split('/').pop());
      return { passed: acc.passed + src.passed, total: acc.total + src.total };
    }, { passed: 0, total: 0 });
    expect(intentionTotals).toEqual(srcTotals);
  });

  it('mirrors the 6B soak nights', () => {
    const soakSrc = readEvidence('PV2-6B-nights.json');
    const { soak } = buildPulseProgress();

    expect(soak.required).toBe(soakSrc.required_consecutive);
    expect(soak.soakComplete).toBe(soakSrc.soak_complete);
    const green = soakSrc.nights.filter((night) => night.status === 'PASS');
    expect(soak.consecutiveGreen).toBe(green[green.length - 1].consecutive_green);
    expect(soak.greenNights).toEqual(green.map((night) => night.night_id));
    expect(soak.lastFailNight).toBe(soakSrc.nights.find((night) => night.status !== 'PASS').night_id);
  });
});
