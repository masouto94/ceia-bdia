import json
from typing import Any, Dict, Optional


def get_user_preference(conn, user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content
            FROM USER_PREFERENCE
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row and row.get("content"):
            content = row["content"]
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except Exception:
                    return {}
            elif isinstance(content, dict):
                return content
    return {}


def get_user_max_results(conn, user_id: Optional[str], default: int = 10) -> int:
    if not user_id:
        return default
    pref = get_user_preference(conn, user_id)
    try:
        max_results = pref.get("result_list", {}).get("max_results")
        if max_results is not None:
            val = int(max_results)
            return val if val > 0 else default
    except (ValueError, TypeError, AttributeError):
        pass
    return default


def set_user_preference(conn, user_id: str, content: Dict[str, Any]):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO USER_PREFERENCE (user_id, content)
            VALUES (%s, %s::jsonb)
            """,
            (user_id, json.dumps(content)),
        )
