from copy import deepcopy
import json
from typing import Any

class LlmFeedbackError(Exception):
    pass


async def enrich_analysis_with_llm_feedback(analysis: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.llm_feedback_enabled or not settings.openai_api_key:
        return _ensure_rule_sources(analysis)

    payload = _feedback_payload(analysis)
    if not payload["items"]:
        return _ensure_rule_sources(analysis)

    feedback = await _request_openai_feedback(settings=settings, payload=payload)
    return _merge_llm_feedback(analysis=analysis, feedback=feedback)


def _ensure_rule_sources(analysis: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(analysis)
    for evidence in enriched.get("evidence", []):
        context = evidence.get("context")
        if not isinstance(context, dict):
            continue
        context["insights"] = [
            {**insight, "source": insight.get("source") or "rules"}
            for insight in context.get("insights", [])
            if isinstance(insight, dict)
        ]
    return enriched


def _feedback_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for evidence_index, evidence in enumerate(analysis.get("evidence", [])):
        context = evidence.get("context")
        if not isinstance(context, dict):
            continue

        items.append(
            {
                "evidence_index": evidence_index,
                "evidence_type": evidence.get("type"),
                "minute": evidence.get("minute"),
                "title": evidence.get("title"),
                "description": evidence.get("description"),
                "confidence": evidence.get("confidence"),
                "summary": context.get("summary"),
                "rule_insights": context.get("insights", []),
                "events": [_compact_event(event) for event in context.get("events", [])[:18]],
                "snapshots": [_compact_snapshot(snapshot) for snapshot in _select_snapshots(context)],
            }
        )

    return {
        "player": analysis.get("player"),
        "scores": analysis.get("scores"),
        "items": items,
    }


async def _request_openai_feedback(settings: Any, payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    body = {
        "model": settings.openai_model,
        "instructions": (
            "너는 League of Legends 복기 코치다. 입력된 Riot API 이벤트와 분 단위 타임라인 프레임만 근거로 "
            "한국어 피드백을 작성한다. 보이지 않는 시야, 의도, 콜, 보이스, 1초 단위 위치는 추측하지 않는다. "
            "좌표는 실제 Riot timeline frame이며 보간된 값이 아니므로, 위치 평가는 '가능성이 높음', "
            "'가까움', '확인 필요'처럼 단정하지 않는 표현을 쓴다. 시야 장악만 반복하지 말고, 로그가 "
            "뒷받침할 때 한타, 픽오프, 무교전 오브젝트, 오브젝트 전환, 리드 활용 관점 중 가장 중요한 "
            "해석을 고른다. 각 evidence마다 최대 2개의 insight만 반환한다. JSON만 반환한다. "
            "형식: {\"items\":[{\"evidence_index\":0,\"insights\":[{\"tone\":\"risk|positive|info\","
            "\"title\":\"짧은 제목\",\"description\":\"근거 기반 설명\"}]}]}"
        ),
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 1200,
        "store": False,
    }
    url = f"{settings.openai_base_url.rstrip('/')}/responses"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LlmFeedbackError(f"OpenAI request failed with HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise LlmFeedbackError("OpenAI request failed") from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise LlmFeedbackError("OpenAI response was not valid JSON") from exc

    output_text = _extract_output_text(response_payload)
    if not output_text:
        raise LlmFeedbackError("OpenAI response did not include output_text")

    try:
        feedback = json.loads(_strip_json_fence(output_text))
    except ValueError as exc:
        raise LlmFeedbackError("OpenAI feedback was not valid JSON") from exc

    if not isinstance(feedback, dict):
        raise LlmFeedbackError("OpenAI feedback JSON must be an object")
    return feedback


def _merge_llm_feedback(analysis: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    enriched = _ensure_rule_sources(analysis)
    items = feedback.get("items")
    if not isinstance(items, list):
        return enriched

    feedback_by_index = {
        evidence_index: item
        for item in items
        for evidence_index in [_optional_int(item.get("evidence_index")) if isinstance(item, dict) else None]
        if evidence_index is not None
    }

    for evidence_index, evidence in enumerate(enriched.get("evidence", [])):
        context = evidence.get("context")
        item = feedback_by_index.get(evidence_index)
        if not isinstance(context, dict) or not isinstance(item, dict):
            continue

        llm_insights = _sanitize_llm_insights(item.get("insights"))
        if not llm_insights:
            continue

        rule_insights = [
            {**insight, "source": insight.get("source") or "rules"}
            for insight in context.get("insights", [])
            if isinstance(insight, dict)
        ]
        context["insights"] = (llm_insights + rule_insights)[:2]

    return enriched


def _sanitize_llm_insights(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    insights: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        tone = item.get("tone")
        title = item.get("title")
        description = item.get("description")
        if tone not in {"risk", "positive", "info"} or not isinstance(title, str) or not isinstance(description, str):
            continue
        title = title.strip()
        description = description.strip()
        if not title or not description:
            continue
        insights.append(
            {
                "tone": tone,
                "title": title[:80],
                "description": description[:260],
                "source": "llm",
            }
        )
        if len(insights) >= 2:
            break

    return insights


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "time_seconds": round((event.get("timestamp_ms") or 0) / 1000),
        "type": event.get("type"),
        "title": event.get("title"),
        "description": event.get("description"),
        "team": event.get("team"),
        "victim_team": event.get("victim_team"),
        "position": _position(event),
    }


def _compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "time_seconds": round((snapshot.get("timestamp_ms") or 0) / 1000),
        "offset_seconds": snapshot.get("offset_seconds"),
        "objective_state": snapshot.get("objective_state"),
        "participants": [
            {
                "team": participant.get("team"),
                "champion": participant.get("champion_name"),
                "is_player": participant.get("is_player"),
                "position": _position(participant),
            }
            for participant in snapshot.get("participants", [])
            if isinstance(participant, dict)
        ],
    }


def _select_snapshots(context: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = [snapshot for snapshot in context.get("snapshots", []) if isinstance(snapshot, dict)]
    if len(snapshots) <= 3:
        return snapshots

    anchor_timestamp_ms = context.get("anchor_timestamp_ms") or 0
    anchor_snapshot = min(
        snapshots,
        key=lambda snapshot: abs((snapshot.get("timestamp_ms") or 0) - anchor_timestamp_ms),
    )
    selected = [snapshots[0], anchor_snapshot, snapshots[-1]]
    deduped: list[dict[str, Any]] = []
    seen: set[int] = set()
    for snapshot in selected:
        timestamp_ms = snapshot.get("timestamp_ms")
        if timestamp_ms in seen:
            continue
        seen.add(timestamp_ms)
        deduped.append(snapshot)
    return deduped


def _position(item: dict[str, Any]) -> dict[str, int | None]:
    return {
        "x": item.get("x") if "x" in item else item.get("position_x"),
        "y": item.get("y") if "y" in item else item.get("position_y"),
    }


def _extract_output_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for output_item in response_payload.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content in output_item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if content.get("type") in {"output_text", "text"} and isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
