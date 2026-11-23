import ipaddress
import socket
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database.storage import get_connection
from backend.permissions import require_active_user

from datetime import datetime, timezone


router = APIRouter(prefix="/websites", tags=["User Websites"])


class WebsiteRegistration(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    url: str = Field(min_length=8, max_length=2048)
    ownership_confirmed: bool


def validate_website_url(url):
    try:
        parsed = urlsplit(url.strip())

        if parsed.scheme not in ("http", "https"):
            raise ValueError()

        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()

        if parsed.port and not (1 <= parsed.port <= 65535):
            raise ValueError()

        host = parsed.hostname.rstrip(".").lower()

        if (
            host == "localhost"
            or host.endswith(".localhost")
            or host.endswith(".local")
            or host.endswith(".internal")
        ):
            raise ValueError()

        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                raise ValueError()
        except ValueError:
            try:
                results = socket.getaddrinfo(host, None)
                for result in results:
                    address = ipaddress.ip_address(result[4][0])
                    if not address.is_global:
                        raise ValueError()
            except socket.gaierror:
                # Undeployed or not-yet-resolvable websites remain pending.
                pass

        return url.strip()

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid public HTTP or HTTPS website URL.",
        )


@router.post("", status_code=201)
def register_website(
    data: WebsiteRegistration,
    user=Depends(require_active_user),
):
    if not data.ownership_confirmed:
        raise HTTPException(
            status_code=400,
            detail="You must confirm that you own or are authorized to monitor this website.",
        )

    url = validate_website_url(data.url)

    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO monitored_websites (
                user_id, name, url, ownership_confirmed,
                monitoring_status, enabled, created_at
            )
            VALUES (?, ?, ?, 1, 'pending', 1, ?)
        """, (user["id"], data.name.strip(), url, now))

        website_id = cursor.lastrowid

    return {
        "message": "Website registered successfully.",
        "website": {
            "id": website_id,
            "name": data.name.strip(),
            "url": url,
            "monitoring_status": "pending",
        },
    }


@router.get("")
def list_websites(user=Depends(require_active_user)):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, name, url, monitoring_status, enabled, created_at
            FROM monitored_websites
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user["id"],)).fetchall()

    return {
        "count": len(rows),
        "websites": [dict(row) for row in rows],
    }


@router.delete("/{website_id}")
def delete_website(
    website_id: int,
    user=Depends(require_active_user),
):
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM monitored_websites
            WHERE id = ? AND user_id = ?
        """, (website_id, user["id"]))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Website not found.",
            )

    return {"message": "Website deleted successfully."}
