from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "dsa"}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    oauth_provider = Column(String, nullable=True)
    oauth_id = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    github_username = Column(String, nullable=True)       # original GitHub login (e.g. "john-doe")
    github_access_token = Column(String, nullable=True)   # OAuth token for GitHub API
    role = Column(String, default="user", nullable=False)
    practice_days = Column(String, default="", nullable=False)

    progress = relationship("UserQuestionProgress", back_populates="user", cascade="all, delete")
    logs = relationship("PracticeLog", back_populates="user", cascade="all, delete")
    pattern_notes = relationship("UserPatternNote", back_populates="user", cascade="all, delete")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = {"schema": "dsa"}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, unique=True)
    pattern = Column(String)
    category = Column(String, default="Mixed")
    difficulty = Column(String, default="Medium")
    hint = Column(String, nullable=True)
    description = Column(String, nullable=True)

    logs = relationship("PracticeLog", back_populates="question", cascade="all, delete")
    progress = relationship("UserQuestionProgress", back_populates="question", cascade="all, delete")


class UserQuestionProgress(Base):
    __tablename__ = "user_question_progress"
    __table_args__ = (
        UniqueConstraint("question_id", "user_id", name="uq_progress_question_user"),
        {"schema": "dsa"},
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("dsa.questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("dsa.users.id"), nullable=False)

    coverage_status = Column(String, default="Not Covered")
    revision_status = Column(String, default="Pending")
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=0)
    next_revision = Column(String, nullable=True)
    accuracy = Column(Float, nullable=True)
    suggestions = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    my_gap_analysis = Column(String, nullable=True)

    question = relationship("Question", back_populates="progress")
    user = relationship("User", back_populates="progress")


class PracticeLog(Base):
    __tablename__ = "practice_logs"
    __table_args__ = {"schema": "dsa"}

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("dsa.questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("dsa.users.id"), nullable=False)
    date = Column(String)
    logic = Column(String, default="")
    code = Column(String, default="")
    time_taken = Column(Integer, default=0)
    correct = Column(Boolean, default=True)
    hint_used = Column(Boolean, default=False)

    question = relationship("Question", back_populates="logs")
    user = relationship("User", back_populates="logs")


class UserPatternNote(Base):
    __tablename__ = "user_pattern_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "pattern", name="uq_pattern_note_user"),
        {"schema": "dsa"},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("dsa.users.id"), nullable=False)
    pattern = Column(String, nullable=False)
    notes = Column(String, default="")
    memory_techniques = Column(String, default="")

    user = relationship("User", back_populates="pattern_notes")
