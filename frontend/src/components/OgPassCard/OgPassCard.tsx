import { FC, useCallback, useEffect, useState } from 'react';
import { Crown, Check } from 'lucide-react';
import { ogPassApi, OgPassStatus } from '@/services/api';
import { Button } from '@/components/ui/button';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  balance: number;
  onPurchased: (newBalance: number) => void;
}

const BENEFITS = [
  '2× mining session rate',
  '+10 max energy (110)',
  'Gold OG badge on your profile',
];

export const OgPassCard: FC<Props> = ({ telegramId, balance, onPurchased }) => {
  const [status, setStatus] = useState<OgPassStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try { setStatus(await ogPassApi.getStatus(telegramId)); } catch { /* ignore */ }
  }, [telegramId]);

  useEffect(() => { load(); }, [load]);

  const buy = async () => {
    setBusy(true); setError('');
    try {
      const r = await ogPassApi.purchase(telegramId);
      onPurchased(r.new_balance);
      await load();
    } catch (e: any) {
      setError(e?.detail || 'Purchase failed.');
    } finally { setBusy(false); }
  };

  const daysLeft = status?.expires_at
    ? Math.max(0, Math.ceil((new Date(status.expires_at).getTime() - Date.now()) / 86400000))
    : 0;

  return (
    <div className="p2e-card">
      <div className="p2e-card-head">
        <Crown size={16} strokeWidth={1.8} />
        <span className="sh-label">OG Pass</span>
        {status?.active && <span className="p2e-pill p2e-pill-gold">ACTIVE</span>}
      </div>
      {BENEFITS.map(b => (
        <div key={b} className="p2e-check done" style={{ padding: '6px 0' }}>
          <span className="p2e-check-icon"><Check size={14} strokeWidth={2.5} /></span>
          <span>{b}</span>
        </div>
      ))}
      {status?.active ? (
        <div className="p2e-note" style={{ color: 'var(--sh-accent-text)', marginTop: 12 }}>
          {daysLeft} day{daysLeft === 1 ? '' : 's'} left · renew to extend from expiry
        </div>
      ) : (
        <>
          <Button
            className="w-full"
            size="lg"
            style={{ marginTop: 12 }}
            onClick={buy}
            disabled={busy || (status != null && balance < status.cost)}
          >
            {busy ? 'Processing…' : status ? `Buy · ${status.cost.toLocaleString()} CSM / ${status.days} days` : 'Loading…'}
          </Button>
          {error && <div className="p2e-error">{error}</div>}
          {status && balance < status.cost && !error && (
            <div className="p2e-note">You need {(status.cost - balance).toLocaleString()} more CSM</div>
          )}
        </>
      )}
    </div>
  );
};
