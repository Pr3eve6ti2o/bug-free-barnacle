import { FC, useState } from 'react';
import { Coins } from 'lucide-react';
import { ModalWindow } from '@/components/ModalWindow/ModalWindow';
import { welcomeApi } from '@/services/api';
import { Button } from '@/components/ui/button';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  onClaimed: (newBalance: number) => void;
  onSkip?: () => void;
}

export const WelcomeBonus: FC<Props> = ({ telegramId, onClaimed, onSkip }) => {
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);

  const claim = async () => {
    setBusy(true);
    setError(false);
    try {
      const r = await welcomeApi.claim(telegramId);
      onClaimed(r.new_balance);
      setDone(true);
      setOpen(false);
    } catch {
      // Claim failed — leave the modal open so the user can retry or skip.
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const skip = () => {
    setDone(true);
    setOpen(false);
    onSkip?.();
  };

  if (done) return null;
  return (
    <ModalWindow isOpen={open} title="Welcome aboard" onClose={() => setOpen(false)}>
      <div style={{ textAlign: 'center', padding: '8px 0 4px' }}>
        <Coins size={52} strokeWidth={1.2} color="var(--sh-accent)" />
        <p style={{ color: 'var(--sh-text)', fontSize: 17, fontWeight: 700, margin: '14px 0 6px' }}>
          Your journey begins
        </p>
        <p style={{ color: 'var(--sh-dim)', fontSize: 14, lineHeight: 1.6, margin: '0 0 18px' }}>
          Here are <strong style={{ color: 'var(--sh-accent-text)' }}>250 CSM</strong> to fuel
          your first flight. Tap the ship to mine more.
        </p>
        <Button className="w-full" size="lg" onClick={claim} disabled={busy}>
          {busy ? 'Claiming…' : 'Claim 250 CSM'}
        </Button>
        {error && (
          <p style={{ color: 'var(--sh-dim)', fontSize: 12, margin: '10px 0 0' }}>
            Could not claim right now — try again in a moment.
          </p>
        )}
        {onSkip && (
          <button
            type="button"
            onClick={skip}
            disabled={busy}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--sh-dim)',
              fontSize: 13,
              fontWeight: 600,
              width: '100%',
              padding: '10px 0 0',
              cursor: 'pointer',
            }}
          >
            Later
          </button>
        )}
      </div>
    </ModalWindow>
  );
};
