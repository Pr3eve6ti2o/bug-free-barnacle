import { FC, useEffect, useState } from 'react';
import { ScrollText } from 'lucide-react';
import { ModalWindow } from '@/components/ModalWindow/ModalWindow';
import { consentApi } from '@/services/api';
import { Button } from '@/components/ui/button';
import { TERMS_VERSION, TERMS_SUMMARY, TERMS_SECTIONS } from '@/data/terms';
import '@/components/p2e.css';

interface Props {
  telegramId: number | string;
  onAccepted: () => void;
}

export const TermsReader: FC = () => (
  <div className="terms-reader">
    {TERMS_SECTIONS.map(s => (
      <section key={s.title}>
        <h3 className="terms-section-title">{s.title}</h3>
        {s.body.map((p, i) => <p key={i} className="terms-section-body">{p}</p>)}
      </section>
    ))}
  </div>
);

/** Non-dismissible first-open consent gate. Renders locked screen until accepted. */
export const TermsGate: FC<Props> = ({ telegramId, onAccepted }) => {
  const [state, setState] = useState<'checking' | 'needed' | 'locked' | 'done'>('checking');
  const [showReader, setShowReader] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    consentApi.getConsent(telegramId)
      .then(r => setState(r.accepted_version >= TERMS_VERSION ? 'done' : 'needed'))
      .catch(() => setState('needed'));
  }, [telegramId]);

  useEffect(() => {
    if (state === 'done') onAccepted();
  }, [state, onAccepted]);

  const accept = async () => {
    setBusy(true);
    try {
      await consentApi.accept(telegramId, TERMS_VERSION);
      setState('done');
    } finally { setBusy(false); }
  };

  if (state === 'checking' || state === 'done') return null;

  if (state === 'locked') {
    return (
      <div className="terms-locked">
        <ScrollText size={40} strokeWidth={1.4} color="var(--sh-accent)" />
        <h2 style={{ color: 'var(--sh-text)', margin: 0 }}>Terms not accepted</h2>
        <p>You need to accept the Terms &amp; Conditions to play Space Hunter.</p>
        <Button style={{ maxWidth: 300 }} onClick={() => setState('needed')}>
          Read terms
        </Button>
      </div>
    );
  }

  return (
    <>
      <ModalWindow isOpen title="Terms & Conditions" onClose={() => {}} dismissible={false}>
        <ul className="terms-summary">
          {TERMS_SUMMARY.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
        <Button variant="ghost" className="w-full" style={{ marginBottom: 10 }} onClick={() => setShowReader(true)}>
          Read the full terms
        </Button>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="outline" className="flex-1" onClick={() => setState('locked')}>
            Decline
          </Button>
          <Button className="flex-1" onClick={accept} disabled={busy}>
            {busy ? 'Saving…' : 'I agree'}
          </Button>
        </div>
      </ModalWindow>
      <ModalWindow isOpen={showReader} title="Terms & Conditions" onClose={() => setShowReader(false)}>
        <TermsReader />
      </ModalWindow>
    </>
  );
};
