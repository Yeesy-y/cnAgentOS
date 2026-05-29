# Risk analysis and record service for public sentiment monitoring.
import json
import re

from app.models.db import get_connection

# (weight, category)
HIGH_WORDS = {
    # 国家危害
    "分裂": (3, "国家危害"),
    "颠覆": (3, "国家危害"),
    "间谍": (3, "国家危害"),
    "叛国": (3, "国家危害"),
    "恐怖主义": (3, "国家危害"),
    "邪教": (3, "国家危害"),
    "反华": (3, "国家危害"),
    "卖国": (3, "国家危害"),
    # 民众风波
    "煽动": (3, "民众风波"),
    "聚众": (3, "民众风波"),
    "暴动": (3, "民众风波"),
    "骚乱": (3, "民众风波"),
    "冲击": (2, "民众风波"),
    "打砸抢": (3, "民众风波"),
    # 道德违规
    "色情": (3, "道德违规"),
    "淫秽": (3, "道德违规"),
    "卖淫": (3, "道德违规"),
    # 法律红线
    "违法": (3, "法律红线"),
    "犯罪": (3, "法律红线"),
    "诈骗": (3, "法律红线"),
    "毒品": (3, "法律红线"),
    "赌博": (3, "法律红线"),
    "洗钱": (3, "法律红线"),
    "走私": (3, "法律红线"),
    "绑架": (3, "法律红线"),
    "暴力": (3, "法律红线"),
    "泄密": (3, "法律红线"),
    "攻击": (2, "法律红线"),
    "极端": (3, "法律红线"),
    "危害": (2, "法律红线"),
}

MEDIUM_WORDS = {
    "敏感": (2, "国家危害"),
    "争议": (1, "民众风波"),
    "谣言": (2, "民众风波"),
    "造谣": (2, "道德违规"),
    "欺骗": (2, "道德违规"),
    "负面": (1, "民众风波"),
    "投诉": (2, "民众风波"),
    "纠纷": (2, "民众风波"),
    "风险": (2, "法律红线"),
    "异常": (2, "法律红线"),
    "预警": (2, "法律红线"),
    "舆情": (1, "民众风波"),
    "游行": (2, "民众风波"),
    "示威": (2, "民众风波"),
    "围堵": (2, "民众风波"),
}


class RiskAnalyzer:
    @classmethod
    def analyze(cls, text):
        text = text or ""
        hits = []
        score = 1

        for word, (weight, category) in HIGH_WORDS.items():
            count = text.count(word)
            if count:
                score += count * weight
                hits.append({"keyword": word, "severity": "high", "count": count, "category": category})

        for word, (weight, category) in MEDIUM_WORDS.items():
            count = text.count(word)
            if count:
                score += count * weight
                hits.append({"keyword": word, "severity": "medium", "count": count, "category": category})

        if re.search(r"(?:http|www\.|\.com|\.cn)", text, re.I):
            score += 1
            hits.append({"keyword": "外链", "severity": "medium", "count": 1, "category": "法律红线"})

        score = max(1, min(score, 10))
        if score >= 8 or any(hit["severity"] == "high" for hit in hits):
            level = "high"
        elif score >= 5:
            level = "medium"
        else:
            level = "low"

        recommendations = {
            "high": ["立即人工复核", "保留上下文证据", "必要时暂停传播或回复"],
            "medium": ["持续跟踪相关话题", "补充事实核查", "引导用户使用规范表达"],
            "low": ["保持常规监测", "纳入趋势统计"],
        }[level]

        keyword_total = sum(hit["count"] for hit in hits)

        return {
            "risk_level": level,
            "risk_score": score,
            "keyword_warnings": hits,
            "warning_count": len(hits),
            "keyword_total": keyword_total,
            "analysis": cls._analysis_text(level, score, hits),
            "recommendations": recommendations,
        }

    @staticmethod
    def risk_level(text):
        return RiskAnalyzer.analyze(text)["risk_level"]

    @staticmethod
    def _analysis_text(level, score, hits):
        level_text = {"high": "高风险", "medium": "中风险", "low": "低风险"}[level]
        if hits:
            words = "、".join(sorted({hit["keyword"] for hit in hits}))
            categories = "、".join(sorted({hit["category"] for hit in hits}))
            return f"系统判定为{level_text}，风险分数 {score}/10。命中风险线索：{words}。涉及类别：{categories}。"
        return f"系统判定为{level_text}，风险分数 {score}/10。未命中明显风险词，建议保持常规监测。"


