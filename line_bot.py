"""LINE Messaging API 封裝"""
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
API_BASE = "https://api.line.me/v2/bot"


def _headers():
    return {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


async def broadcast_message(messages: list) -> dict:
    """廣播訊息給所有好友"""
    if not CHANNEL_ACCESS_TOKEN:
        return {"status": "error", "message": "未設定 LINE_CHANNEL_ACCESS_TOKEN"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/message/broadcast",
            headers=_headers(),
            json={"messages": messages},
        )
        return {
            "status": "success" if resp.is_success else "failed",
            "http_code": resp.status_code,
            "response": resp.text,
        }


async def multicast_message(user_ids: list, messages: list) -> dict:
    """發送給指定用戶"""
    if not CHANNEL_ACCESS_TOKEN:
        return {"status": "error", "message": "未設定 LINE_CHANNEL_ACCESS_TOKEN"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/message/multicast",
            headers=_headers(),
            json={"to": user_ids, "messages": messages},
        )
        return {
            "status": "success" if resp.is_success else "failed",
            "http_code": resp.status_code,
            "response": resp.text,
        }


async def push_message(user_id: str, messages: list) -> dict:
    """一對一推送訊息給指定用戶"""
    if not CHANNEL_ACCESS_TOKEN:
        return {"status": "error", "message": "未設定 LINE_CHANNEL_ACCESS_TOKEN"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/message/push",
            headers=_headers(),
            json={"to": user_id, "messages": messages},
        )
        return {
            "status": "success" if resp.is_success else "failed",
            "http_code": resp.status_code,
            "response": resp.text,
        }


async def get_user_profile(user_id: str) -> dict:
    """取得用戶名稱等資訊"""
    if not CHANNEL_ACCESS_TOKEN:
        return {"status": "error", "message": "未設定 LINE_CHANNEL_ACCESS_TOKEN"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API_BASE}/profile/{user_id}",
            headers=_headers(),
        )
        if resp.is_success:
            data = resp.json()
            return {
                "status": "success",
                "user_id": user_id,
                "display_name": data.get("displayName", ""),
                "picture_url": data.get("pictureUrl", ""),
                "status_message": data.get("statusMessage", ""),
            }
        return {"status": "failed", "http_code": resp.status_code, "response": resp.text}


async def get_all_followers() -> list:
    """取得所有好友的 user_id 列表"""
    if not CHANNEL_ACCESS_TOKEN:
        return []

    user_ids = []
    async with httpx.AsyncClient() as client:
        url = f"{API_BASE}/followers/ids"
        while url:
            resp = await client.get(url, headers=_headers())
            if not resp.is_success:
                break
            data = resp.json()
            user_ids.extend(data.get("userIds", []))
            url = data.get("next", "")
    return user_ids


def build_text_message(text: str) -> list:
    """建立文字訊息"""
    return [{"type": "text", "text": text}]


def build_image_message(image_url: str, preview_url: str = None) -> list:
    """建立圖片訊息"""
    return [{
        "type": "image",
        "originalContentUrl": image_url,
        "previewImageUrl": preview_url or image_url,
    }]


def build_flex_message(alt_text: str, contents: dict) -> list:
    """建立 Flex Message"""
    return [{
        "type": "flex",
        "altText": alt_text,
        "contents": contents,
    }]
