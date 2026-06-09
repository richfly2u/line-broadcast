"""資料庫模型"""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from database import Base


class Post(Base):
    """貼文"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="")           # 標題
    content = Column(Text, default="")                  # 文字內容
    image_url = Column(String(500), default="")         # 圖片網址
    msg_type = Column(String(20), default="text")       # text / image / flex
    status = Column(String(20), default="draft")        # draft / scheduled / sent / failed
    schedule_at = Column(DateTime, nullable=True)       # 排程時間
    sent_at = Column(DateTime, nullable=True)           # 實際發送時間
    send_result = Column(JSON, nullable=True)           # LINE API 回傳結果
    template_name = Column(String(100), default="")     # 範本名稱（空白則非範本）
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class SendLog(Base):
    """發送記錄"""
    __tablename__ = "send_logs"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, nullable=True)            # 關聯貼文 ID
    msg_type = Column(String(20))
    content_preview = Column(String(200), default="")
    target_type = Column(String(20), default="broadcast")  # broadcast / multicast / push
    target_ids = Column(JSON, nullable=True)
    status = Column(String(20), default="success")       # success / failed
    response = Column(JSON, nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)


class Friend(Base):
    """好友"""
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), default="")
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
