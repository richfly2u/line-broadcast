"""LINE 自動群發貼文系統 — FastAPI 主程式"""
import os
import datetime
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, get_db
from models import Post, SendLog
from line_bot import broadcast_message, build_text_message, build_image_message
from scheduler import check_and_send

APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(check_and_send, "interval", minutes=1, id="send_check")
    scheduler.start()
    logger.info("排程器已啟動 (每分鐘檢查到期貼文)")
    yield
    scheduler.shutdown()


app = FastAPI(title="LINE 群發貼文系統", lifespan=lifespan)

# 掛載靜態檔案
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


# ─── Pydantic 模型 ───

class PostCreate(BaseModel):
    title: str = ""
    content: str = ""
    image_url: str = ""
    msg_type: str = "text"
    schedule_at: str | None = None  # ISO 格式
    template_name: str = ""


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    image_url: str | None = None
    msg_type: str | None = None
    schedule_at: str | None = None
    status: str | None = None


class SendRequest(BaseModel):
    post_id: int | None = None
    content: str = ""
    image_url: str = ""
    msg_type: str = "text"
    target_type: str = "broadcast"  # broadcast / multicast


class FriendCreate(BaseModel):
    user_id: str
    display_name: str = ""


class PersonalizedSendRequest(BaseModel):
    content: str = ""
    image_url: str = ""
    name_placeholder: str = "{name}"
    user_ids: list = []  # 為空時發給所有已存好友


# ─── API 路由 ───

@app.get("/")
async def root():
    return {"message": "LINE 群發貼文系統 API", "version": "1.0"}


# 貼文管理
@app.get("/api/posts")
def list_posts(db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.created_at.desc()).limit(100).all()
    return [format_post(p) for p in posts]


