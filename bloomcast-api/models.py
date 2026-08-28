from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from db import Base, engine


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="user")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lake_name = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    approved = Column(Boolean, default=False, nullable=False)  # moderation gate
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="posts")


def create_tables():
    Base.metadata.create_all(bind=engine)