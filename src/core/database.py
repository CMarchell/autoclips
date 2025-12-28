"""SQLite database for tracking videos, topics, and footage usage."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from .config import get_database_path, settings

Base = declarative_base()


class VideoProject(Base):
    """Tracks all video projects created."""

    __tablename__ = "video_projects"

    id = Column(String, primary_key=True)  # UUID-style ID
    topic = Column(Text, nullable=False)
    niche = Column(String, nullable=True)
    status = Column(String, default="draft")  # draft, preview, approved, killed
    script = Column(Text, nullable=True)
    voice_id = Column(String, nullable=True)
    music_track = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    footage_clips = relationship("FootageUsage", back_populates="project")
    metadata = relationship("VideoMetadata", back_populates="project", uselist=False)


class FootageUsage(Base):
    """Tracks footage clips used in videos."""

    __tablename__ = "footage_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    pexels_video_id = Column(Integer, nullable=False)
    keyword = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    start_time = Column(Float, nullable=True)  # When clip starts in video
    duration = Column(Float, nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("VideoProject", back_populates="footage_clips")


class VideoMetadata(Base):
    """Stores generated metadata for videos."""

    __tablename__ = "video_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("video_projects.id"), nullable=False)
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array stored as text
    hashtags = Column(Text, nullable=True)  # JSON array stored as text
    platform_tiktok = Column(Text, nullable=True)  # Platform-specific metadata
    platform_youtube = Column(Text, nullable=True)
    platform_instagram = Column(Text, nullable=True)

    project = relationship("VideoProject", back_populates="metadata")


class TopicHistory(Base):
    """Tracks topics used to prevent repetition."""

    __tablename__ = "topic_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)
    niche = Column(String, nullable=True)
    topic_hash = Column(String, nullable=False)  # For faster lookups
    created_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """Database interface for AutoClips."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # Project operations
    def create_project(
        self,
        project_id: str,
        topic: str,
        niche: Optional[str] = None,
    ) -> VideoProject:
        """Create a new video project."""
        with self.get_session() as session:
            project = VideoProject(
                id=project_id,
                topic=topic,
                niche=niche,
                status="draft",
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def get_project(self, project_id: str) -> Optional[VideoProject]:
        """Get a project by ID."""
        with self.get_session() as session:
            return session.query(VideoProject).filter_by(id=project_id).first()

    def update_project(self, project_id: str, **kwargs) -> Optional[VideoProject]:
        """Update project fields."""
        with self.get_session() as session:
            project = session.query(VideoProject).filter_by(id=project_id).first()
            if project:
                for key, value in kwargs.items():
                    if hasattr(project, key):
                        setattr(project, key, value)
                session.commit()
                session.refresh(project)
            return project

    def list_projects(self, status: Optional[str] = None) -> list[VideoProject]:
        """List projects, optionally filtered by status."""
        with self.get_session() as session:
            query = session.query(VideoProject)
            if status:
                query = query.filter_by(status=status)
            return query.order_by(VideoProject.created_at.desc()).all()

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its related records."""
        with self.get_session() as session:
            project = session.query(VideoProject).filter_by(id=project_id).first()
            if project:
                # Delete related records
                session.query(FootageUsage).filter_by(project_id=project_id).delete()
                session.query(VideoMetadata).filter_by(project_id=project_id).delete()
                session.delete(project)
                session.commit()
                return True
            return False

    # Footage tracking
    def add_footage_usage(
        self,
        project_id: str,
        pexels_video_id: int,
        keyword: Optional[str] = None,
        filename: Optional[str] = None,
        start_time: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> FootageUsage:
        """Record footage usage for a project."""
        with self.get_session() as session:
            usage = FootageUsage(
                project_id=project_id,
                pexels_video_id=pexels_video_id,
                keyword=keyword,
                filename=filename,
                start_time=start_time,
                duration=duration,
            )
            session.add(usage)
            session.commit()
            session.refresh(usage)
            return usage

    def is_footage_recently_used(self, pexels_video_id: int) -> bool:
        """Check if footage was used within the cooldown period."""
        cooldown = settings.deduplication.footage_cooldown_count
        with self.get_session() as session:
            recent_usage = (
                session.query(FootageUsage)
                .order_by(FootageUsage.used_at.desc())
                .limit(cooldown)
                .all()
            )
            return any(u.pexels_video_id == pexels_video_id for u in recent_usage)

    def get_footage_for_project(self, project_id: str) -> list[FootageUsage]:
        """Get all footage clips for a project."""
        with self.get_session() as session:
            return (
                session.query(FootageUsage)
                .filter_by(project_id=project_id)
                .order_by(FootageUsage.start_time)
                .all()
            )

    def remove_footage_from_project(
        self, project_id: str, filename: Optional[str] = None, keyword: Optional[str] = None
    ) -> bool:
        """Remove footage from a project by filename or keyword."""
        with self.get_session() as session:
            query = session.query(FootageUsage).filter_by(project_id=project_id)
            if filename:
                query = query.filter_by(filename=filename)
            elif keyword:
                query = query.filter(FootageUsage.keyword.ilike(f"%{keyword}%"))
            else:
                return False

            deleted = query.delete(synchronize_session=False)
            session.commit()
            return deleted > 0

    # Topic history
    def add_topic_to_history(self, topic: str, niche: Optional[str] = None) -> TopicHistory:
        """Add a topic to the history."""
        import hashlib

        topic_hash = hashlib.md5(topic.lower().strip().encode()).hexdigest()

        with self.get_session() as session:
            history = TopicHistory(
                topic=topic,
                niche=niche,
                topic_hash=topic_hash,
            )
            session.add(history)
            session.commit()
            session.refresh(history)
            return history

    def is_topic_recently_used(self, topic: str) -> bool:
        """Check if a similar topic was used within the cooldown period."""
        import hashlib

        topic_hash = hashlib.md5(topic.lower().strip().encode()).hexdigest()
        cooldown_days = settings.deduplication.topic_cooldown_days
        cutoff = datetime.utcnow() - timedelta(days=cooldown_days)

        with self.get_session() as session:
            return (
                session.query(TopicHistory)
                .filter(TopicHistory.topic_hash == topic_hash, TopicHistory.created_at > cutoff)
                .first()
                is not None
            )

    def get_recent_topics(self, limit: int = 50) -> list[TopicHistory]:
        """Get recently used topics."""
        with self.get_session() as session:
            return (
                session.query(TopicHistory)
                .order_by(TopicHistory.created_at.desc())
                .limit(limit)
                .all()
            )

    # Metadata operations
    def save_metadata(
        self,
        project_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        hashtags: Optional[str] = None,
    ) -> VideoMetadata:
        """Save or update metadata for a project."""
        with self.get_session() as session:
            metadata = session.query(VideoMetadata).filter_by(project_id=project_id).first()
            if metadata:
                if title:
                    metadata.title = title
                if description:
                    metadata.description = description
                if tags:
                    metadata.tags = tags
                if hashtags:
                    metadata.hashtags = hashtags
            else:
                metadata = VideoMetadata(
                    project_id=project_id,
                    title=title,
                    description=description,
                    tags=tags,
                    hashtags=hashtags,
                )
                session.add(metadata)
            session.commit()
            session.refresh(metadata)
            return metadata

    def get_metadata(self, project_id: str) -> Optional[VideoMetadata]:
        """Get metadata for a project."""
        with self.get_session() as session:
            return session.query(VideoMetadata).filter_by(project_id=project_id).first()


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
