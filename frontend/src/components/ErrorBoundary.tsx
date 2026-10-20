import {
  Component,
  type CSSProperties,
  type ComponentType,
  type GetDerivedStateFromError,
  type PropsWithChildren,
  type ReactNode,
} from 'react';

export interface ErrorBoundaryProps extends PropsWithChildren {
  fallback?: ReactNode | ComponentType<{ error: unknown }>;
}

interface ErrorBoundaryState {
  error?: unknown;
}

type TelegramWebApp = {
  close?: () => void;
};

function getTelegramWebApp(): TelegramWebApp | undefined {
  const { Telegram } = window as unknown as {
    Telegram?: { WebApp?: TelegramWebApp };
  };

  return Telegram?.WebApp;
}

function canCloseApp(): boolean {
  return typeof getTelegramWebApp()?.close === 'function';
}

function closeApp(): void {
  getTelegramWebApp()?.close?.();
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  try {
    return JSON.stringify(error) ?? String(error);
  } catch {
    return String(error);
  }
}

const overlayStyle: CSSProperties = {
  position: 'fixed',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '24px',
  boxSizing: 'border-box',
  background:
    'radial-gradient(120% 120% at 50% 0%, #10131f 0%, #06070c 60%)',
  color: '#f5f7ff',
  fontFamily: 'inherit',
  zIndex: 1000,
};

const cardStyle: CSSProperties = {
  width: '100%',
  maxWidth: '420px',
  padding: '24px',
  borderRadius: '20px',
  border: '1px solid rgba(245, 197, 24, 0.28)',
  background: 'linear-gradient(180deg, #12141d 0%, #0a0b12 100%)',
  boxShadow: '0 24px 60px rgba(0, 0, 0, 0.6)',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: '#f5c518',
};

const titleStyle: CSSProperties = {
  margin: 0,
  fontSize: '20px',
  lineHeight: 1.3,
  fontWeight: 700,
  color: '#f5f7ff',
};

const messageStyle: CSSProperties = {
  margin: 0,
  padding: '12px 14px',
  maxHeight: '160px',
  overflow: 'auto',
  borderRadius: '12px',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  background: 'rgba(255, 255, 255, 0.04)',
  color: '#c3c8d8',
  fontSize: '13px',
  lineHeight: 1.5,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
};

const buttonBaseStyle: CSSProperties = {
  appearance: 'none',
  width: '100%',
  padding: '14px 18px',
  borderRadius: '14px',
  fontSize: '16px',
  fontWeight: 700,
  cursor: 'pointer',
  fontFamily: 'inherit',
};

const primaryButtonStyle: CSSProperties = {
  ...buttonBaseStyle,
  border: 'none',
  background: '#f5c518',
  color: '#06070c',
  borderRadius: '999px',
  fontWeight: 600,
};

const secondaryButtonStyle: CSSProperties = {
  ...buttonBaseStyle,
  border: '1px solid rgba(245, 197, 24, 0.35)',
  background: 'transparent',
  color: '#f5c518',
};

export function ErrorFallback({ error }: { error: unknown }) {
  const showClose = canCloseApp();

  return (
    <div style={overlayStyle} role="alert">
      <div style={cardStyle}>
        <p style={eyebrowStyle}>Something went wrong</p>
        <h1 style={titleStyle}>The game hit a snag</h1>
        <pre style={messageStyle}>{formatError(error)}</pre>
        <button
          type="button"
          style={primaryButtonStyle}
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
        {showClose && (
          <button
            type="button"
            style={secondaryButtonStyle}
            onClick={closeApp}
          >
            Close
          </button>
        )}
      </div>
    </div>
  );
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {};

  // eslint-disable-next-line max-len
  static getDerivedStateFromError: GetDerivedStateFromError<ErrorBoundaryProps, ErrorBoundaryState> = (error) => ({ error });

  componentDidCatch(error: Error) {
    this.setState({ error });
  }

  render() {
    const {
      state: {
        error,
      },
      props: {
        fallback: Fallback,
        children,
      },
    } = this;

    if (!('error' in this.state)) {
      return children;
    }

    if (typeof Fallback === 'function') {
      return <Fallback error={error} />;
    }

    if (Fallback !== undefined && Fallback !== null) {
      return Fallback;
    }

    return <ErrorFallback error={error} />;
  }
}
