import { FC, useCallback, useEffect, useState, useRef } from 'react';
import { Wallet } from 'lucide-react';
import { Page } from '@/components/Page.tsx';
import { gameApi, walletApi } from '@/services/api';
import { WithdrawCard } from '@/components/WithdrawCard/WithdrawCard';
import { DropEventCard } from '@/components/DropEventCard/DropEventCard';
import { TonConnectButton, useTonWallet, useTonConnectUI } from '@tonconnect/ui-react';
import { toUserFriendlyAddress } from '@tonconnect/sdk';
import TONCoinPixel from '../../../assets/TON_Coin_Pixel.png';
import './DropPage.css';
import '@/components/p2e.css';
import { useTelegramUserId } from '@/hooks/useTelegramUser';

export const DropPage: FC = () => {
  const [balance, setBalance] = useState<number | null>(null);
  const [isBalanceLoading, setIsBalanceLoading] = useState(true);
  const [balanceError, setBalanceError] = useState(false);
  const [isWalletConnected, setIsWalletConnected] = useState(false);
  const [walletAddress, setWalletAddress] = useState('');

  const [tonConnectUI] = useTonConnectUI();
  const wallet = useTonWallet();
  const tonConnectRef = useRef<HTMLDivElement>(null);

  const userId = useTelegramUserId() as number;

  // Начальная проверка состояния кошелька
  useEffect(() => {
    const initializeWalletStatus = async () => {
      try {
        const walletStatus = await walletApi.getWalletStatus(Number(userId));
        console.log('Initial walletStatus:', walletStatus); // теперь это объект { is_connected, address }
        setIsWalletConnected(walletStatus.is_connected);
        if (walletStatus.address) {
          setWalletAddress(walletStatus.address);
        } else if (wallet) {
          await tonConnectUI.disconnect();
          setIsWalletConnected(false);
          setWalletAddress('');
        }
      } catch (error) {
        console.error('Error initializing wallet status:', error);
        setIsWalletConnected(false);
        setWalletAddress('');
      }
    };

    initializeWalletStatus();
  }, [userId, tonConnectUI]);

  // Исправленный вариант эффекта синхронизации
  useEffect(() => {
    const handleStatusChange = async (walletInfo: any) => {
      // Если нет информации о кошельке от tonconnect
      if (!walletInfo) {
        // НЕ очищаем кошелек сразу, а проверяем БД
        console.log('Local wallet state changed. Checking server state...');
        
        try {
          // Проверяем, есть ли кошелек в БД
          const walletStatus = await walletApi.getWalletStatus(Number(userId));
          console.log('Server wallet status after local change:', walletStatus);
          
          // Если в БД кошелек подключен и есть адрес - используем его
          if (walletStatus.is_connected && walletStatus.address) {
            console.log('Server has wallet connected, maintaining state');
            setIsWalletConnected(true);
            setWalletAddress(walletStatus.address);
          } else {
            // Только если в БД нет подключения, то отключаем
            console.log('Server confirms wallet is not connected');
            setIsWalletConnected(false);
            setWalletAddress('');
          }
        } catch (error) {
          console.error('Error checking wallet status:', error);
          // При ошибке сохраняем текущее состояние
        }
        return;
      }

      // Если есть информация о кошельке
      try {
        const userFriendlyAddress = toUserFriendlyAddress(walletInfo.account.address);
        console.log('Wallet connected locally:', userFriendlyAddress);
        
        // Сначала устанавливаем локальное состояние
        setIsWalletConnected(true);
        setWalletAddress(userFriendlyAddress);
        
        // Затем синхронизируем с сервером
        await walletApi.connectWallet(Number(userId), userFriendlyAddress);
      } catch (error) {
        console.error('Error syncing wallet with server:', error);
      }
    };

    const unsubscribe = tonConnectUI.onStatusChange(handleStatusChange);
    return () => { unsubscribe(); };
  }, [tonConnectUI, userId]);

  // Баланс: последний успешный ответ сохраняется, ошибка его не обнуляет
  const fetchBalance = useCallback(async () => {
    try {
      setIsBalanceLoading(true);
      const state = await gameApi.getGameState(userId);
      setBalance(state.balance);
      setBalanceError(false);
    } catch (error) {
      console.error('Error fetching balance:', error);
      setBalanceError(true);
    } finally {
      setIsBalanceLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchBalance();
    const interval = setInterval(fetchBalance, 10000);
    return () => clearInterval(interval);
  }, [fetchBalance]);


  const connectWallet = async () => {
    try {
      await tonConnectUI.openModal();
    } catch (error) {
      console.error('Failed to open wallet modal:', error);
      alert('Failed to connect wallet. Please try again.');
    }
  };

  const disconnectWallet = async () => {
    try {
      // Сначала отключаем в БД
      await walletApi.disconnectWallet(Number(userId));
      // Затем локально
      await tonConnectUI.disconnect();
      // И обновляем UI
      setIsWalletConnected(false);
      setWalletAddress('');
    } catch (error) {
      console.error('Failed to disconnect wallet:', error);
    }
  };

  const copyWalletAddress = () => {
    navigator.clipboard.writeText(walletAddress);
    alert('Wallet address copied to clipboard!');
  };

  return (
    <Page back={false}>
      <div className="drop-page-container">
        <div className="coins-container">
          <div className="sh-label balance-title">Balance</div>
          <div className="coins-amount tnum">
            {balance === null ? '—' : balance.toFixed(0)}
            {balance !== null && <span className="coins-unit">CSM</span>}
          </div>
          {balanceError && (
            <button className="balance-retry" onClick={fetchBalance} disabled={isBalanceLoading}>
              Retry
            </button>
          )}
        </div>

        <DropEventCard userId={Number(userId)} onClaimed={(b) => setBalance(b)} />

        <img src={TONCoinPixel} alt="TON Coin" className="ton-coin-image" />

        <p className="drop-hint">Connect your TON wallet to prepare for the token drop.</p>

        <div className="hidden-ton-connect" ref={tonConnectRef}>
          <TonConnectButton />
        </div>

        {wallet && walletAddress ? (
          <div className="connected-wallet-container">
            <div className="wallet-info">
              <span className="wallet-status-dot" />
              <p className="wallet-address tnum" onClick={copyWalletAddress} title="Tap to copy">
                {`${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`}
              </p>
              <p className="wallet-connected-text">Wallet connected</p>
            </div>
            <button className="connect-wallet-button ghost" onClick={disconnectWallet}>
              <Wallet className="wallet-icon" />
              <span className="wallet-button-text">Disconnect</span>
            </button>
          </div>
        ) : isWalletConnected && walletAddress ? (
          <div className="connected-wallet-container">
            <div className="wallet-info">
              <span
                className="wallet-status-dot"
                style={{ background: 'rgba(138, 143, 156, 0.6)', boxShadow: 'none' }}
              />
              <p className="wallet-address tnum" onClick={copyWalletAddress} title="Tap to copy">
                {`${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`}
              </p>
              <p className="wallet-connected-text">Wallet linked — reconnect to withdraw</p>
            </div>
            <button className="connect-wallet-button" onClick={connectWallet}>
              <Wallet className="wallet-icon" />
              <span className="wallet-button-text">Reconnect</span>
            </button>
          </div>
        ) : (
          <div className="wallet-button-container">
            <button className="connect-wallet-button" onClick={connectWallet}>
              <Wallet className="wallet-icon" />
              <span className="wallet-button-text">Connect TON wallet</span>
            </button>
          </div>
        )}

        <div style={{ height: 16 }} />
        <WithdrawCard
          telegramId={userId}
          balance={balance === null ? -1 : balance}
          onRequested={(newBalance) => setBalance(newBalance)}
        />
      </div>
    </Page>
  );
};