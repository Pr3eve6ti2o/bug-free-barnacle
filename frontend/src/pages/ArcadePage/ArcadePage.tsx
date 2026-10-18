import { FC, useEffect, useMemo, useRef, useState } from 'react';
import { Coins, Dices, Gift, MousePointerClick, Sparkles } from 'lucide-react';
import { Page } from '@/components/Page.tsx';
import { Button } from '@/components/ui/button';
import {
    arcadeApi, buttonApi,
    type ArcadeState, type ButtonStateResponse,
} from '@/services/api';
import './ArcadePage.css';
import '@/components/p2e.css';
import { useTelegramUserId } from '@/hooks/useTelegramUser';

const SEG_COLORS = ['#15161f', '#3d2f05', '#15161f', '#3d2f05', '#15161f', '#57430a', '#6e5603'];

function errText(e: any): string {
    return e?.detail || e?.message || 'Something went wrong';
}

export const ArcadePage: FC = () => {
    const userId = useTelegramUserId() as number;

    const [arcade, setArcade] = useState<ArcadeState | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [rotation, setRotation] = useState(0);
    const [spinning, setSpinning] = useState(false);
    const [wheelMsg, setWheelMsg] = useState('');

    const [choice, setChoice] = useState<'heads' | 'tails'>('heads');
    const [stake, setStake] = useState(50);
    const [flipping, setFlipping] = useState(false);
    const [coinFace, setCoinFace] = useState<'heads' | 'tails'>('heads');
    const [flipMsg, setFlipMsg] = useState('');

    const [btn, setBtn] = useState<ButtonStateResponse | null>(null);
    const [pressing, setPressing] = useState(false);
    const [btnMsg, setBtnMsg] = useState('');
    const msgTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const loadAll = async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const [a, b] = await Promise.all([arcadeApi.getState(userId), buttonApi.getState(userId)]);
            setArcade(a);
            setBtn(b);
        } catch (e) {
            setArcade(null);
            setBtn(null);
            setLoadError(errText(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadAll(); }, []);

    const segments = arcade?.wheel.segments ?? [0, 10, 25, 50, 100, 250, 1000];
    const segAngle = 360 / segments.length;
    const wheelBg = useMemo(() => {
        const stops = segments.map((_, i) =>
            `${SEG_COLORS[i % SEG_COLORS.length]} ${(i * segAngle).toFixed(2)}deg ${((i + 1) * segAngle).toFixed(2)}deg`);
        return `conic-gradient(from -${(segAngle / 2).toFixed(2)}deg, ${stops.join(', ')})`;
    }, [segments, segAngle]);

    const spin = async () => {
        if (spinning || !arcade) return;
        setSpinning(true);
        setWheelMsg('');
        try {
            const res = await arcadeApi.spin(userId);
            const jitter = (Math.random() - 0.5) * segAngle * 0.55;
            const target = -(res.segment_index * segAngle) + jitter;
            setRotation(prev => {
                const base = prev - (prev % 360) + 360 * 6;
                let next = base + target;
                if (next <= prev + 360 * 4) next += 360;
                return next;
            });
            setTimeout(() => {
                setArcade(res);
                setSpinning(false);
                setWheelMsg(res.payout > 0
                    ? `+${res.payout.toLocaleString()} CSM${res.segment_index === segments.length - 1 ? ' — JACKPOT!' : ''}`
                    : 'No win this time');
            }, 4300);
        } catch (e) {
            setSpinning(false);
            setWheelMsg(errText(e));
        }
    };

    const flip = async () => {
        if (flipping || !arcade) return;
        setFlipping(true);
        setFlipMsg('');
        try {
            const res = await arcadeApi.flip(userId, choice, stake);
            setCoinFace(res.result);
            setTimeout(() => {
                setFlipping(false);
                setArcade(prev => prev ? { ...prev, balance: res.balance } : prev);
                setFlipMsg(res.won
                    ? `${res.result === 'heads' ? 'Heads' : 'Tails'} — you won +${res.payout.toLocaleString()} CSM`
                    : `${res.result === 'heads' ? 'Heads' : 'Tails'} — you lost ${stake.toLocaleString()} CSM`);
            }, 950);
        } catch (e) {
            setFlipping(false);
            setFlipMsg(errText(e));
        }
    };

    const flashBtnMsg = (text: string) => {
        setBtnMsg(text);
        if (msgTimer.current) clearTimeout(msgTimer.current);
        msgTimer.current = setTimeout(() => setBtnMsg(''), 2600);
    };

    const floatPlusOne = (host: HTMLElement | null) => {
        if (!host) return;
        const rect = host.getBoundingClientRect();
        const el = document.createElement('span');
        el.textContent = '+1';
        el.setAttribute('aria-hidden', 'true');
        const s = el.style;
        s.position = 'fixed';
        s.left = `${rect.left + rect.width / 2}px`;
        s.top = `${rect.top - 4}px`;
        s.transform = 'translate(-50%, 0)';
        s.fontWeight = '850';
        s.fontSize = '18px';
        s.lineHeight = '1';
        s.color = 'var(--sh-gold)';
        s.textShadow = '0 0 14px rgba(245, 197, 24, 0.6)';
        s.pointerEvents = 'none';
        s.userSelect = 'none';
        s.zIndex = '80';
        document.body.appendChild(el);
        const drop = () => el.remove();
        const anim = el.animate?.(
            [
                { opacity: 0, transform: 'translate(-50%, 6px) scale(0.85)' },
                { opacity: 1, transform: 'translate(-50%, -14px) scale(1.06)', offset: 0.22 },
                { opacity: 0, transform: 'translate(-50%, -52px) scale(1)' },
            ],
            { duration: 720, easing: 'cubic-bezier(0.22, 0.8, 0.26, 1)' },
        );
        if (anim) anim.onfinish = drop;
        else setTimeout(drop, 760);
    };

    const press = async (ev?: { currentTarget: EventTarget | null }) => {
        if (pressing) return;
        const before = btn;
        floatPlusOne((ev?.currentTarget as HTMLElement | null) ?? null);
        setPressing(true);
        if (before) {
            setBtn({
                ...before,
                total_presses: (before.total_presses ?? 0) + 1,
                my_presses: (before.my_presses ?? 0) + 1,
                presses_to_next: Math.max(0, (before.presses_to_next ?? 1) - 1),
            });
        }
        try {
            const res = await buttonApi.press(userId);
            setBtn(res);
            if (res.can_claim_chest) flashBtnMsg('Milestone reached — claim your chest below!');
        } catch (e: any) {
            if (before) setBtn(before);
            const detail = String(e?.detail ?? e?.message ?? '');
            if (/too fast/i.test(detail) || e?.status === 429) {
                flashBtnMsg('Too fast — the reactor needs a breath');
            } else {
                flashBtnMsg(detail || errText(e));
            }
        } finally {
            setPressing(false);
        }
    };

    const claimChest = async () => {
        try {
            const res = await buttonApi.claim(userId);
            setBtn(res);
            if (res.balance !== undefined) {
                setArcade(prev => prev ? { ...prev, balance: res.balance! } : prev);
            }
            flashBtnMsg(`Chest claimed: +${(res.claimed ?? 100).toLocaleString()} CSM`);
        } catch (e) {
            flashBtnMsg(errText(e));
        }
    };

    const balance = arcade?.balance ?? 0;
    const freeLeft = arcade?.wheel.free_spins_left ?? 0;
    const freeLeftLoaded = typeof arcade?.wheel.free_spins_left === 'number';
    const paidSpinPrice = arcade?.wheel.paid_spin_cost ?? 0;
    const spinLabel = !freeLeftLoaded
        ? 'Loading…'
        : freeLeft > 0
            ? `${freeLeft} free spin${freeLeft === 1 ? '' : 's'} left`
            : `${paidSpinPrice.toLocaleString()} CSM per spin · Free spins reset at midnight`;
    const progress = btn ? Math.round((btn.presses_into_milestone / btn.milestone_size) * 100) : 0;

    return (
        <Page back={true}>
            {loadError && (
                <div className="p2e-card" style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <Gift size={18} style={{ color: 'var(--sh-gold)' }} />
                        <span style={{ fontWeight: 600, fontSize: 15 }}>Couldn't load the arcade</span>
                    </div>
                    <div style={{ fontSize: 13, opacity: 0.62, lineHeight: 1.45, marginBottom: 10 }}>{loadError}</div>
                    <Button className="w-full" disabled={loading} onClick={() => { void loadAll(); }}>
                        {loading ? 'Retrying…' : 'Retry'}
                    </Button>
                </div>
            )}
            {loading && !arcade && !loadError && (
                <div className="p2e-card" style={{ marginBottom: 12, opacity: 0.62 }}>Loading the arcade…</div>
            )}
            <div style={{ padding: '14px 14px 110px', maxWidth: 430, margin: '0 auto' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Arcade</h1>
                    <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px',
                        borderRadius: 999, background: 'rgba(245,197,24,0.1)',
                        border: '1px solid rgba(245,197,24,0.3)', fontWeight: 750, fontSize: 14,
                    }}>
                        <Coins size={15} style={{ color: 'var(--sh-gold)' }} />
                        <span className="tnum">{balance.toLocaleString()} CSM</span>
                    </span>
                </div>
                <p style={{ opacity: 0.65, fontSize: 13, margin: '2px 0 14px' }}>
                    Mini-games and the community reactor — every prize is paid in CSM.
                </p>

                {/* ------- Spin wheel (from StoryVibe's casino) ------- */}
                <div className="p2e-card" style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <Sparkles size={18} style={{ color: 'var(--sh-gold)' }} />
                        <span style={{ fontWeight: 750, fontSize: 16 }}>Fortune Wheel</span>
                        <span style={{ marginLeft: 'auto', fontSize: 12.5, opacity: 0.75 }}>
                            {loadError ? 'Unavailable' : spinLabel}
                        </span>
                    </div>
                    <div className="wheel-wrap">
                        <div className="wheel-pointer" />
                        <div className="wheel-disc" style={{ background: wheelBg, transform: `rotate(${rotation}deg)` }}>
                            {segments.map((v, i) => (
                                <span key={i} className="wheel-label" style={{
                                    transform: `translate(-50%, -50%) rotate(${i * segAngle}deg) translateY(-92px)`,
                                }}>{v === 0 ? '0' : v.toLocaleString()}</span>
                            ))}
                        </div>
                        <button
                            type="button"
                            className="wheel-hub"
                            disabled={spinning || !arcade}
                            onClick={spin}
                            style={{ border: 0, padding: 0, appearance: 'none' }}
                        >SPIN</button>
                    </div>
                    <div style={{ minHeight: 22, textAlign: 'center', fontWeight: 700, fontSize: 14.5, color: 'var(--sh-gold)', margin: '6px 0 8px' }}>
                        {wheelMsg}
                    </div>
                    <Button className="w-full" disabled={spinning || !arcade} onClick={spin}>
                        {!arcade
                            ? (loading ? 'Loading…' : 'Unavailable')
                            : spinning
                                ? 'Spinning…'
                                : freeLeft > 0
                                    ? 'Spin — free'
                                    : `Spin — ${arcade.wheel.paid_spin_cost ?? 75} CSM`}
                    </Button>
                </div>

                {/* ------- Coin flip (from StoryVibe's casino) ------- */}
                <div className="p2e-card" style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                        <Dices size={18} style={{ color: 'var(--sh-gold)' }} />
                        <span style={{ fontWeight: 600, fontSize: 17, letterSpacing: '-0.01em' }}>Coin Flip</span>
                        <span style={{ marginLeft: 'auto', fontSize: 13, color: 'rgba(255,255,255,.62)', fontVariantNumeric: 'tabular-nums' }}>Pays 1.9×</span>
                    </div>
                    <div className={`coin-disc ${flipping ? 'flipping' : ''}`}>
                        {coinFace === 'heads' ? 'HEADS' : 'TAILS'}
                    </div>
                    <div style={{ display: 'flex', gap: 8, margin: '10px 0 8px' }}>
                        {(['heads', 'tails'] as const).map(side => (
                            <button key={side} className={`stake-chip ${choice === side ? 'active' : ''}`}
                                onClick={() => setChoice(side)}>
                                {side === 'heads' ? 'Heads' : 'Tails'}
                            </button>
                        ))}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                        {[10, 50, 100, 250].map(v => (
                            <button key={v} className={`stake-chip ${stake === v ? 'active' : ''}`}
                                disabled={v > (balance ?? Infinity)}
                                onClick={() => setStake(Math.min(v, Math.max(10, balance ?? v)))}>
                                {v}
                            </button>
                        ))}
                    </div>
                    <div style={{ minHeight: 20, textAlign: 'center', fontWeight: 650, fontSize: 13.5, marginBottom: 6 }}>
                        {flipMsg}
                    </div>
                    {(balance ?? Infinity) < 10 && (
                        <div style={{ textAlign: 'center', fontSize: 12.5, fontWeight: 600, color: '#f5c518', marginBottom: 6 }}>
                            You need at least 10 CSM
                        </div>
                    )}
                    <Button className="w-full" disabled={flipping || !arcade || (balance ?? Infinity) < 10} onClick={flip}>
                        {flipping ? 'Flipping…' : `Flip for ${stake} CSM`}
                    </Button>
                </div>

                {/* ------- The Button (from ButtonMania) ------- */}
                <div className="p2e-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <MousePointerClick size={18} style={{ color: 'var(--sh-gold)' }} />
                        <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>The Button</span>
                        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'rgba(255,255,255,.62)' }}>Community reactor</span>
                    </div>
                    <p style={{ fontSize: 13, lineHeight: 1.45, color: 'rgba(255,255,255,.62)', margin: '6px 0 2px' }}>
                        One button, every hunter. Each {btn?.milestone_size.toLocaleString() ?? '1,000'} presses charge a
                        milestone chest of {btn?.chest_amount ?? 100} CSM for everyone who pressed at least {btn?.claim_min_presses ?? 10} times.
                    </p>
                    <div className="tnum" style={{ textAlign: 'center', fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 10 }}>
                        {(btn?.total_presses ?? 0).toLocaleString()}
                    </div>
                    <div style={{ textAlign: 'center', fontSize: 12, opacity: 0.65 }}>total presses · yours: {(btn?.my_presses ?? 0).toLocaleString()}</div>
                    <button className="reactor-btn" disabled={pressing} onClick={press}>PRESS</button>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, opacity: 0.8, marginTop: 6 }}>
                        <span>Milestone {btn?.milestone ?? 0}</span>
                        <span className="tnum">
                            {Math.max(0, btn?.presses_to_next ?? 1000).toLocaleString()} presses to the next chest
                        </span>
                    </div>
                    <div className="arcade-progress"><div style={{ width: `${progress}%` }} /></div>
                    <div
                        role="status"
                        aria-live="polite"
                        style={{ minHeight: 20, textAlign: 'center', fontWeight: 650, fontSize: 13.5, margin: '8px 0 2px', color: 'var(--sh-gold)' }}
                    >
                        {btnMsg}
                    </div>
                    {btn?.can_claim_chest && (
                        <Button className="w-full" onClick={claimChest}>
                            <Gift size={16} style={{ marginRight: 6 }} />
                            Claim milestone chest — {btn.chest_amount} CSM
                        </Button>
                    )}
                </div>
            </div>
        </Page>
    );
};