@app.get("/api/posts/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "貼文不存在")
    return format_post(post)


@app.post("/api/posts")
def create_post(data: PostCreate, db: Session = Depends(get_db)):
    schedule_at = None
    if data.schedule_at:
        try:
            schedule_at = datetime.datetime.fromisoformat(data.schedule_at)
        except:
            pass

    post = Post(
        title=data.title,
        content=data.content,
        image_url=data.image_url,
        msg_type=data.msg_type or "text",
        template_name=data.template_name,
        schedule_at=schedule_at,
        status="scheduled" if schedule_at else "draft",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return format_post(post)


@app.put("/api/posts/{post_id}")
def update_post(post_id: int, data: PostUpdate, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "貼文不存在")

    for field, value in data.dict(exclude_unset=True).items():
        if field == "schedule_at" and value:
            try:
                value = datetime.datetime.fromisoformat(value)
                setattr(post, field, value)
                if post.status == "draft":
                    post.status = "scheduled"
            except:
                pass
        elif value is not None:
            setattr(post, field, value)

    db.commit()
    db.refresh(post)
    return format_post(post)


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "貼文不存在")
    db.delete(post)
    db.commit()
    return {"status": "deleted"}


# 立即發送
@app.post("/api/send")
async def send_now(data: SendRequest, db: Session = Depends(get_db)):
    if data.post_id:
        post = db.query(Post).filter(Post.id == data.post_id).first()
        if not post:
            raise HTTPException(404, "貼文不存在")
        content = post.content
        image_url = post.image_url
        msg_type = post.msg_type
    else:
        content = data.content
        image_url = data.image_url
        msg_type = data.msg_type

    messages = []
    if content:
        messages.append({"type": "text", "text": content})
    if image_url:
        messages.append({"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url})
    if not messages:
        return {"status": "error", "message": "沒有可發送的內容"}

    result = await broadcast_message(messages)

    # 記錄
    log = SendLog(
        post_id=data.post_id,
        msg_type=msg_type,
        content_preview=content[:100],
        status=result["status"],
        response=result,
    )
    db.add(log)
    db.commit()

    return result


# 取得好友列表
@app.get("/api/followers")
async def list_followers():
    """列出所有 LINE 好友的 user_id"""
    from line_bot import get_all_followers
    user_ids = await get_all_followers()
    return {"total": len(user_ids), "followers": user_ids}


# 取得好友名稱
@app.get("/api/followers/{user_id}")
async def get_follower_info(user_id: str):
    from line_bot import get_user_profile
    profile = await get_user_profile(user_id)
    return profile


# ─── LINE Webhook（自動接收好友加入／訊息）───

@app.post("/webhook")
async def line_webhook(request: Request, db: Session = Depends(get_db)):
    from models import Friend

    body = await request.json()
    events = body.get("events", [])

    for event in events:
        event_type = event.get("type", "")
        source = event.get("source", {})
        user_id = source.get("userId", "")

        if not user_id:
            continue

        # 好友加入或傳訊息 → 自動存到好友清單
        if event_type in ("follow", "message", "unfollow"):
            from line_bot import get_user_profile
            profile = await get_user_profile(user_id)
            name = profile.get("display_name", "")

            existing = db.query(Friend).filter(Friend.user_id == user_id).first()
            if not existing:
                db.add(Friend(user_id=user_id, display_name=name))
                db.commit()
                print(f"[Webhook] 新好友加入: {name} ({user_id})")
            else:
                if name and name != existing.display_name:
                    existing.display_name = name
                    db.commit()
                print(f"[Webhook] 已存在好友: {name} ({user_id})")

    return {"status": "ok"}


# ─── 好友管理（手動加入，取代被限制的 LINE API）───

@app.get("/api/friends")
def list_friends(db: Session = Depends(get_db)):
    from models import Friend
    friends = db.query(Friend).order_by(Friend.added_at.desc()).all()
    return [
        {"id": f.id, "user_id": f.user_id, "display_name": f.display_name, "added_at": f.added_at.isoformat()}
        for f in friends
    ]


@app.post("/api/friends")
async def add_friend(data: FriendCreate, db: Session = Depends(get_db)):
    from models import Friend
    from line_bot import get_user_profile

    # 自動查姓名
    name = data.display_name
    if not name:
        profile = await get_user_profile(data.user_id)
        if profile.get("status") == "success":
            name = profile.get("display_name", "")

    existing = db.query(Friend).filter(Friend.user_id == data.user_id).first()
    if existing:
        existing.display_name = name or existing.display_name
    else:
        db.add(Friend(user_id=data.user_id, display_name=name))
    db.commit()
    return {"status": "success", "user_id": data.user_id, "display_name": name}


@app.delete("/api/friends/{friend_id}")
def remove_friend(friend_id: int, db: Session = Depends(get_db)):
    from models import Friend
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f:
        raise HTTPException(404, "好友不存在")
    db.delete(f)
    db.commit()
    return {"status": "deleted"}


# 個性化推播（每個人收到帶自己名字的訊息）
@app.post("/api/send/personalized")
async def send_personalized(data: PersonalizedSendRequest, db: Session = Depends(get_db)):
    from line_bot import get_user_profile, push_message
    from models import Friend

    # 若沒指定 user_ids，從 DB 拉所有好友
    if data.user_ids:
        targets = [{"user_id": uid} for uid in data.user_ids]
    else:
        friends = db.query(Friend).all()
        targets = [{"user_id": f.user_id} for f in friends]
    
    if not targets:
        return {"status": "error", "message": "沒有好友，請先用 /api/friends 加入"}

    results = []
    for t in targets:
        profile = await get_user_profile(t["user_id"])
        name = profile.get("display_name", "好友")
        personalized = data.content.replace(data.name_placeholder, name)

        messages = []
        if personalized:
            messages.append({"type": "text", "text": personalized})
        if data.image_url:
            messages.append({"type": "image", "originalContentUrl": data.image_url, "previewImageUrl": data.image_url})

        if messages:
            result = await push_message(t["user_id"], messages)
            results.append({"user_id": t["user_id"], "name": name, "status": result["status"]})

    success = sum(1 for r in results if r["status"] == "success")
    return {"total": len(results), "success": success, "failed": len(results) - success, "details": results}


# 發送記錄
@app.get("/api/logs")
def list_logs(db: Session = Depends(get_db)):
    logs = db.query(SendLog).order_by(SendLog.sent_at.desc()).limit(100).all()
    return [
        {
            "id": log.id,
            "post_id": log.post_id,
            "msg_type": log.msg_type,
            "content_preview": log.content_preview,
            "status": log.status,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        }
        for log in logs
    ]


# 統計
@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Post).count()
    draft = db.query(Post).filter(Post.status == "draft").count()
    scheduled = db.query(Post).filter(Post.status == "scheduled").count()
    sent = db.query(Post).filter(Post.status == "sent").count()
    failed = db.query(Post).filter(Post.status == "failed").count()
    sent_logs = db.query(SendLog).count()
    return {
        "total_posts": total,
        "draft": draft,
        "scheduled": scheduled,
        "sent": sent,
        "failed": failed,
        "total_sends": sent_logs,
    }


# 範本
@app.get("/api/templates")
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(Post).filter(Post.template_name != "").all()
    return [format_post(p) for p in templates]


def format_post(p: Post):
    return {
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "image_url": p.image_url,
        "msg_type": p.msg_type,
        "status": p.status,
        "template_name": p.template_name,
        "schedule_at": p.schedule_at.isoformat() if p.schedule_at else None,
        "sent_at": p.sent_at.isoformat() if p.sent_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# 管理後台（SPA）
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8") as f:
        return f.read()
