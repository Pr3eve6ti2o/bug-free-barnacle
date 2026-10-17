import { FC, useEffect, useState } from 'react';
import { Users, BadgeCheck, Check, Coins, UserPlus, Gauge, Gift } from 'lucide-react';
import { ReferralStats, userApi, walletApi } from '@/services/api';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  stats: ReferralStats | null;
}

/**
 * Crew earnings panel (ATF-style referral core):
 * banded Tier-1 yield share, 4% Tier-2, qualification + milestone bonuses,
 * plus the verified-profile checklist (+10% earnings).
 */
export const ReferralPanel: FC<Props> = ({ telegramId, stats }) => {
  const [verified, setVerified] = useState<{ username: boolean; wallet: boolean } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [user, wallet] = await Promise.all([
          userApi.getUser(telegramId) as Promise<any>,
          walletApi.getWalletStatus(Number(telegramId)).catch(() => ({ is_connected: false })),
        ]);
        setVerified({
          username: Boolean(user?.username && String(user.username).trim()),
          wallet: Boolean((wallet as any)?.is_connected),
        });
      } catch { /* ignore */ }
    })();
  }, [telegramId]);

  const t1Rate = stats?.tier1_rate_pct ?? 12;
  const t2Rate = stats?.tier2_rate_pct ?? 4;

  return (
    <div className="p2e-card">
      <div className="p2e-card-head">
        <Coins size={16} strokeWidth={1.8} />
        <span className="sh-label">Crew earnings</span>
        <span className="tnum" style={{ marginLeft: 'auto', color: 'var(--sh-gold)', fontWeight: 700, fontSize: 17 }}>
          +{(stats?.earnings_total ?? 0).toLocaleString()} CSM
        </span>
      </div>

      <div className="p2e-row">
        <div className="p2e-row-main">
          <div className="p2e-row-name">Direct crew <span className="p2e-pill">{t1Rate}% of their mining</span></div>
          <div className="p2e-row-sub">Yield share from friends you invited</div>
        </div>
        <div className="p2e-row-value tnum">+{(stats?.earnings_tier1 ?? 0).toLocaleString()}</div>
      </div>
      <div className="p2e-row">
        <div className="p2e-row-main">
          <div className="p2e-row-name">Extended crew <span className="p2e-pill">{t2Rate}%</span></div>
          <div className="p2e-row-sub">From friends of your friends</div>
        </div>
        <div className="p2e-row-value tnum">+{(stats?.earnings_tier2 ?? 0).toLocaleString()}</div>
      </div>

      <div className="p2e-card-head" style={{ marginTop: 18 }}>
        <Users size={16} strokeWidth={1.8} />
        <span className="sh-label">How crew mining works</span>
      </div>
      <div className="p2e-check done">
        <span className="p2e-check-icon"><UserPlus size={13} strokeWidth={2.2} /></span>
        <span><b>+1,000 CSM</b> for every friend who starts mining</span>
      </div>
      <div className="p2e-check done">
        <span className="p2e-check-icon"><Gauge size={13} strokeWidth={2.2} /></span>
        <span><b>+5% mining rate</b> per qualified crew member (up to +100%)</span>
      </div>
      <div className="p2e-check done">
        <span className="p2e-check-icon"><Gift size={13} strokeWidth={2.2} /></span>
        <span>Your friend gets a <b>+500 CSM</b> welcome bonus on their first claim</span>
      </div>

      {stats?.milestones.map(m => {
        const pct = Math.min(100, (stats.qualified_invites / m.invites) * 100);
        return (
          <div key={m.invites} className="p2e-milestone" style={{ marginTop: 10 }}>
            <div className="p2e-milestone-row">
              <span>{m.invites} qualified crew</span>
              <span className="tnum">
                {m.claimed ? 'Claimed ✓' : `+${m.reward.toLocaleString()} CSM`}
              </span>
            </div>
            <div className="p2e-bar"><div className="p2e-bar-fill" style={{ width: `${pct}%` }} /></div>
          </div>
        );
      })}

      <div className="p2e-card-head" style={{ marginTop: 18 }}>
        <BadgeCheck size={16} strokeWidth={1.8} />
        <span className="sh-label">Verified profile · +10% earnings</span>
      </div>
      {verified ? (
        <>
          <div className={`p2e-check ${verified.username ? 'done' : ''}`}>
            <span className="p2e-check-icon">{verified.username && <Check size={14} strokeWidth={2.5} />}</span>
            Telegram username set
          </div>
          <div className={`p2e-check ${verified.wallet ? 'done' : ''}`}>
            <span className="p2e-check-icon">{verified.wallet && <Check size={14} strokeWidth={2.5} />}</span>
            TON wallet connected
          </div>
          {verified.username && verified.wallet && (
            <div style={{ marginTop: 8 }}><span className="p2e-pill p2e-pill-green">+10% ACTIVE</span></div>
          )}
        </>
      ) : (
        <div className="p2e-loading">Checking…</div>
      )}
    </div>
  );
};
