import logging
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Request, Response, HTTPException

from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import get_db
from app.services.ai import handle_incoming_message
from app.services.plans import get_current_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])


def build_twiml_response(message: str) -> str:
    """Build TwiML XML safely using ElementTree (no f-string injection)."""
    response = ET.Element("Response")
    msg = ET.SubElement(response, "Message")
    msg.text = message
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(response, encoding="unicode")


async def validate_twilio_request(request: Request) -> dict:
    form = await request.form()
    params = dict(form)

    if settings.twilio_auth_token:
        validator = RequestValidator(settings.twilio_auth_token)
        url = str(request.url)
        # Railway uses HTTPS behind a proxy
        if request.headers.get("x-forwarded-proto") == "https":
            url = url.replace("http://", "https://")
        signature = request.headers.get("X-Twilio-Signature", "")
        if not validator.validate(url, params, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params


@router.post("/sms")
async def incoming_sms(request: Request):
    try:
        params = await validate_twilio_request(request)

        body = params.get("Body", "").strip()
        from_number = params.get("From", "")
        twilio_sid = params.get("MessageSid", "")

        # Determine current plan
        plan = await get_current_plan()
        plan_id = plan["id"] if plan else settings.default_plan_id

        # Deduplicate — check if we've already processed this message
        db = await get_db()
        if twilio_sid:
            existing = await db.execute_fetchall(
                "SELECT id FROM conversations WHERE twilio_sid=?", (twilio_sid,)
            )
            if existing:
                logger.info("Duplicate message SID %s — skipping", twilio_sid)
                return Response(
                    content=build_twiml_response(""),
                    media_type="application/xml",
                )

        # Log incoming message
        await db.execute(
            """INSERT INTO conversations (plan_id, direction, channel, phone_number, content, twilio_sid)
               VALUES (?, 'inbound', 'sms', ?, ?, ?)""",
            (plan_id, from_number, body, twilio_sid or None),
        )
        await db.commit()

        # Process with Claude AI
        response_text = await handle_incoming_message(plan_id, body, from_number)

        # Log outbound response
        await db.execute(
            """INSERT INTO conversations (plan_id, direction, channel, phone_number, content, ai_interpretation)
               VALUES (?, 'outbound', 'sms', ?, ?, ?)""",
            (plan_id, from_number, response_text, body),
        )
        await db.commit()

        return Response(
            content=build_twiml_response(response_text),
            media_type="application/xml",
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error processing incoming SMS")
        # Always return valid TwiML on error
        return Response(
            content=build_twiml_response("Sorry, something went wrong. Please try again."),
            media_type="application/xml",
        )
