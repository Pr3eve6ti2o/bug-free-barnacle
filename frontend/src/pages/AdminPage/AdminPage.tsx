import { FC, useEffect, useState } from 'react';
import {
    BarChart3, Coins, ListTodo, Megaphone, Search, Settings2, ShieldAlert, SlidersHorizontal,
} from 'lucide-react';
import { Page } from '@/components/Page.tsx';
import { Button } from '@/components/ui/button';
import {
    adminApi,
    type AdminAction, type AdminComms, type AdminEconomy, type AdminSettings,
    type AdminStats, type AdminTaskFull, type AdminUser, type AdminWithdrawal,
} from '@/services/api';
import '@/components/p2e.css';

type Section = 'overview' | 'players' | 'withdrawals' | 'tasks' | 'economy' | 'comms' | 'controls';

const MENU: { id: Section; label: string; icon: any }[] = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'players', label: 'Players', icon: Search },
    { id: 'withdrawals', label: 'Payouts', icon: Coins },
    { id: 'tasks', label: 'Tasks', icon: ListTodo },
    { id: 'economy', label: 'Economy', icon: SlidersHorizontal },
    { id: 'comms', label: 'Comms', icon: Megaphone },
    { id: 'controls', label: 'Controls', icon: Settings2 },
];

const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', borderRadius: 12, boxSizing: 'border-box',
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
    color: 'inherit', fontSize: 14, outline: 'none',
};
const labelStyle: React.CSSProperties = { fontSize: 12, opacity: 0.6, marginBottom: 4, display: 'block' };

function Toggle({ on, onClick, label, hint }: { on: boolean; onClick: () => void; label: string; hint: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{label}</div>
                <div style={{ fontSize: 12.5, opacity: 0.65 }}>{hint}</div>
            </div>
            <button onClick={onClick} aria-label={label} style={{
                width: 52, height: 30, borderRadius: 999, border: '1px solid rgba(245,197,24,0.4)',
                background: on ? 'var(--sh-gold)' : 'rgba(255,255,255,0.12)', cursor: 'pointer',
                position: 'relative', flexShrink: 0, transition: 'background 0.2s',
            }}>
                <span style={{
                    position: 'absolute', top: 3, left: on ? 25 : 3, width: 22, height: 22, borderRadius: '50%',
                    background: on ? '#221a02' : '#fff', transition: 'left 0.2s',
                }} />
            </button>
        </div>
    );
}

const CONDITION_TYPES = [
    'mining_sessions', 'mining_claims', 'bot_started', 'referrals', 'balance',
    'level', 'wallet_connected', 'taps', 'energy_spent', 'daily_balance', 'passive_income',
];

