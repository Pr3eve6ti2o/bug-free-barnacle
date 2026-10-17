import { FC, useEffect, useState } from 'react';
import { Gift, Timer } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { dropsApi, type DropState } from '@/services/api';
import '@/components/p2e.css';

function fmtCountdown(ms: number): string {
    if (ms <= 0) return '00:00';
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const mm = String(m % 60).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Timed token drop (from Kennix88/Token-Giver): a limited CSM pool opens on a
 *  schedule; first come, first served, one claim per hunter per drop. */
export const DropEventCard: FC<{ userId: number; onClaimed?: (newBalance: number) => void }> = ({ userId, onClaimed }) => {
    const [drop, setDrop] = useState<DropState | null>(null);
    const [now, setNow] = useState(Date.now());
    const [claiming, setClaiming] = useState(false);
    const [msg, setMsg] = useState('');

    const load = async () => {
        try { setDrop(await dropsApi.getCurrent(userId)); } catch { /* keep last state */ }
    };

    useEffect(() => { load(); }, []);
    useEffect(() => {
        const t = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(t);
    }, []);
    // Refresh server state when a window boundary passes.
    useEffect(() => {
        if (!drop) return;
        const boundary = new Date(drop.live ? drop.ends_at : drop.next_starts_at).getTime();
        if (now > boundary + 500) load();
    }, [now, drop?.live, drop?.ends_at, drop?.next_starts_at]);

    if (!drop) return null;

    const target = new Date(drop.live ? drop.ends_at : drop.next_starts_at).getTime();
    const countdown = fmtCountdown(target - now);
    const poolPct = Math.max(0, Math.min(100, (drop.pool_remaining / drop.pool_total) * 100));

    const claim = async () => {
        if (claiming) return;
        setClaiming(true);
        setMsg('');
        try {
            const res = await dropsApi.claim(userId);
            setDrop(res);
            setMsg(`+${(res.claimed_amount ?? drop.per_claim).toLocaleString()} CSM claimed`);
            onClaimed?.(res.balance);
        } catch (e: any) {
            setMsg(e?.detail || 'Could not claim');
            load();
        } finally {
            setClaiming(false);
        }
    };

    return (
        <div className="p2e-card" style={{ width: '100%', maxWidth: 430, margin: '0 auto 14px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Gift size={18} style={{ color: 'var(--sh-gold)' }} />
                <span style={{ fontWeight: 750, fontSize: 16 }}>Timed Drop</span>
                <span style={{
                    marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5,
                    fontSize: 12.5, fontWeight: 700,
                    color: drop.live ? '#4ade80' : 'inherit', opacity: drop.live ? 1 : 0.75,
                }}>
                    <Timer size={14} />
                    {drop.live ? `Live — ends in ${countdown}` : `Next drop in ${countdown}`}
                </span>
            </div>
            <p style={{ fontSize: 12.5, opacity: 0.65, margin: '6px 0 0' }}>
                A {drop.pool_total.toLocaleString()} CSM pool opens every 30 minutes for 15 minutes.
                Each hunter can claim {drop.per_claim} CSM — first come, first served.
            </p>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, opacity: 0.8, marginTop: 10 }}>
                <span>Pool remaining</span>
                <span className="tnum">{drop.pool_remaining.toLocaleString()} / {drop.pool_total.toLocaleString()} CSM · {drop.claims} claims</span>
            </div>
            <div style={{ height: 10, borderRadius: 6, background: 'rgba(255,255,255,0.09)', overflow: 'hidden', marginTop: 6 }}>
                <div style={{
                    height: '100%', width: `${poolPct}%`, borderRadius: 6,
                    background: 'linear-gradient(90deg, #a87f0a, var(--sh-gold))', transition: 'width 0.4s ease',
                }} />
            </div>
            {msg && (
                <div style={{ textAlign: 'center', fontWeight: 700, fontSize: 13.5, color: 'var(--sh-gold)', marginTop: 10 }}>
                    {msg}
                </div>
            )}
            <Button className="w-full" style={{ marginTop: 10 }} disabled={!drop.claimable || claiming} onClick={claim}>
                {drop.claimed_by_me
                    ? 'Claimed — see you at the next drop'
                    : drop.live
                        ? (drop.pool_remaining < drop.per_claim ? 'Pool exhausted' : `Claim ${drop.per_claim} CSM`)
                        : 'Waiting for the drop to open'}
            </Button>
        </div>
    );
};
