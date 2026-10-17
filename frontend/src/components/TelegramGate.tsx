import { useCallback } from 'react';
import type { CSSProperties, MouseEvent, ReactNode } from 'react';
import { useTelegramUserId } from '../hooks/useTelegramUser';

const TELEGRAM_BOT_URL = 'https://t.me/FARMGradientbot';

type TelegramWindow = Window & {
  Telegram?: { WebApp?: { openTelegramLink?: (url: string) => void } };
};

const cardStyle: CSSProperties = {
  background: '#06070c',
  border: '1px solid rgba(245, 197, 24, 0.35)',
  borderRadius: 16,
  padding: '32px 24px',
  maxWidth: 420,
  margin: '0 auto',
  textAlign: 'center',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 16,
};

const buttonStyle: CSSProperties = {
  display: 'inline-block',
  padding: '12px 28px',
  borderRadius: 999,
  border: 'none',
  background: '#f5c518',
  color: '#06070c',
  fontWeight: 700,
  fontSize: 16,
  letterSpacing: 0.3,
  cursor: 'pointer',
  textDecoration: 'none',
  boxShadow: '0 6px 20px rgba(245, 197, 24, 0.25)',
};

export function TelegramGate() {
  const handleClick = useCallback((event: MouseEvent<HTMLAnchorElement>) => {
    const webApp = typeof window === 'undefined' ? undefined : (window as TelegramWindow).Telegram?.WebApp;
    if (!webApp?.openTelegramLink) return; // fall back to the anchor's default navigation
    event.preventDefault();
    webApp.openTelegramLink(TELEGRAM_BOT_URL);
  }, []);

  return (
    <div className="p2e-card" style={cardStyle}>
      <div style={{ fontSize: 18, fontWeight: 600, color: '#f5c518', lineHeight: 1.4 }}>
        Open this game from Telegram to play
      </div>
      <a
        href={TELEGRAM_BOT_URL}
        target="_blank"
        rel="noopener noreferrer"
        style={buttonStyle}
        onClick={handleClick}
      >
        Open in Telegram
      </a>
    </div>
  );
}

export function RequireTelegram({ children }: { children: ReactNode }) {
  const userId = useTelegramUserId();
  if (userId === null) return <TelegramGate />;
  return <>{children}</>;
}