class RiskRecordRepository:
    @staticmethod
    def save_if_high(conn, username, user_id, source_type, source_name, ref_id, content, risk):
        if risk["risk_level"] != "high":
            return
        keywords_json = json.dumps(risk["keyword_warnings"], ensure_ascii=False)
        preview = (content or "").strip().replace("\n", " ")[:200]
        conn.execute(
            """
            INSERT INTO risk_records(
                username, user_id, risk_level, source_type, source_name,
                risk_keywords, keyword_count, risk_score, content_preview, ref_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_type, ref_id) DO UPDATE SET
                username=excluded.username,
                user_id=excluded.user_id,
                risk_level=excluded.risk_level,
                source_name=excluded.source_name,
                risk_keywords=excluded.risk_keywords,
                keyword_count=excluded.keyword_count,
                risk_score=excluded.risk_score,
                content_preview=excluded.content_preview,
                create_at=datetime('now')
            """,
            (
                username or "未知用户",
                int(user_id or 0),
                risk["risk_level"],
                source_type,
                source_name,
                keywords_json,
                risk["keyword_total"],
                risk["risk_score"],
                preview,
                int(ref_id or 0),
            ),
        )

    @staticmethod
    def user_stats(conn, risk_level=None):
        sql = """
            SELECT username,
                   risk_level,
                   SUM(keyword_count) AS keyword_total,
                   COUNT(*) AS event_count,
                   MAX(create_at) AS last_detected
            FROM risk_records
        """
        params = ()
        if risk_level:
            sql += " WHERE risk_level=?"
            params = (risk_level,)
        sql += " GROUP BY username, risk_level ORDER BY keyword_total DESC, event_count DESC LIMIT 100"
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "username": row["username"],
                "risk_level": row["risk_level"],
                "keyword_total": int(row["keyword_total"] or 0),
                "event_count": int(row["event_count"] or 0),
                "last_detected": row["last_detected"] or "",
            }
            for row in rows
        ]

    @staticmethod
    def recent_records(conn, limit=50):
        rows = conn.execute(
            """
            SELECT id, username, risk_level, source_type, source_name,
                   keyword_count, risk_score, content_preview, create_at
            FROM risk_records
            ORDER BY create_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


class ChatDataCollector:
    """Collect historical chat data from 智能问数 and 智能聊天 subsystems."""

    QA_SOURCE = "智能问数"
    IM_SOURCES = ("用户私聊", "数字员工私聊", "群聊")

    @classmethod
    def fetch_qa_messages(cls, conn, limit=60):
        try:
            rows = conn.execute(
                """
                SELECT cm.id, cm.content, cm.create_at, cm.role,
                       cc.title AS conversation_title, u.id AS user_id, u.username AS sender
                FROM chat_messages cm
                LEFT JOIN chat_conversations cc ON cm.conversation_id=cc.id
                LEFT JOIN users u ON cc.user_id=u.id
                ORDER BY cm.create_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "source": cls.QA_SOURCE,
                    "source_type": "qa_chat",
                    "sender": row["sender"] or "用户",
                    "user_id": row["user_id"] or 0,
                    "conversation_title": row["conversation_title"] or "",
                    "content": row["content"] or "",
                    "create_at": row["create_at"] or "",
                    "role": row["role"] or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    @classmethod
    def fetch_im_messages(cls, conn, limit=60):
        rows = []
        rows.extend(cls._private_messages(conn, limit // 3 + 1))
        rows.extend(cls._employee_messages(conn, limit // 3 + 1))
        rows.extend(cls._group_messages(conn, limit // 3 + 1))
        rows.sort(key=lambda item: item.get("create_at") or "", reverse=True)
        return rows[:limit]

    @classmethod
    def fetch_all(cls, conn, qa_limit=40, im_limit=40):
        qa = cls.fetch_qa_messages(conn, qa_limit)
        im = cls.fetch_im_messages(conn, im_limit)
        return qa, im

    @classmethod
    def _private_messages(cls, conn, limit):
        try:
            rows = conn.execute(
                """
                SELECT pm.id, pm.content, pm.created_at AS create_at,
                       su.id AS user_id, su.username AS sender, ru.username AS receiver
                FROM private_messages pm
                LEFT JOIN users su ON su.id=pm.sender_id
                LEFT JOIN users ru ON ru.id=pm.receiver_id
                ORDER BY pm.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "source": "用户私聊",
                    "source_type": "im_private",
                    "sender": row["sender"] or "用户",
                    "user_id": row["user_id"] or 0,
                    "conversation_title": f"私聊：{row['sender'] or ''} -> {row['receiver'] or ''}",
                    "content": row["content"] or "",
                    "create_at": row["create_at"] or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    @classmethod
    def _employee_messages(cls, conn, limit):
        try:
            rows = conn.execute(
                """
                SELECT epm.id, epm.content, epm.created_at AS create_at, epm.sender_type,
                       u.id AS user_id, u.username, de.employee_name
                FROM employee_private_messages epm
                LEFT JOIN users u ON u.id=epm.user_id
                LEFT JOIN digital_employees de ON de.id=epm.employee_id
                ORDER BY epm.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "source": "数字员工私聊",
                    "source_type": "im_employee",
                    "sender": row["username"] if row["sender_type"] == "user" else row["employee_name"],
                    "user_id": row["user_id"] or 0,
                    "conversation_title": f"{row['username'] or ''} / {row['employee_name'] or ''}",
                    "content": row["content"] or "",
                    "create_at": row["create_at"] or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    @classmethod
    def _group_messages(cls, conn, limit):
        try:
            rows = conn.execute(
                """
                SELECT gm.id, gm.content, gm.created_at AS create_at, gm.sender_type,
                       g.name AS group_name, u.id AS user_id, u.username, de.employee_name
                FROM group_messages gm
                LEFT JOIN groups g ON g.id=gm.group_id
                LEFT JOIN users u ON u.id=gm.sender_id AND gm.sender_type='user'
                LEFT JOIN digital_employees de ON de.id=gm.sender_id AND gm.sender_type='employee'
                ORDER BY gm.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "source": "群聊",
                    "source_type": "im_group",
                    "sender": row["username"] if row["sender_type"] == "user" else row["employee_name"],
                    "user_id": row["user_id"] or 0 if row["sender_type"] == "user" else 0,
                    "conversation_title": row["group_name"] or "",
                    "content": row["content"] or "",
                    "create_at": row["create_at"] or "",
                }
                for row in rows
            ]
        except Exception:
            return []

    @classmethod
    def count_by_date(cls, conn, date_text):
        total = 0
        total += cls._count_table(conn, "chat_messages", "create_at", date_text)
        for table in ("private_messages", "employee_private_messages", "group_messages"):
            total += cls._count_table(conn, table, "created_at", date_text)
        return total

    @classmethod
    def count_by_hour(cls, conn, hour_text):
        total = 0
        total += cls._count_hour(conn, "chat_messages", "create_at", hour_text)
        for table in ("private_messages", "employee_private_messages", "group_messages"):
            total += cls._count_hour(conn, table, "created_at", hour_text)
        return total

    @staticmethod
    def _count_table(conn, table, col, date_text):
        try:
            row = conn.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE DATE({col})=?",
                (date_text,),
            ).fetchone()
            return int(row["total"] or 0) if row else 0
        except Exception:
            return 0

    @staticmethod
    def _count_hour(conn, table, col, hour_text):
        try:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS total FROM {table}
                WHERE {col} >= datetime('now', '-24 hours')
                  AND strftime('%H', {col})=?
                """,
                (hour_text,),
            ).fetchone()
            return int(row["total"] or 0) if row else 0
        except Exception:
            return 0

    @classmethod
    def source_counts(cls, conn):
        counts = {}
        try:
            row = conn.execute("SELECT COUNT(*) AS total FROM chat_messages").fetchone()
            counts[cls.QA_SOURCE] = int(row["total"] or 0) if row else 0
        except Exception:
            counts[cls.QA_SOURCE] = 0
        for label, table in (
            ("用户私聊", "private_messages"),
            ("数字员工私聊", "employee_private_messages"),
            ("群聊", "group_messages"),
        ):
            try:
                row = conn.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()
                counts[label] = int(row["total"] or 0) if row else 0
            except Exception:
                counts[label] = 0
        return counts

    @classmethod
    def recent_contents(cls, conn, limit=200):
        items = []
        items.extend(cls.fetch_qa_messages(conn, limit // 2))
        items.extend(cls.fetch_im_messages(conn, limit // 2))
        return items[:limit]
