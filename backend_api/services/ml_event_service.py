from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
import logging

from models import MLEvent
from schemas import MLEventCreate, MLEventResponse

logger = logging.getLogger("backend_api.services.ml_event_service")

FAKE_PROBABILITY_THRESHOLD = 0.75


def log_ml_event(db: Session, event: MLEventCreate) -> MLEvent:
    """
    Persist a new ML detection event to the database.

    If the fake_probability is above the threshold, a warning is logged
    which can be extended to trigger alerts (email, webhook, etc.)
    """
    db_event = MLEvent(
        call_id=event.call_id,
        speaker_id=event.speaker_id,
        fake_probability=event.fake_probability,
        timestamp=datetime.utcnow(),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    if event.fake_probability >= FAKE_PROBABILITY_THRESHOLD:
        logger.warning(
            f"[ALERT] High fake probability detected! "
            f"call_id={event.call_id}, speaker_id={event.speaker_id}, "
            f"score={event.fake_probability:.2%}"
        )

    return db_event


def get_events_for_call(db: Session, call_id: UUID) -> list[MLEvent]:
    """Return all ML events for a given call ID sorted by timestamp."""
    return (
        db.query(MLEvent)
        .filter(MLEvent.call_id == call_id)
        .order_by(MLEvent.timestamp.asc())
        .all()
    )
