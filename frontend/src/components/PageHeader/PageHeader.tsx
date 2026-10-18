import React, { useState, useEffect } from 'react';
import WebApp from '@twa-dev/sdk';
import './PageHeader.css';
import '@/components/p2e.css';
import { ModalWindow } from '../ModalWindow/ModalWindow';
import { TermsReader } from '../TermsConsent/TermsConsent';

import { gameApi, miningApi } from '../../services/api';



import FlyPageIcon from '../icons/FlyPageIcon/FlyPageIcon.svg';
import BoostPageIcon from '../icons/BoostPageIcon/BoostPageIcon.svg';
import TasksPageIcon from '../icons/TasksPageIcon/TasksPageIcon.svg';
import MePageIcon from '../icons/MePageIcon/MePageIcon.svg';
import DropPageIcon from '../icons/DropPageIcon/DropPageIcon.svg';


export const PageHeader: React.FC = () => {

    const [passiveIncome, setPassiveIncome] = useState(0);
    const [miningRate, setMiningRate] = useState<number | null>(null);
    const [showHelpModal, setShowHelpModal] = useState(false);
    const [showTermsModal, setShowTermsModal] = useState(false);
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 99281932;

    // Загружаем пассивный доход при монтировании
    useEffect(() => {
        const fetchPassiveIncome = async () => {
            try {
                const data = await gameApi.getPassiveIncome(userId);
                setPassiveIncome(data.passive_income_rate);
            } catch (error) {
                console.error('Error fetching passive income:', error);
            }
        };

        // Mining rate takes precedence in the header pill while a session runs
        const fetchMiningRate = async () => {
            try {
                const s = await miningApi.getStatus(userId);
                // Farming model: the pill shows mining power — the live
                // session rate while mining, otherwise the potential rate.
                setMiningRate(s.hourly_rate ?? s.potential?.hourly_rate ?? null);
            } catch {
                /* offline — keep last */
            }
        };

        // Загружаем пассивный доход при монтировании
        fetchPassiveIncome();
        fetchMiningRate();

        // Обновляем отображение пассивного дохода каждые 30 секунд
        const displayIntervalId = setInterval(() => { fetchPassiveIncome(); fetchMiningRate(); }, 30000);
        
        // Применяем пассивный доход каждую минуту
        const applyIncomeInterval = setInterval(async () => {
            try {
                const result = await gameApi.applyPassiveIncome(userId);
                if (result?.applied_income > 0) {
                    console.log(`Passive income applied: +${result.applied_income} CSM`);
                }
            } catch (error) {
                console.error('Error applying passive income:', error);
            }
        }, 60000); // 60 секунд = 1 минута
        
        // Очищаем оба интервала при размонтировании компонента
        return () => {
            clearInterval(displayIntervalId);
            clearInterval(applyIncomeInterval);
        };
    }, [userId]);
    
    const handleHelpClick = () => {
        setShowHelpModal(true);
    };

    const user = WebApp.initDataUnsafe.user;
    const userInitial = (user?.first_name?.[0] || user?.username?.[0] || '?').toUpperCase();

    return (
        <>
            <header className="page-header">
                <div className="avatar-container">
                    {user?.photo_url ? (
                        <img
                            src={user.photo_url}
                            alt="User Avatar"
                            className="user-avatar"
                        />
                    ) : (
                        <span className="user-avatar-fallback">{userInitial}</span>
                    )}
                </div>
                <div className="farming-rate-container">
                    <div className="farming-rate tnum">
                        {(miningRate ?? passiveIncome).toLocaleString()} CSM/h
                    </div>
                </div>
                <button
                    onClick={handleHelpClick}
                    className="help-button"
                >
                    <span className="help-icon">?</span>
                </button>
            </header>

            <ModalWindow
                isOpen={showHelpModal}
                onClose={() => setShowHelpModal(false)}
                title="Quick guide"
            >
                <div className="help-content">
                    <div className="help-section">
                        <h3 className="help-section-title">
                            Fly
                            <img src={FlyPageIcon} alt="Fly icon" />
                        </h3>
                        <p>The main game screen — tap the ship to earn coins. Also home to daily bonuses, the NFT collection and your level progress.</p>
                    </div>

                    <div className="help-section">
                        <h3 className="help-section-title">
                            Boost
                            <img src={BoostPageIcon} alt="Boost icon" />
                        </h3>
                        <p>Upgrade your ship with modules across four categories: energy, navigation, research and defence. Each upgrade raises income and tap power.</p>
                    </div>

                    <div className="help-section">
                        <h3 className="help-section-title">
                            Tasks
                            <img src={TasksPageIcon} alt="Tasks icon" />
                        </h3>
                        <p>Complete daily and global tasks for extra rewards. Daily tasks refresh every day.</p>
                    </div>

                    <div className="help-section">
                        <h3 className="help-section-title">
                            Me
                            <img src={MePageIcon} alt="Me icon" />
                        </h3>
                        <p>See friends who play, ranked by balance. Invite friends to earn bonuses.</p>
                    </div>

                    <div className="help-section">
                        <h3 className="help-section-title">
                            Drop
                            <img src={DropPageIcon} alt="Drop icon" />
                        </h3>
                        <p>Connect a TON wallet to manage your game balance.</p>
                    </div>

                    <button
                        className="p2e-btn p2e-btn-ghost"
                        style={{ marginTop: 12, minHeight: 44 }}
                        onClick={() => { setShowHelpModal(false); setShowTermsModal(true); }}
                    >
                        Terms &amp; Conditions
                    </button>
                </div>
            </ModalWindow>

            <ModalWindow
                isOpen={showTermsModal}
                onClose={() => setShowTermsModal(false)}
                title="Terms & Conditions"
            >
                <TermsReader />
            </ModalWindow>
        </>
    );
}