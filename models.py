from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    telegram_id = Column(BigInteger, primary_key=True)
    btc_address = Column(String)
    eth_address = Column(String)
    usdt_address = Column(String)
    btc_balance = Column(Float, default=0.0)
    eth_balance = Column(Float, default=0.0)
    usdt_balance = Column(Float, default=0.0)

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    transaction_type = Column(String)
    coin_type = Column(String)
    amount = Column(Float)
    fee = Column(Float)
    from_address = Column(String)
    to_address = Column(String)
    tx_hash = Column(String)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)