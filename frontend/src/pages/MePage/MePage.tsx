import { FC, useEffect, useState } from "react";
import { Check, Copy, Send, ShieldCheck, Users, Wallet, ArrowDownToLine, Pickaxe } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/Page.tsx";
import {
  adminApi, gameApi, miningApi, referralApi, ReferralStats, userApi,
  walletApi, withdrawApi, PayoutEvent, WithdrawalRecord,
} from '@/services/api';
import { Spinner } from '@/components/Spinner/Spinner.tsx';
import { ReferralPanel } from "@/components/ReferralPanel/ReferralPanel";
import { Leaderboard } from "@/components/Leaderboard/Leaderboard";
import "./MePage.css";
import "@/components/p2e.css";
import { useTelegramUserId } from '@/hooks/useTelegramUser';

interface Friend {
  id: number;
  username: string;
  telegram_id: number;
  game_state: {
    balance: number;
    level: number;
  }
}

const WITHDRAW_MIN = 1000;

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.max(1, Math.floor((Date.now() - then) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export const MePage: FC = () => {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [boardTab, setBoardTab] = useState<"friends" | "global">("friends");
  const [copied, setCopied] = useState(false);
  const [manualCopy, setManualCopy] = useState(false);
  const userId = useTelegramUserId() as number;
  const navigate = useNavigate();
  const [isAdmin, setIsAdmin] = useState(false);
  const [loadError, setLoadError] = useState(false);

  // Profile + economy snapshot
  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user as
    { username?: string; first_name?: string; last_name?: string } | undefined;
  const displayName = tgUser?.username || tgUser?.first_name || 'Pilot';
  const [balance, setBalance] = useState<number | null>(null);
  const [level, setLevel] = useState<number | null>(null);
  const [power, setPower] = useState<number | null>(null);

  // Withdrawal
  const [address, setAddress] = useState('');
  const [amount, setAmount] = useState('');
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const [withdrawMsg, setWithdrawMsg] = useState('');
  const [withdrawError, setWithdrawError] = useState('');
  const [history, setHistory] = useState<WithdrawalRecord[]>([]);
  const [payouts, setPayouts] = useState<PayoutEvent[]>([]);

  useEffect(() => {
    adminApi.whoami(userId).then(r => setIsAdmin(r.is_admin)).catch(() => setIsAdmin(false));
  }, []);
  const inviteLink = `https://t.me/FARMGradientbot?startapp=${userId}`;

  const load = async () => {
    try {
      setLoading(true);
      const [referrals, s] = await Promise.all([
        userApi.getUserReferrals(userId),
        referralApi.getStats(userId).catch(() => null),
      ]);
      setFriends(referrals);
      setStats(s);
      setLoadError(false);
    } catch (error) {
      console.error('Failed to load referrals:', error);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  const loadProfile = async () => {
    try {
      const [state, mining] = await Promise.all([
        gameApi.getGameState(userId),
        miningApi.getStatus(userId).catch(() => null),
      ]);
      setBalance(state.balance);
      setLevel(state.level);
      if (mining?.potential) setPower(mining.potential.hourly_rate);
    } catch { /* header falls back to placeholders */ }
    walletApi.getWalletStatus(userId)
      .then(w => { if (w.is_connected && w.address) setAddress(w.address); })
      .catch(() => { /* ignore */ });
    withdrawApi.getHistory(userId).then(setHistory).catch(() => { /* ignore */ });
    withdrawApi.getRecent().then(setPayouts).catch(() => { /* ignore */ });
  };

  useEffect(() => {
    void load();
    void loadProfile();
  }, [userId]);

  const submitWithdraw = async () => {
    const amt = parseInt(amount, 10);
    setWithdrawMsg('');
    setWithdrawError('');
    if (!amt || Number.isNaN(amt)) {
      setWithdrawError('Enter an amount.');
      return;
    }
    setWithdrawBusy(true);
    try {
      const r = await withdrawApi.request(userId, amt, address.trim());
      setBalance(r.new_balance);
      setWithdrawMsg(`Request #${r.id} received — ${r.amount.toLocaleString('en-GB')} CSM is being processed.`);
      setAmount('');
      withdrawApi.getHistory(userId).then(setHistory).catch(() => { /* ignore */ });
      withdrawApi.getRecent().then(setPayouts).catch(() => { /* ignore */ });
    } catch (e: any) {
      setWithdrawError(e?.detail || 'Withdrawal failed. Check the amount and address.');
    } finally {
      setWithdrawBusy(false);
    }
  };

  const copyInviteLink = async () => {
    const flashCopied = () => {
      setCopied(true);
      setManualCopy(false);
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success');
      window.setTimeout(() => setCopied(false), 1600);
    };

    const execCommandCopy = (text: string) => {
      try {
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.top = '-1000px';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        area.setSelectionRange(0, area.value.length);
        const ok = document.execCommand('copy');
        document.body.removeChild(area);
        return ok;
      } catch (err) {
        console.error("execCommand copy failed:", err);
        return false;
      }
    };

    try {
      await navigator.clipboard.writeText(inviteLink);
      flashCopied();
      return;
    } catch (err) {
      console.error("Failed to copy:", err);
    }

    if (execCommandCopy(inviteLink)) {
      flashCopied();
      return;
    }

    // Last resort — show the link so it can be copied by hand.
    setCopied(false);
    setManualCopy(true);
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error');
  };

  const inviteFriend = () => {
    const text = encodeURIComponent(`Join my crew in Space Hunter and grab a +500 CSM welcome bonus 🚀\n`);
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${text}`;
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('medium');

    const tg = window.Telegram?.WebApp;
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(shareUrl);
    } else if (tg?.openLink) {
      tg.openLink(shareUrl);
    } else {
      window.open(shareUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const getInitial = (name: string) => {
    return name && name.length > 0 ? name[0].toUpperCase() : '?';
  };

  const earnedByTid = new Map((stats?.friends ?? []).map(f => [f.telegram_id, f]));
  const sortedFriends = [...friends].sort((a, b) =>
    (earnedByTid.get(b.telegram_id)?.earned_for_you || 0) - (earnedByTid.get(a.telegram_id)?.earned_for_you || 0)
    || (b.game_state?.balance || 0) - (a.game_state?.balance || 0)
  );

  const emptyCrew = !loading && !loadError && !!stats && stats.total_invites === 0;

  return (
    <Page back={false}>
      <div className="me-page-container">
        {/* Profile */}
        <div className="p2e-card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="friend-avatar" style={{ width: 52, height: 52, flexShrink: 0 }}>
            <div className="friend-avatar-placeholder" style={{ fontSize: 20 }}>
              {getInitial(displayName)}
            </div>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 17, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {displayName}
            </div>
            <div style={{ fontSize: 13, opacity: 0.62 }}>
              ID {userId} · Level {level ?? '—'}
            </div>
          </div>
          <span className="p2e-pill p2e-pill-green">Pilot</span>
        </div>

        {/* Stats */}
        <div className="me-stats-grid">
          <div className="me-stat">
            <span className="me-stat-label">Balance</span>
            <span className="me-stat-value tnum">{balance === null ? '—' : balance.toLocaleString('en-GB')}</span>
            <span className="me-stat-unit">CSM</span>
          </div>
          <div className="me-stat">
            <span className="me-stat-label"><Pickaxe size={11} /> Mining power</span>
            <span className="me-stat-value tnum">{power === null ? '—' : power.toLocaleString('en-GB')}</span>
            <span className="me-stat-unit">CSM/h</span>
          </div>
          <div className="me-stat">
            <span className="me-stat-label"><Users size={11} /> Crew</span>
            <span className="me-stat-value tnum">{stats ? stats.total_invites : '—'}</span>
            <span className="me-stat-unit">friends</span>
          </div>
          <div className="me-stat">
            <span className="me-stat-label">Crew earned</span>
            <span className="me-stat-value tnum">{stats ? `+${stats.earnings_total.toLocaleString('en-GB')}` : '—'}</span>
            <span className="me-stat-unit">CSM</span>
          </div>
        </div>

        {/* Referral */}
        <div className="p2e-card">
          <div className="sh-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Users size={14} strokeWidth={1.8} /> Your invite link
          </div>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.62)', margin: '8px 0 14px', lineHeight: 1.5 }}>
            +1,000 CSM when a friend starts mining, plus a share of everything
            your crew mines — up to 12% from direct friends.
          </div>
          <div className="invite-buttons">
            <button className="invite-button primary" onClick={inviteFriend}>
              <Send className="w-5 h-5" />
              Invite friends
            </button>
            <button className="invite-button" onClick={copyInviteLink}>
              {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
              {copied ? 'Copied' : 'Copy link'}
            </button>
          </div>
          {manualCopy && (
            <input
              readOnly
              value={inviteLink}
              autoFocus
              onFocus={(e) => e.currentTarget.select()}
              aria-label="Invite link"
              style={{
                width: '100%', marginTop: 12, padding: '12px 14px', borderRadius: 12,
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                color: 'inherit', fontSize: 13, fontFamily: 'inherit',
              }}
            />
          )}
        </div>

        {!emptyCrew && (
        <div className="friends-section">
          <div className="p2e-segmented">
            <button className={boardTab === "friends" ? "active" : ""} onClick={() => setBoardTab("friends")}>
              Friends
            </button>
            <button className={boardTab === "global" ? "active" : ""} onClick={() => setBoardTab("global")}>
              Global
            </button>
          </div>
          {boardTab === "global" ? (
            <Leaderboard telegramId={userId} />
          ) : (
          <>
          <div className="sh-label friends-title">Playing friends</div>
          {loading ? (
            <div className="spinner-container">
              <Spinner />
            </div>
          ) : loadError ? (
            <div className="no-friends">
              <p>Couldn’t load your crew. Check your connection and try again.</p>
              <button className="invite-button" onClick={load} style={{ marginTop: 12 }}>Retry</button>
            </div>
          ) : (
            <div className="friends-list-container">
              {sortedFriends.length === 0 ? (
                <div className="no-friends">
                  <p>No crew yet. Invite friends — every miner you bring makes you earn faster.</p>
                </div>
              ) : (
                <div className="friends-list">
                  {sortedFriends.map((friend, index) => {
                    const earned = earnedByTid.get(friend.telegram_id);
                    return (
                    <div key={friend.id} className="friend-item">
                      <span className="friend-position tnum">{index + 1}</span>
                      <div className="friend-avatar">
                        <div className="friend-avatar-placeholder">
                          {getInitial(friend.username)}
                        </div>
                      </div>
                      <div className="friend-info">
                        <span className="friend-name">{friend.username}</span>
                        <span className="friend-coins tnum">
                          {(friend.game_state?.balance || 0).toLocaleString()} CSM
                          {earned && earned.earned_for_you > 0 && (
                            <span style={{ color: 'var(--sh-green, #4ade80)' }}> · +{earned.earned_for_you.toLocaleString()} for you</span>
                          )}
                        </span>
                      </div>
                      {earned?.qualified
                        ? <span className="p2e-pill p2e-pill-green">Mining</span>
                        : <span className="friend-level tnum">Lv {friend.game_state?.level || 1}</span>}
                    </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
          </>
          )}
        </div>
        )}
        <div style={{ height: 16 }} />
        <ReferralPanel telegramId={userId} stats={stats} />

        {/* Withdraw */}
        <div className="p2e-card" style={{ marginTop: 14 }}>
          <div className="sh-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Wallet size={14} strokeWidth={1.8} /> Withdraw CSM
          </div>
          <div style={{ fontSize: 13, opacity: 0.62, margin: '8px 0 12px', lineHeight: 1.5 }}>
            Minimum withdrawal is {WITHDRAW_MIN.toLocaleString('en-GB')} CSM to a TON wallet.
            Requests are reviewed and paid out in order.
          </div>
          <input
            className="p2e-input"
            placeholder="TON wallet address (EQ… / UQ…)"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            style={{ marginBottom: 8, height: 48, borderRadius: 12 }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="p2e-input"
              placeholder={`Amount (min ${WITHDRAW_MIN.toLocaleString('en-GB')})`}
              inputMode="numeric"
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^0-9]/g, ''))}
              style={{ flex: 1 }}
            />
            <button className="invite-button primary" onClick={submitWithdraw} disabled={withdrawBusy} style={{ flexShrink: 0 }}>
              <ArrowDownToLine className="w-5 h-5" />
              {withdrawBusy ? 'Sending…' : 'Withdraw'}
            </button>
          </div>
          {withdrawMsg && <div style={{ color: 'var(--sh-green, #4ade80)', fontSize: 13, marginTop: 9 }}>{withdrawMsg}</div>}
          {withdrawError && <div className="p2e-error" style={{ marginTop: 9 }}>{withdrawError}</div>}
          {history.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="sh-label" style={{ marginBottom: 6 }}>Your requests</div>
              {history.slice(0, 5).map(h => (
                <div key={h.id} className="me-feed-row">
                  <span className="tnum">{h.amount.toLocaleString('en-GB')} CSM</span>
                  <span className={`p2e-pill ${h.status === 'pending' ? '' : 'p2e-pill-green'}`}>{h.status}</span>
                  <span style={{ opacity: 0.6, fontSize: 12 }}>{timeAgo(h.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent payouts feed */}
        {payouts.length > 0 && (
          <div className="p2e-card" style={{ marginTop: 14 }}>
            <div className="sh-label" style={{ marginBottom: 8 }}>Recent payouts</div>
            {payouts.map((p, i) => (
              <div key={i} className="me-feed-row">
                <span style={{ fontWeight: 600, fontSize: 15, color: 'rgba(255,255,255,.92)' }}>{p.name}</span>
                <span style={{ color: 'rgba(255,255,255,.62)', fontSize: 13 }}>
                  {p.kind === 'withdrawal' ? 'withdrew' : 'earned from crew'}
                </span>
                <span className="tnum" style={{ color: 'var(--sh-gold)', fontWeight: 600, fontSize: 15 }}>
                  {p.amount.toLocaleString('en-GB')} CSM
                </span>
                <span style={{ color: 'rgba(255,255,255,.45)', fontSize: 11 }}>{timeAgo(p.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        {isAdmin && (
          <button
            onClick={() => navigate('/SpaceHunter/admin')}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, width: '100%',
              marginTop: 12, padding: '13px 14px', borderRadius: 16, cursor: 'pointer',
              background: 'rgba(245,197,24,0.07)', border: '1px solid rgba(245,197,24,0.25)',
              color: 'inherit', textAlign: 'left',
            }}
          >
            <ShieldCheck size={19} strokeWidth={1.8} style={{ color: 'var(--sh-gold)', flexShrink: 0 }} />
            <span style={{ flex: 1 }}>
              <span style={{ display: 'block', fontWeight: 650, fontSize: 14.5 }}>Admin Panel</span>
              <span style={{ display: 'block', fontSize: 12.5, opacity: 0.7 }}>Users, referral toggle, drops and announcements</span>
            </span>
          </button>
        )}
      </div>
    </Page>
  );
};
