from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from sqlalchemy import select
from app.models.user import User

router = APIRouter(prefix="/wallet", tags=["wallet"])

class WalletConnection(BaseModel):
    address: str


def _valid_ton_address(address: str) -> bool:
    """Same shape rule the withdrawal endpoint enforces: 48 chars, known
    TON prefix. Stops garbage strings from flipping `is_verified` (+10%)."""
    a = (address or "").strip()
    return len(a) == 48 and a[:2] in ("EQ", "UQ", "kQ", "0Q")


@router.post("/{telegram_id}/connect")
async def connect_wallet(telegram_id: int, wallet: WalletConnection, db: AsyncSession = Depends(get_db)):
    """Подключить TON кошелек к аккаунту пользователя"""
    if not _valid_ton_address(wallet.address):
        raise HTTPException(status_code=400, detail="Invalid TON address")
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.ton_wallet_address = wallet.address.strip()
    await db.commit()

    return {"success": True, "message": "Wallet connected successfully"}

@router.get("/{telegram_id}/status")
async def get_wallet_status(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Получить статус подключения кошелька пользователя"""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "is_connected": user.ton_wallet_address is not None,
        "address": user.ton_wallet_address
    }

@router.delete("/{telegram_id}/disconnect")
async def disconnect_wallet(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Отключить TON кошелек от аккаунта пользователя"""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.ton_wallet_address = None
    await db.commit()
    
    return {"success": True, "message": "Wallet disconnected successfully"}