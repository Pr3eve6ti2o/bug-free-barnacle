import { FC, useCallback, useEffect, useState } from 'react';
import { Trophy, Crown } from 'lucide-react';
import { ratingApi, LeaderEntry } from '@/services/api';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
}

export const Leaderboard: FC<Props> = ({ telegramId }) => {
  const [leaders, setLeaders] = useState<LeaderEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await ratingApi.getGlobal(50);
      setLeaders(r.leaders);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p2e-card"><div className="p2e-loading">Loading leaderboard…</div></div>;

  const myId = Number(telegramId);
  return (
    <div className="p2e-card">
      <div className="p2e-card-head">
        <Trophy size={16} strokeWidth={1.8} />
        <span className="sh-label">Global leaderboard</span>
      </div>
      {leaders.length === 0 && <div className="p2e-note">No miners yet.</div>}
      {leaders.map(l => (
        <div key={l.telegram_id} className={`p2e-row ${l.telegram_id === myId ? 'me' : ''}`}>
          <div className="p2e-rank tnum">{l.rank}</div>
          <div className="p2e-row-main">
            <div className="p2e-row-name">
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.username || 'Miner'}</span>
              {l.og_badge && <Crown size={13} strokeWidth={2} color="var(--sh-accent)" />}
            </div>
            <div className="p2e-row-sub">Level {l.level}</div>
          </div>
          <div className="p2e-row-value tnum">{l.balance.toLocaleString()}</div>
        </div>
      ))}
    </div>
  );
};
