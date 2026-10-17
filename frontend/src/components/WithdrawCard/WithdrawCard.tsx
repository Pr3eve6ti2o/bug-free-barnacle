import { FC, useCallback, useEffect, useState } from 'react';
import { ArrowUpFromLine } from 'lucide-react';
import { withdrawApi, WithdrawalRecord } from '@/services/api';
import { Button } from '@/components/ui/button';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  balance: number;
  onRequested: (newBalance: number) => void;
}

export const WithdrawCard: FC<Props> = ({ telegramId, balance, onRequested }) => {
  const [amount, setAmount] = useState('');
  const [address, setAddress] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<WithdrawalRecord[]>([]);

  const loadHistory = useCallback(async () => {
    try { setHistory(await withdrawApi.getHistory(telegramId)); } catch { /* ignore */ }
  }, [telegramId]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const submit = async () => {
    const amt = parseInt(amount, 10);
    if (!amt || amt <= 0) { setError('Enter an amount.'); return; }
    if (!address.trim()) { setError('Enter your TON wallet address.'); return; }
    setBusy(true); setError('');
    try {
      const r = await withdrawApi.request(telegramId, amt, address.trim());
      setAmount(''); setAddress('');
      onRequested(r.new_balance);
      await loadHistory();
    } catch (e: any) {
      setError(e?.detail || 'Request failed.');
    } finally { setBusy(false); }
  };

  return (
    <div className="p2e-card">
      <div className="p2e-card-head">
        <ArrowUpFromLine size={16} strokeWidth={1.8} />
        <span className="sh-label">Withdraw CSM</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <input
          className="p2e-input"
          inputMode="numeric"
          placeholder="Amount (min 1,000 CSM)"
          value={amount}
          onChange={e => setAmount(e.target.value.replace(/[^0-9]/g, ''))}
        />
        <input
          className="p2e-input"
          placeholder="TON address (EQ…)"
          value={address}
          onChange={e => setAddress(e.target.value.trim())}
          autoCapitalize="off"
          spellCheck={false}
          style={{ fontSize: 14 }}
        />
        <Button className="w-full" size="lg" onClick={submit} disabled={busy}>
          {busy ? 'Sending…' : 'Request withdrawal'}
        </Button>
      </div>
      {error && <div className="p2e-error">{error}</div>}
      <div className="p2e-note">Demo build — requests are recorded and settled manually. Balance: {balance < 0 ? '…' : balance.toLocaleString()} CSM</div>

      {history.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="sh-label" style={{ marginBottom: 6 }}>History</div>
          {history.map(h => (
            <div key={h.id} className="p2e-row">
              <div className="p2e-row-main">
                <div className="p2e-row-name tnum">{h.amount.toLocaleString()} CSM</div>
                <div className="p2e-row-sub tnum" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {h.address.slice(0, 10)}…{h.address.slice(-6)}
                </div>
              </div>
              <span className={`p2e-pill ${h.status === 'pending' ? 'p2e-pill-gold' : h.status === 'approved' ? 'p2e-pill-green' : ''}`}>
                {h.status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