export const AdminPage: FC = () => {
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 99281932;
    const [gate, setGate] = useState<'loading' | 'admin' | 'denied'>('loading');
    const [section, setSection] = useState<Section>('overview');
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [actions, setActions] = useState<AdminAction[]>([]);
    const [settings, setSettings] = useState<AdminSettings | null>(null);
    const [notice, setNotice] = useState('');
    const [error, setError] = useState('');

    // players
    const [q, setQ] = useState('');
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [selected, setSelected] = useState<AdminUser | null>(null);
    const [adjustAmt, setAdjustAmt] = useState('100');
    const [levelVal, setLevelVal] = useState('1');
    const [boostVal, setBoostVal] = useState('0');
    const [grantVal, setGrantVal] = useState('500');
    const [referrerVal, setReferrerVal] = useState('');
    const [banReason, setBanReason] = useState('');

    // withdrawals
    const [withdrawals, setWithdrawals] = useState<AdminWithdrawal[]>([]);
    const [wCounts, setWCounts] = useState<Record<string, number>>({});
    const [wFilter, setWFilter] = useState('');
    const [txById, setTxById] = useState<Record<number, string>>({});

    // tasks
    const [tasks, setTasks] = useState<AdminTaskFull[]>([]);
    const [newTask, setNewTask] = useState({
        title: '', description: '', type: 'permanent', reward: 100, reward_type: 'token',
        multiplier_pct: 0, link_url: '', condition_type: 'mining_claims', condition_value: 1,
    });

    // economy + comms
    const [economy, setEconomy] = useState<AdminEconomy | null>(null);
    const [comms, setComms] = useState<AdminComms | null>(null);
    const [bannerText, setBannerText] = useState('');
    const [broadcastText, setBroadcastText] = useState('');

    const flash = (t: string) => { setNotice(t); setError(''); setTimeout(() => setNotice(''), 4000); };
    const fail = (e: any) => setError(e?.response?.data?.detail || e?.message || 'Something went wrong');

    const loadOverview = async () => {
        const [s, a] = await Promise.all([adminApi.getStats(userId), adminApi.getActions(userId)]);
        setStats(s); setActions(a.actions);
    };
    const loadSettings = async () => {
        const s = await adminApi.getSettings(userId);
        setSettings(s); setBannerText(s.announcement || '');
    };
    const loadUsers = async (query = '') => {
        const r = await adminApi.listUsers(userId, query);
        setUsers(r.users);
    };
    const loadWithdrawals = async (status = wFilter) => {
        const r = await adminApi.listWithdrawals(userId, status);
        setWithdrawals(r.withdrawals); setWCounts(r.counts);
    };
    const loadTasks = async () => setTasks((await adminApi.listAllTasks(userId)).tasks);
    const loadEconomy = async () => setEconomy(await adminApi.getEconomy(userId));
    const loadComms = async () => setComms(await adminApi.getComms(userId));

    useEffect(() => {
        adminApi.whoami(userId).then(r => {
            if (r.is_admin) {
                setGate('admin');
                loadOverview(); loadSettings(); loadUsers(); loadWithdrawals(''); loadTasks(); loadEconomy(); loadComms();
            } else setGate('denied');
        }).catch(() => setGate('denied'));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const pickUser = async (tid: number) => {
        try {
            const u = await adminApi.getUser(userId, tid);
            setSelected(u);
            setLevelVal(String(u.level)); setBoostVal(String(u.admin_boost_pct));
            setReferrerVal(u.referrer_telegram_id ? String(u.referrer_telegram_id) : '');
        } catch { fail(new Error('User not found')); }
    };
    const refreshSelected = async () => { if (selected) await pickUser(selected.telegram_id); };

    const applyAdjust = async () => {
        if (!selected) return;
        const amt = parseInt(adjustAmt, 10);
        if (isNaN(amt) || amt === 0) return;
        try {
            const r = await adminApi.adjust(userId, selected.telegram_id, amt);
            flash(`Balance adjusted ${amt > 0 ? '+' : ''}${amt} → ${r.balance.toLocaleString()} CSM`);
            refreshSelected(); loadOverview();
        } catch (e) { fail(e); }
    };
    const applyLevel = async () => {
        if (!selected) return;
        try {
            await adminApi.setLevel(userId, selected.telegram_id, parseInt(levelVal, 10));
            flash(`Level set to ${levelVal}`); refreshSelected();
        } catch (e) { fail(e); }
    };
    const applyBoost = async () => {
        if (!selected) return;
        try {
            await adminApi.grantBoost(userId, selected.telegram_id, parseFloat(boostVal));
            flash(`Admin mining boost set to ${boostVal}%`); refreshSelected();
        } catch (e) { fail(e); }
    };
    const applyGrant = async () => {
        if (!selected) return;
        try {
            const r = await adminApi.grantReferralBonus(userId, selected.telegram_id, parseInt(grantVal, 10));
            flash(`Referral bonus granted → balance ${r.balance.toLocaleString()} CSM`); refreshSelected(); loadOverview();
        } catch (e) { fail(e); }
    };
    const applyReferrer = async () => {
        if (!selected) return;
        try {
            const v = referrerVal.trim();
            await adminApi.setReferrer(userId, selected.telegram_id, v ? parseInt(v, 10) : null);
            flash(v ? `Referrer set to ${v}` : 'Referrer cleared'); refreshSelected();
        } catch (e) { fail(e); }
    };
    const applyBan = async (ban: boolean) => {
        if (!selected) return;
        try {
            if (ban) await adminApi.banUser(userId, selected.telegram_id, banReason);
            else await adminApi.unbanUser(userId, selected.telegram_id);
            flash(ban ? 'Player banned' : 'Player unbanned'); refreshSelected(); loadOverview(); loadUsers(q);
        } catch (e) { fail(e); }
    };

    const reviewW = async (w: AdminWithdrawal, action: 'approve' | 'reject') => {
        try {
            await adminApi.reviewWithdrawal(userId, w.id, action);
            flash(action === 'approve' ? `Withdrawal #${w.id} approved` : `Withdrawal #${w.id} rejected — ${w.amount.toLocaleString()} CSM refunded`);
            loadWithdrawals(); loadOverview();
        } catch (e) { fail(e); }
    };
    const payW = async (w: AdminWithdrawal) => {
        const tx = (txById[w.id] || '').trim();
        if (tx.length < 8) { setError('Paste the payout transaction hash or link first'); return; }
        try {
            const r = await adminApi.markPaid(userId, w.id, tx);
            flash(`Withdrawal #${w.id} marked paid${r.proof_posted ? ' — proof posted to the channel' : ''}`);
            loadWithdrawals(); loadOverview();
        } catch (e) { fail(e); }
    };

    const createTask = async () => {
        if (!newTask.title.trim()) { setError('Task needs a title'); return; }
        try {
            await adminApi.createTask(userId, {
                title: newTask.title, description: newTask.description, type: newTask.type,
                reward: Number(newTask.reward), reward_type: newTask.reward_type,
                multiplier_pct: Number(newTask.multiplier_pct), link_url: newTask.link_url || null,
                condition_type: newTask.condition_type, condition_value: Number(newTask.condition_value),
            });
            flash('Task created'); setNewTask({ ...newTask, title: '', description: '' }); loadTasks();
        } catch (e) { fail(e); }
    };
    const toggleTask = async (t: AdminTaskFull) => {
        try { await adminApi.patchTask(userId, t.id, { is_active: !t.is_active }); loadTasks(); } catch (e) { fail(e); }
    };
    const removeTask = async (t: AdminTaskFull) => {
        try { await adminApi.deleteTask(userId, t.id); flash('Task deleted'); loadTasks(); } catch (e) { fail(e); }
    };

    const saveEconomy = async () => {
        if (!economy) return;
        try {
            const r = await adminApi.setEconomy(userId, economy);
            setEconomy(r); flash('Economy settings saved — new sessions and purchases use them now');
        } catch (e) { fail(e); }
    };
    const saveComms = async (patch: Partial<AdminComms>) => {
        try { setComms(await adminApi.setComms(userId, patch)); flash('Comms settings saved'); } catch (e) { fail(e); }
    };
    const sendBroadcast = async () => {
        if (!broadcastText.trim()) return;
        try {
            const r = await adminApi.broadcast(userId, broadcastText.trim());
            flash(`Broadcast sent to ${r.sent} of ${r.audience} players (${r.failed} failed)`);
            setBroadcastText(''); loadOverview();
        } catch (e) { fail(e); }
    };
    const saveBanner = async (text: string) => {
        try {
            const s = await adminApi.updateSettings(userId, { announcement: text });
            setSettings(s); flash(text ? 'Announcement is live on the Mining screen' : 'Announcement cleared');
        } catch (e) { fail(e); }
    };
    const toggleSetting = async (key: 'referrals_enabled' | 'arcade_enabled', value: boolean) => {
        try {
            const s = await adminApi.updateSettings(userId, { [key]: value });
            setSettings(s); flash(`${key === 'referrals_enabled' ? 'Referral payouts' : 'Arcade'} ${value ? 'enabled' : 'disabled'}`);
        } catch (e) { fail(e); }
    };
    const forceDrop = async () => {
        try {
            const r = await adminApi.forceStartDrop(userId);
            flash(`Drop forced live until ${new Date(r.ends_at).toLocaleTimeString('en-GB')}`); loadOverview();
        } catch (e) { fail(e); }
    };
    const downloadExport = async () => {
        try {
            const blob = await adminApi.exportActions(userId);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'spacehunter-export.xlsx'; a.click();
            URL.revokeObjectURL(url);
        } catch (e) { fail(e); }
    };

    if (gate === 'loading') {
        return <Page back={true}><div style={{ padding: 24, opacity: 0.7 }}>Checking admin access…</div></Page>;
    }
    if (gate === 'denied') {
        return (
            <Page back={true}>
                <div style={{ padding: '24px 14px', maxWidth: 430, margin: '0 auto' }}>
                    <div className="p2e-card" style={{ textAlign: 'center', padding: 28 }}>
                        <ShieldAlert size={30} style={{ color: 'var(--sh-gold)', marginBottom: 8 }} />
                        <div style={{ fontWeight: 750, fontSize: 17 }}>Admins only</div>
                        <p style={{ opacity: 0.65, fontSize: 13.5 }}>
                            This Telegram account isn't on the admin allowlist, so the panel stays closed.
                        </p>
                    </div>
                </div>
            </Page>
        );
    }

    const tiles: [string, string][] = stats ? [
        ['Users', stats.users.toLocaleString()],
        ['Balances held', `${stats.balances_total.toLocaleString()} CSM`],
        ['Lifetime earned', `${stats.lifetime_earned_total.toLocaleString()} CSM`],
        ['Referral payouts', `${stats.referral_payouts.toLocaleString()} CSM`],
        ['Pending payouts', stats.pending_withdrawals.toLocaleString()],
        ['Paid out', `${stats.paid_out_total.toLocaleString()} CSM`],
        ['Banned', stats.banned_users.toLocaleString()],
        ['Arcade plays', stats.arcade_plays.toLocaleString()],
        ['Button presses', stats.button_presses.toLocaleString()],
        ['Drop claims', stats.drop_claims.toLocaleString()],
    ] : [];

    const statusChip = (s: string) => ({
        padding: '3px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, letterSpacing: '0.01em',
        background: s === 'paid' ? 'rgba(74,222,128,0.15)' : s === 'approved' ? 'rgba(96,165,250,0.15)'
            : s === 'rejected' ? 'rgba(248,113,113,0.15)' : 'rgba(245,197,24,0.15)',
        color: s === 'paid' ? '#4ade80' : s === 'approved' ? '#60a5fa' : s === 'rejected' ? '#f87171' : 'var(--sh-gold)',
    } as React.CSSProperties);

    return (
        <Page back={true}>
            <div style={{ padding: '16px 16px 110px', maxWidth: 430, margin: '0 auto' }}>
                <h1 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 2px' }}>Admin Panel</h1>
                <p style={{ opacity: 0.65, fontSize: 13, margin: '0 0 14px' }}>
                    Every action is signature-verified against the admin allowlist and written to the audit log.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 14 }}>
                    {MENU.map(m => (
                        <button key={m.id} onClick={() => setSection(m.id)} style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
                            padding: '11px 4px', borderRadius: 14, cursor: 'pointer', color: 'inherit',
                            background: section === m.id ? 'rgba(245,197,24,0.14)' : 'rgba(255,255,255,0.05)',
                            border: `1px solid ${section === m.id ? 'rgba(245,197,24,0.55)' : 'rgba(255,255,255,0.1)'}`,
                            fontSize: 11.5, fontWeight: 700,
                        }}>
                            <m.icon size={17} style={{ color: 'var(--sh-gold)' }} />
                            {m.label}
                            {m.id === 'withdrawals' && (wCounts.pending ?? 0) > 0 && (
                                <span style={{ background: '#f87171', color: '#fff', borderRadius: 999, padding: '0 6px', fontSize: 10.5 }}>
                                    {wCounts.pending}
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {notice && (
                    <div style={{
                        padding: '10px 12px', borderRadius: 12, marginBottom: 12, fontSize: 13.5, fontWeight: 650,
                        background: 'rgba(74,222,128,0.12)', border: '1px solid rgba(74,222,128,0.4)',
                    }}>{notice}</div>
                )}
                {error && (
                    <div style={{
                        padding: '10px 12px', borderRadius: 12, marginBottom: 12, fontSize: 13.5, fontWeight: 650,
                        background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.4)',
                    }}>{error}</div>
                )}

                {section === 'overview' && (
                    <>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                            {tiles.map(([k, v]) => (
                                <div key={k} className="p2e-card" style={{ padding: '12px 14px' }}>
                                    <div style={{ fontSize: 11.5, opacity: 0.6, textTransform: 'uppercase', letterSpacing: 0.5 }}>{k}</div>
                                    <div className="tnum" style={{ fontSize: 17, fontWeight: 800, marginTop: 2 }}>{v}</div>
                                </div>
                            ))}
                        </div>
                        <div className="p2e-card">
                            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                                <div style={{ fontWeight: 750, flex: 1 }}>Recent admin actions</div>
                                <Button variant="outline" onClick={downloadExport}>Export Excel</Button>
                            </div>
                            {actions.length === 0 && <div style={{ opacity: 0.6, fontSize: 13 }}>No actions yet.</div>}
                            {actions.map((a, i) => (
                                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '5px 0', borderTop: i ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
                                    <span style={{ fontWeight: 700 }}>{a.action}</span>
                                    <span style={{ opacity: 0.7, flex: 1 }}>{a.target} {a.detail}</span>
                                    <span style={{ opacity: 0.45 }}>{a.at ? new Date(a.at).toLocaleTimeString('en-GB') : ''}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {section === 'players' && (
                    <div className="p2e-card">
                        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                            <input style={inputStyle} placeholder="Search username or Telegram ID" value={q}
                                onChange={e => setQ(e.target.value)} />
                            <Button onClick={() => loadUsers(q)}>Search</Button>
                        </div>
                        {users.map(u => (
                            <button key={u.telegram_id} onClick={() => pickUser(u.telegram_id)} style={{
                                display: 'flex', width: '100%', gap: 8, alignItems: 'center', textAlign: 'left',
                                padding: '9px 6px', background: 'transparent', border: 'none', cursor: 'pointer',
                                color: 'inherit', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: 13.5,
                            }}>
                                <span style={{ fontWeight: 700, flex: 1 }}>
                                    @{u.username || '—'} <span style={{ opacity: 0.45, fontWeight: 400 }}>{u.telegram_id}</span>
                                    {u.banned && <span style={{ color: '#f87171', marginLeft: 6, fontSize: 11.5 }}>BANNED</span>}
                                </span>
                                <span style={{ opacity: 0.55, fontSize: 12 }}>Lv {u.level}</span>
                                <span className="tnum">{u.balance.toLocaleString()} CSM</span>
                            </button>
                        ))}
                        {selected && (
                            <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: 'rgba(245,197,24,0.06)', border: '1px solid rgba(245,197,24,0.25)' }}>
                                <div style={{ fontWeight: 800 }}>
                                    @{selected.username || '—'} · {selected.telegram_id}
                                    {selected.banned && <span style={{ color: '#f87171' }}> · BANNED{selected.ban_reason ? `: ${selected.ban_reason}` : ''}</span>}
                                </div>
                                <div style={{ fontSize: 13, opacity: 0.8, margin: '4px 0 10px', lineHeight: 1.55 }}>
                                    Balance {selected.balance.toLocaleString()} · Level {selected.level} · Mined {selected.lifetime_mined.toLocaleString()} ·
                                    Lifetime {selected.lifetime_earned.toLocaleString()} · Referral earnings {selected.referral_earnings.toLocaleString()} ·
                                    Invites {selected.invites} · Referrer {selected.referrer_telegram_id ?? '—'} ·
                                    Task boost +{selected.task_boost_pct}% · Admin boost +{selected.admin_boost_pct}% ·
                                    Wallet {selected.wallet ? `${selected.wallet.slice(0, 6)}…${selected.wallet.slice(-4)}` : 'not connected'}
                                </div>

                                <span style={labelStyle}>Adjust balance (CSM, ±1,000,000)</span>
                                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                                    <input style={inputStyle} type="number" value={adjustAmt} onChange={e => setAdjustAmt(e.target.value)} />
                                    <Button onClick={applyAdjust}>Adjust</Button>
                                </div>

                                <span style={labelStyle}>Set level (1–100)</span>
                                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                                    <input style={inputStyle} type="number" value={levelVal} onChange={e => setLevelVal(e.target.value)} />
                                    <Button onClick={applyLevel}>Set level</Button>
                                </div>

                                <span style={labelStyle}>Admin mining boost % (−90 to +500, applies to new sessions)</span>
                                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                                    <input style={inputStyle} type="number" value={boostVal} onChange={e => setBoostVal(e.target.value)} />
                                    <Button onClick={applyBoost}>Set boost</Button>
                                </div>

                                <span style={labelStyle}>Grant referral bonus (CSM, written to the ledger as an admin grant)</span>
                                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                                    <input style={inputStyle} type="number" value={grantVal} onChange={e => setGrantVal(e.target.value)} />
                                    <Button onClick={applyGrant}>Grant</Button>
                                </div>

                                <span style={labelStyle}>Referrer (Telegram ID, blank clears)</span>
                                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                                    <input style={inputStyle} type="number" value={referrerVal} onChange={e => setReferrerVal(e.target.value)} placeholder="e.g. 123456789" />
                                    <Button onClick={applyReferrer}>Set referrer</Button>
                                </div>

                                <span style={labelStyle}>{selected.banned ? 'This player is banned — their game access is refused.' : 'Ban this player (game access is refused immediately)'}</span>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    {!selected.banned && (
                                        <input style={inputStyle} value={banReason} onChange={e => setBanReason(e.target.value)} placeholder="Reason (optional)" />
                                    )}
                                    {selected.banned
                                        ? <Button style={{ flex: 1 }} onClick={() => applyBan(false)}>Unban player</Button>
                                        : <Button style={{ flex: 1, background: '#b91c1c' }} onClick={() => applyBan(true)}>Ban player</Button>}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {section === 'withdrawals' && (
                    <div className="p2e-card">
                        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                            {['', 'pending', 'approved', 'paid', 'rejected'].map(s => (
                                <button key={s || 'all'} onClick={() => { setWFilter(s); loadWithdrawals(s); }} style={{
                                    padding: '6px 12px', borderRadius: 999, cursor: 'pointer', fontSize: 12.5, fontWeight: 700,
                                    color: 'inherit', border: `1px solid ${wFilter === s ? 'rgba(245,197,24,0.55)' : 'rgba(255,255,255,0.12)'}`,
                                    background: wFilter === s ? 'rgba(245,197,24,0.14)' : 'rgba(255,255,255,0.05)',
                                }}>
                                    {s === '' ? 'All' : s} {s && wCounts[s] ? `(${wCounts[s]})` : ''}
                                </button>
                            ))}
                        </div>
                        {withdrawals.length === 0 && <div style={{ opacity: 0.6, fontSize: 13 }}>No withdrawal requests here.</div>}
                        {withdrawals.map(w => (
                            <div key={w.id} style={{ padding: '10px 0', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13.5 }}>
                                    <span style={{ fontWeight: 800 }}>#{w.id}</span>
                                    <span style={{ flex: 1 }}>@{w.username || '—'} <span style={{ opacity: 0.45 }}>{w.telegram_id}</span></span>
                                    <span className="tnum" style={{ fontWeight: 800 }}>{w.amount.toLocaleString()} CSM</span>
                                    <span style={statusChip(w.status)}>{w.status}</span>
                                </div>
                                <div style={{ fontSize: 12, opacity: 0.6, margin: '3px 0 8px', wordBreak: 'break-all' }}>
                                    {w.address} · {w.created_at ? new Date(w.created_at).toLocaleString('en-GB') : ''}
                                    {w.tx_hash ? ` · tx ${w.tx_hash.slice(0, 18)}…` : ''}
                                </div>
                                {w.status === 'pending' && (
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <Button style={{ flex: 1 }} onClick={() => reviewW(w, 'approve')}>Approve</Button>
                                        <Button style={{ flex: 1, background: '#b91c1c' }} onClick={() => reviewW(w, 'reject')}>Reject + refund</Button>
                                    </div>
                                )}
                                {w.status === 'approved' && (
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <input style={inputStyle} placeholder="Payout tx hash or tonviewer link"
                                            value={txById[w.id] || ''} onChange={e => setTxById({ ...txById, [w.id]: e.target.value })} />
                                        <Button onClick={() => payW(w)}>Mark paid</Button>
                                    </div>
                                )}
                            </div>
                        ))}
                        <div style={{ fontSize: 12, opacity: 0.55, marginTop: 8 }}>
                            Flow: approve → pay the wallet yourself → paste the transaction hash → Mark paid.
                            Marking paid posts the real payout proof to your channel (Comms tab) when configured.
                            Rejecting refunds the escrowed CSM to the player.
                        </div>
                    </div>
                )}

                {section === 'tasks' && (
                    <>
                        <div className="p2e-card" style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 750, marginBottom: 10 }}>Create a task</div>
                            <span style={labelStyle}>Title</span>
                            <input style={{ ...inputStyle, marginBottom: 8 }} value={newTask.title}
                                onChange={e => setNewTask({ ...newTask, title: e.target.value })} placeholder="e.g. Mine 10 times" />
                            <span style={labelStyle}>Description</span>
                            <input style={{ ...inputStyle, marginBottom: 8 }} value={newTask.description}
                                onChange={e => setNewTask({ ...newTask, description: e.target.value })} placeholder="Optional" />
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                                <div>
                                    <span style={labelStyle}>Condition</span>
                                    <select style={inputStyle} value={newTask.condition_type}
                                        onChange={e => setNewTask({ ...newTask, condition_type: e.target.value })}>
                                        {CONDITION_TYPES.map(c => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <span style={labelStyle}>Target value</span>
                                    <input style={inputStyle} type="number" value={newTask.condition_value}
                                        onChange={e => setNewTask({ ...newTask, condition_value: Number(e.target.value) })} />
                                </div>
                                <div>
                                    <span style={labelStyle}>Reward type</span>
                                    <select style={inputStyle} value={newTask.reward_type}
                                        onChange={e => setNewTask({ ...newTask, reward_type: e.target.value })}>
                                        <option value="token">Token (CSM)</option>
                                        <option value="multiplier">Mining power %</option>
                                    </select>
                                </div>
                                <div>
                                    <span style={labelStyle}>{newTask.reward_type === 'token' ? 'Reward (CSM)' : 'Boost %'}</span>
                                    <input style={inputStyle} type="number"
                                        value={newTask.reward_type === 'token' ? newTask.reward : newTask.multiplier_pct}
                                        onChange={e => setNewTask(newTask.reward_type === 'token'
                                            ? { ...newTask, reward: Number(e.target.value) }
                                            : { ...newTask, multiplier_pct: Number(e.target.value) })} />
                                </div>
                                <div>
                                    <span style={labelStyle}>Kind</span>
                                    <select style={inputStyle} value={newTask.type}
                                        onChange={e => setNewTask({ ...newTask, type: e.target.value })}>
                                        <option value="permanent">Permanent</option>
                                        <option value="daily">Daily</option>
                                    </select>
                                </div>
                                <div>
                                    <span style={labelStyle}>Link (optional)</span>
                                    <input style={inputStyle} value={newTask.link_url}
                                        onChange={e => setNewTask({ ...newTask, link_url: e.target.value })} placeholder="https://t.me/…" />
                                </div>
                            </div>
                            <Button className="w-full" onClick={createTask}>Create task</Button>
                        </div>
                        <div className="p2e-card">
                            <div style={{ fontWeight: 750, marginBottom: 6 }}>All tasks</div>
                            {tasks.map(t => (
                                <div key={t.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: 13 }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 700, opacity: t.is_active ? 1 : 0.45 }}>{t.title}</div>
                                        <div style={{ opacity: 0.55, fontSize: 12 }}>
                                            {t.condition_type} ≥ {t.condition_value} · {t.reward_type === 'token' ? `${t.reward} CSM` : `+${t.multiplier_pct}% power`} · {t.type}
                                        </div>
                                    </div>
                                    <button onClick={() => toggleTask(t)} style={{
                                        padding: '5px 10px', borderRadius: 999, cursor: 'pointer', fontSize: 11.5, fontWeight: 700,
                                        color: t.is_active ? '#4ade80' : 'inherit',
                                        background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
                                    }}>{t.is_active ? 'Live' : 'Hidden'}</button>
                                    <button onClick={() => removeTask(t)} style={{
                                        padding: '5px 10px', borderRadius: 999, cursor: 'pointer', fontSize: 11.5, fontWeight: 700,
                                        color: '#f87171', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)',
                                    }}>Delete</button>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {section === 'economy' && economy && (
                    <div className="p2e-card">
                        <div style={{ fontWeight: 750, marginBottom: 4 }}>Economy settings</div>
                        <p style={{ fontSize: 12.5, opacity: 0.65, margin: '0 0 12px' }}>
                            Applied live: the base rate and session length affect new mining sessions,
                            the OG price affects new purchases, the welcome reward affects new claims.
                            In-flight sessions keep the terms they started with.
                        </p>
                        <span style={labelStyle}>Base mining rate (CSM per hour)</span>
                        <input style={{ ...inputStyle, marginBottom: 10 }} type="number" value={economy.base_rate}
                            onChange={e => setEconomy({ ...economy, base_rate: Number(e.target.value) })} />
                        <span style={labelStyle}>Mining session length (hours)</span>
                        <input style={{ ...inputStyle, marginBottom: 10 }} type="number" value={economy.session_hours}
                            onChange={e => setEconomy({ ...economy, session_hours: Number(e.target.value) })} />
                        <span style={labelStyle}>OG Pass price (CSM)</span>
                        <input style={{ ...inputStyle, marginBottom: 10 }} type="number" value={economy.og_cost}
                            onChange={e => setEconomy({ ...economy, og_cost: Number(e.target.value) })} />
                        <span style={labelStyle}>Welcome bonus (CSM)</span>
                        <input style={{ ...inputStyle, marginBottom: 12 }} type="number" value={economy.welcome_reward}
                            onChange={e => setEconomy({ ...economy, welcome_reward: Number(e.target.value) })} />
                        <Button className="w-full" onClick={saveEconomy}>Save economy</Button>
                    </div>
                )}

                {section === 'comms' && (
                    <>
                        <div className="p2e-card" style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 750, marginBottom: 4 }}>Announcement banner</div>
                            <p style={{ fontSize: 12.5, opacity: 0.65, margin: '0 0 10px' }}>
                                Shown as a banner on every player's Mining screen.
                            </p>
                            <textarea style={{ ...inputStyle, minHeight: 74, resize: 'vertical' }} maxLength={280}
                                value={bannerText} onChange={e => setBannerText(e.target.value)}
                                placeholder="e.g. Double mining weekend — crew payouts boosted!" />
                            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                                <Button style={{ flex: 1 }} onClick={() => saveBanner(bannerText)}>Publish</Button>
                                <Button style={{ flex: 1 }} variant="outline" onClick={() => { setBannerText(''); saveBanner(''); }}>Clear</Button>
                            </div>
                        </div>

                        <div className="p2e-card" style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 750, marginBottom: 4 }}>Broadcast via the bot</div>
                            <p style={{ fontSize: 12.5, opacity: 0.65, margin: '0 0 10px' }}>
                                Sends a Telegram message to everyone who has pressed /start in the bot
                                {comms ? ` — currently ${comms.bot_audience} player${comms.bot_audience === 1 ? '' : 's'}` : ''}.
                            </p>
                            <textarea style={{ ...inputStyle, minHeight: 74, resize: 'vertical' }} maxLength={1000}
                                value={broadcastText} onChange={e => setBroadcastText(e.target.value)}
                                placeholder="Your message to all players…" />
                            <Button className="w-full" style={{ marginTop: 10 }} onClick={sendBroadcast}>Send broadcast</Button>
                        </div>

                        {comms && (
                            <div className="p2e-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                <div>
                                    <div style={{ fontWeight: 750, marginBottom: 4 }}>Payout proofs channel</div>
                                    <p style={{ fontSize: 12.5, opacity: 0.65, margin: '0 0 8px' }}>
                                        Create a Telegram channel, add @FARMGradientbot as an admin, and paste its
                                        @username or ID here. Real payouts you mark paid are posted there automatically.
                                    </p>
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <input style={inputStyle} value={comms.proofs_channel_id}
                                            onChange={e => setComms({ ...comms, proofs_channel_id: e.target.value })}
                                            placeholder="@your_proofs_channel" />
                                        <Button onClick={() => saveComms({ proofs_channel_id: comms.proofs_channel_id })}>Save</Button>
                                    </div>
                                </div>
                                <Toggle on={comms.proofs_realtime} label="Real-time proof posts"
                                    hint="Post each payout to the channel the moment you mark it paid."
                                    onClick={() => saveComms({ proofs_realtime: !comms.proofs_realtime })} />
                                <Toggle on={comms.digest_enabled} label="Daily payout digest"
                                    hint="Once a day, post the day's real payout totals to the channel."
                                    onClick={() => saveComms({ digest_enabled: !comms.digest_enabled })} />
                                {comms.digest_enabled && (
                                    <div>
                                        <span style={labelStyle}>Digest hour (UTC, 0–23)</span>
                                        <div style={{ display: 'flex', gap: 8 }}>
                                            <input style={inputStyle} type="number" value={comms.digest_hour_utc}
                                                onChange={e => setComms({ ...comms, digest_hour_utc: Number(e.target.value) })} />
                                            <Button onClick={() => saveComms({ digest_hour_utc: comms.digest_hour_utc })}>Save</Button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {section === 'controls' && settings && (
                    <div className="p2e-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        <Toggle on={settings.referrals_enabled} label="Referral payouts"
                            hint="When off, mining pays no crew shares or referral bonuses."
                            onClick={() => toggleSetting('referrals_enabled', !settings.referrals_enabled)} />
                        <Toggle on={settings.arcade_enabled} label="Arcade"
                            hint="Switch the Fortune Wheel and Coin Flip on or off for everyone."
                            onClick={() => toggleSetting('arcade_enabled', !settings.arcade_enabled)} />
                        <div>
                            <div style={{ fontWeight: 700, fontSize: 15 }}>Force-start a drop</div>
                            <div style={{ fontSize: 12.5, opacity: 0.65, marginBottom: 8 }}>
                                Opens a 5,000 CSM drop immediately, live for 15 minutes.
                            </div>
                            <Button className="w-full" onClick={forceDrop}>Start drop now</Button>
                        </div>
                    </div>
                )}
            </div>
        </Page>
    );
};
