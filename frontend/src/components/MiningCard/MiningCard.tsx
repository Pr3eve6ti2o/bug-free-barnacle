import { FC, useCallback, useEffect, useRef, useState } from 'react';
import { Pickaxe } from 'lucide-react';
import { miningApi, MiningStatus } from '@/services/api';
import { haptic } from '@/telegram/initTelegram';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  onClaimed: (newBalance: number) => void;
}

function fmtCountdown(totalSeconds: number): string {
  const s = Math.max(0, totalSeconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

export const MiningCard: FC<Props> = ({ telegramId, onClaimed }) => {
  const [status, setStatus] = useState<MiningStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const timerRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await miningApi.getStatus(telegramId);
      setStatus(s);
    } catch {
      /* offline — keep last state */
    } finally {
      setLoading(false);
    }
  }, [telegramId]);

  useEffect(() => {
    load();
    timerRef.current = window.setInterval(() => setTick(t => t + 1), 1000);
    return () => { if (timerRef.current) window.clearInterval(timerRef.current); };
  }, [load]);

  // refresh status when the countdown likely finished
  useEffect(() => {
    if (status?.state === 'active' && status.seconds_left !== undefined && status.seconds_left <= 1) {
      load();
    }
  }, [tick, status, load]);

  const startMining = async () => {
    setBusy(true); setError('');
    try {
      await miningApi.start(telegramId);
      haptic('tap');
      await load();
    } catch (e: any) {
      setError(e?.detail || 'Could not start mining. Try again.');
    } finally { setBusy(false); }
  };

  const claim = async () => {
    setBusy(true); setError('');
    try {
      const r = await miningApi.claim(telegramId);
      onClaimed(r.new_balance);
      await load();
    } catch (e: any) {
      setError(e?.detail || 'Claim failed.');
    } finally { setBusy(false); }
  };

  if (loading) {
    return <div className="p2e-card mining-card"><div className="p2e-loading">Loading mining…</div></div>;
  }

  const breakdown = status?.potential?.breakdown;
  const potentialRate = status?.potential?.hourly_rate;

  const renderRateBreakdown = () => {
    if (!breakdown) return null;
    const nextHold = [1000, 10000, 50000, 200000].find(t => t > breakdown.holdings_tier) ?? null;
    return (
      <div className="rate-breakdown">
        <div className="rate-row">
          <span className="sh-label">Base rate</span><b className="tnum">{breakdown.base}/h</b>
        </div>
        <div className="rate-row">
          <span className="sh-label">Referrals · {breakdown.qualified_referrals} qualified</span>
          <b className={breakdown.referral_pct > 0 ? 'rate-up tnum' : 'tnum'}>
            +{breakdown.referral_pct}%
          </b>
        </div>
        <div className="rate-row">
          <span className="sh-label">Holdings tier</span>
          <b className={breakdown.holdings_mult > 1 ? 'rate-up tnum' : 'tnum'}>
            ×{breakdown.holdings_mult.toFixed(2).replace(/\.?0+$/, '')}
          </b>
        </div>
        <div className="rate-row">
          <span>Task boost</span>
          <b className={`tnum ${breakdown.task_boost_pct > 0 ? 'rate-up' : ''}`.trim()}>
            +{breakdown.task_boost_pct}%
          </b>
        </div>
        {breakdown.og_active && (
          <div className="rate-row"><span>OG Pass</span><b className="rate-up tnum">×2</b></div>
        )}
        {breakdown.verified && (
          <div className="rate-row"><span>Verified profile</span><b className="rate-up tnum">+10%</b></div>
        )}
        <div className="rate-cta">
          {breakdown.qualified_referrals < 20
            ? <>Invite friends or hold more CSM to mine faster</>
            : nextHold
              ? <>Hold {nextHold.toLocaleString('en-GB')} CSM for the next tier</>
              : <>Max mining power reached</>}
        </div>
      </div>
    );
  };

  const renderHeroRing = (secondsLeft: number) => {
    const total = 21600;
    const progress = Math.min(1, Math.max(0, (total - secondsLeft) / total));
    const R = 84;
    const C = 2 * Math.PI * R;
    return (
      <div className="mining-hero">
        <div className="mining-ring-wrap">
          <svg viewBox="0 0 196 196">
            <defs>
              <linearGradient id="shGoldGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#ffe9a3" />
                <stop offset="55%" stopColor="#f5c518" />
                <stop offset="100%" stopColor="#c98f06" />
              </linearGradient>
            </defs>
            <circle cx="98" cy="98" r={R} className="mining-ring-track" />
            <circle
              cx="98" cy="98" r={R}
              className="mining-ring-fill"
              strokeDasharray={C}
              strokeDashoffset={C * (1 - progress)}
            />
          </svg>
          <div className="mining-ring-center">
            <div className="mining-ring-timer tnum">{fmtCountdown(secondsLeft)}</div>
            <div className="mining-ring-label">Mining</div>
          </div>
        </div>
        <div className="mining-rate tnum">
          ≈ {status?.accrued_estimate ?? 0} CSM · <b>{status?.hourly_rate ?? potentialRate ?? 0}/h</b>
        </div>
      </div>
    );
  };

  return (
    <div className="p2e-card mining-card p2e-card-glass">
      <div className="p2e-card-head">
        <Pickaxe size={16} strokeWidth={1.8} />
        <span className="sh-label">Mining session</span>
        {status?.state === 'active' && (
          <Badge variant="gold" className="tnum" style={{ marginLeft: 'auto' }}>
            {status.hourly_rate ?? 0}/h
          </Badge>
        )}
      </div>

      {status?.state === 'active' && renderHeroRing(status.seconds_left ?? 0)}

      {status?.state === 'claimable' && (
        <>
          <div className="mining-ready tnum">+{status.accrued ?? 0} CSM ready</div>
          <Button className="w-full" size="lg" onClick={claim} disabled={busy}>
            {busy ? 'Claiming…' : 'Claim rewards'}
          </Button>
        </>
      )}

      {(status?.state === 'none' || !status) && (
        <>
          <div className="mining-sub">Press start and your ship mines for 6 hours — come back when the timer ends to claim and restart.</div>
          {potentialRate !== undefined && (
            <div className="mining-rate tnum" style={{ marginBottom: 8 }}>
              Your rate: <b>{potentialRate}/h</b> · ≈ <b>{potentialRate * 6} CSM</b> per cycle
            </div>
          )}
          <Button className="w-full" size="lg" onClick={startMining} disabled={busy}>
            {busy ? 'Starting…' : 'Start mining'}
          </Button>
        </>
      )}

      {(status?.state === 'active' || status?.state === 'none' || !status) && renderRateBreakdown()}

      {error && <div className="p2e-error">{error}</div>}
    </div>
  );
};
