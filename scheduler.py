"""排程器 — 定期檢查並發送到期貼文"""
import datetime
import logging
from database import SessionLocal
from models import Post, SendLog
from line_bot import broadcast_message, build_text_message, build_image_message

logger = logging.getLogger(__name__)


async def check_and_send():
    """每分鐘執行：找出到期的 scheduled 貼文並發送"""
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        due_posts = (
            db.query(Post)
            .filter(Post.status == "scheduled", Post.schedule_at <= now)
            .all()
        )

        for post in due_posts:
            try:
                # 建立訊息
                messages = []
                if post.msg_type == "text":
                    messages = build_text_message(post.content)
                elif post.msg_type == "image":
                    messages = build_image_message(post.image_url)
                else:
                    messages = build_text_message(post.content)

                # 發送
                result = await broadcast_message(messages)

                # 更新狀態
                post.status = "sent" if result["status"] == "success" else "failed"
                post.sent_at = now
                post.send_result = result

                # 記錄
                log = SendLog(
                    post_id=post.id,
                    msg_type=post.msg_type,
                    content_preview=post.content[:100],
                    status=post.status,
                    response=result,
                )
                db.add(log)
                logger.info(f"Post {post.id} sent: {result['status']}")

            except Exception as e:
                post.status = "failed"
                post.send_result = {"error": str(e)}
                logger.error(f"Post {post.id} failed: {e}")

        db.commit()

    finally:
        db.close()
