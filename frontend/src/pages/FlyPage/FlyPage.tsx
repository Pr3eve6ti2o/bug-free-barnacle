import { FC, useCallback, useEffect, useState } from 'react';
import { gameApi, userApi, adminApi } from '@/services/api';
import { useTelegramUserId } from '@/hooks/useTelegramUser';
import { MiningCard } from '@/components/MiningCard/MiningCard';
import { WelcomeBonus } from '@/components/WelcomeBonus/WelcomeBonus';
import { TermsGate } from '@/components/TermsConsent/TermsConsent';
import { Page } from '@/components/Page.tsx';

// Ships by level
import ImperialDestroyer from '../../../assets/Imperial_Destroyer_Pixel_Art.png';
import Vostok from '../../../assets/Vostok_Pixel_Art.png';
import Starship from '../../../assets/Starship_Pixel_Art.png';
import SpaceShuttle from '../../../assets/Space_Shuttle_Pixel_Art.png';
import MilleniumFalcon from '../../../assets/Millenium_Falcon_Pixel_Art.png';
import EnergiaBuran from '../../../assets/Energia_Buran_Pixel_Art.png';
import Angara from '../../../assets/Angara_Pixel_Art.png';

import './FlyPage.css';
import '@/components/p2e.css';

const MAX_LEVEL = 7;
const SHIPS = [Vostok, SpaceShuttle, Angara, Starship, EnergiaBuran, MilleniumFalcon, ImperialDestroyer];

export const FlyPage: FC = () => {
    const userId = useTelegramUserId() as number;

    // T&C gate → welcome bonus sequencing
    const [termsAccepted, setTermsAccepted] = useState(false);
    const [welcomeDone, setWelcomeDone] = useState(
        () => { try { return localStorage.getItem(`sh_welcome_seen_${userId}`) === '1'; } catch { return false; } }
    );
    const markWelcomeSeen = () => {
        try { localStorage.setItem(`sh_welcome_seen_${userId}`, '1'); } catch { /* ignore */ }
        setWelcomeDone(true);
    };

    const [announcement, setAnnouncement] = useState('');
    const [balance, setBalance] = useState<number | null>(null);
    const [level, setLevel] = useState(1);
    const [loadError, setLoadError] = useState<string | null>(null);

    useEffect(() => {
        adminApi.getAnnouncement().then(r => setAnnouncement(r.text || '')).catch(() => { /* ignore */ });
    }, []);

    // Referral start_param: register the inviter once, before the first state fetch
    const consumeStartParam = useCallback(async () => {
        try {
            const raw = sessionStorage.getItem('sh_start_param');
            if (!raw) return;
            const refId = Number(raw);
            if (/^\d+$/.test(raw) && refId !== userId) {
                const username = window.Telegram?.WebApp?.initDataUnsafe?.user?.username || '';
                try {
                    await userApi.registerWithReferral(userId, username, refId);
                } catch { /* already registered — fine */ }
            }
            sessionStorage.removeItem('sh_start_param');
        } catch { /* ignore */ }
    }, [userId]);

    const initialize = useCallback(async () => {
        setLoadError(null);
        try {
            await consumeStartParam();
            const state = await gameApi.getGameState(userId);
            setBalance(state.balance);
            setLevel(state.level);
        } catch (error) {
            console.error('Error initializing game state:', error);
            setLoadError(error instanceof Error ? error.message : 'Failed to load the game state');
        }
    }, [consumeStartParam, userId]);

    useEffect(() => {
        void initialize();
    }, [initialize]);

    const ship = SHIPS[Math.min(level - 1, MAX_LEVEL - 1)] || SHIPS[0];

    return (
        <Page back={false}>
            <TermsGate telegramId={userId} onAccepted={() => setTermsAccepted(true)} />
            {termsAccepted && !welcomeDone && (
                <WelcomeBonus
                    telegramId={userId}
                    onClaimed={(newBalance) => {
                        setBalance(newBalance);
                        markWelcomeSeen();
                    }}
                    onSkip={markWelcomeSeen}
                />
            )}

            <div className="fly-page-container">
                {announcement && (
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                        marginBottom: 12, padding: '12px 14px', borderRadius: 16,
                        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                        fontSize: 13, fontWeight: 600, lineHeight: 1.4,
                    }}>
                        <span style={{ fontSize: 14 }}>📣</span>
                        <span>{announcement}</span>
                    </div>
                )}

                {loadError && (
                    <div className="p2e-card" style={{ margin: '14px auto', maxWidth: 420, textAlign: 'center' }}>
                        <div style={{ fontWeight: 750, fontSize: 16, marginBottom: 6 }}>Couldn't load the game</div>
                        <div style={{ fontSize: 13, opacity: 0.78, lineHeight: 1.45, marginBottom: 10 }}>{loadError}</div>
                        <button className="fly-action" onClick={() => void initialize()}>
                            <span>Retry</span>
                        </button>
                    </div>
                )}

                <div className="fly-balance-hero">
                    <div className="fly-balance-value tnum">
                        {balance === null ? '—' : Number(balance.toFixed(0)).toLocaleString('en-GB')}
                    </div>
                    <div className="fly-balance-unit">CSM</div>
                </div>

                <div className="stat-chips" style={{ justifyContent: 'center' }}>
                    <div className="stat-chip stat-chip-purple">
                        <span className="stat-chip-label">Level</span>
                        <span className="stat-chip-value tnum">{level}</span>
                    </div>
                    <div className="stat-chip stat-chip-gold">
                        <span className="stat-chip-label">Session</span>
                        <span className="stat-chip-value tnum">6h</span>
                    </div>
                </div>

                <div className="mining-ship fly-hero" aria-hidden>
                    <span className="ship-glow" />
                    <img src={ship} alt="" className="ship-image ship-float" />
                </div>

                <div className="fly-action">
                    <MiningCard
                        telegramId={userId}
                        onClaimed={(newBalance) => setBalance(newBalance)}
                    />
                </div>

                <p className="fly-hint">
                    Mining runs for 6 hours per session. Boost your power with
                    tasks, crew invites and holdings — then come back to claim.
                </p>
            </div>
        </Page>
    );
};
