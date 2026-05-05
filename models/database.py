import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text,
    DateTime, Boolean, JSON
)
from sqlalchemy.orm import DeclarativeBase, Session

from config import DB_PATH


class Base(DeclarativeBase):
    pass


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Property info
    address = Column(String, nullable=False)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    units = Column(Integer)
    year_built = Column(Integer, nullable=True)
    sqft = Column(Integer, nullable=True)
    purchase_price = Column(Float)
    asking_price = Column(Float, nullable=True)
    monthly_rent_total = Column(Float, nullable=True)
    listing_url = Column(String)
    source = Column(String)  # crexi | zillow | manual | mock
    scraped_at = Column(DateTime)

    # Underwriting results — Year 1 snapshot
    gpr = Column(Float, nullable=True)
    vacancy_rate = Column(Float, nullable=True)
    egi = Column(Float, nullable=True)
    other_income = Column(Float, nullable=True)
    total_opex = Column(Float, nullable=True)
    noi = Column(Float, nullable=True)
    going_in_cap_rate = Column(Float, nullable=True)
    loan_amount = Column(Float, nullable=True)
    equity_invested = Column(Float, nullable=True)
    annual_ds = Column(Float, nullable=True)
    net_cash_flow_y1 = Column(Float, nullable=True)
    coc_y1 = Column(Float, nullable=True)
    dscr_y1 = Column(Float, nullable=True)
    price_per_unit = Column(Float, nullable=True)

    # Returns
    irr_5yr = Column(Float, nullable=True)
    irr_10yr = Column(Float, nullable=True)
    equity_multiple_5yr = Column(Float, nullable=True)
    equity_multiple_10yr = Column(Float, nullable=True)

    # AI analysis
    ai_score = Column(Float, nullable=True)       # 0–10 quantitative score
    ai_grade = Column(String, nullable=True)      # A/B/C/D/F
    ai_memo = Column(Text, nullable=True)         # investment thesis paragraph
    ai_risks = Column(JSON, nullable=True)        # list of risk bullets
    ai_strengths = Column(JSON, nullable=True)    # list of strength bullets

    # Deal tracking
    status = Column(String, default="pipeline")  # pipeline | underwritten | pass | pursuing | closed
    decision = Column(String, nullable=True)      # buy | pass | watch
    pass_reason = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    excel_path = Column(String, nullable=True)

    underwritten_at = Column(DateTime, nullable=True)
    uw_assumptions_json = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    engine = init_db()
    return Session(engine)


def upsert_deal(session: Session, deal_data: dict) -> Deal:
    existing = None
    if deal_data.get("listing_url"):
        existing = session.query(Deal).filter_by(
            listing_url=deal_data["listing_url"]
        ).first()

    if existing:
        for k, v in deal_data.items():
            if hasattr(existing, k) and v is not None:
                setattr(existing, k, v)
        session.commit()
        return existing
    else:
        deal = Deal(**{k: v for k, v in deal_data.items() if hasattr(Deal, k)})
        session.add(deal)
        session.commit()
        return deal
