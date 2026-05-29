# Public sentiment and risk warning controller.
import json

import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection
from app.models.risk_service import (
    ChatDataCollector,
    RiskAnalyzer,
    RiskRecordRepository,
)


class PublicSentimentIndexHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        username = self.current_user
        if isinstance(username, dict):
            username = username.get("username", "Admin")
        self.render(
            "admin_public_sentiment.html",
            title="智能舆情分析 - AI 智能瞭望系统",
            username=username,
            active_menu="public_sentiment",
        )


class SentimentAnalysisHandler(AdminBaseHandler):
    """Analyze free-form text from the manual risk panel."""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        text_content = self.get_argument("content", "").strip()
        if not text_content:
            self._json({"success": False, "message": "请输入待分析的文本内容"})
            return

        result = RiskAnalyzer.analyze(text_content)
        result["original_text"] = text_content
        self._json({"success": True, "data": result})

    def _json(self, payload):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(payload, ensure_ascii=False))


class WatchDataSentimentHandler(AdminBaseHandler):
    """Analyze data collected by the watch subsystem."""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT wd.id, wd.keyword, wd.title, wd.content, wd.url, wd.create_at,
                           COALESCE(ws.source_name, '未分类') AS source_name
                    FROM watch_data wd
                    LEFT JOIN watch_sources ws ON ws.id=wd.source_id
                    ORDER BY wd.create_at DESC
                    LIMIT 50
                    """
                ).fetchall()

                data = []
                for row in rows:
                    text = " ".join([row["keyword"] or "", row["title"] or "", row["content"] or ""])
                    risk = RiskAnalyzer.analyze(text)
                    RiskRecordRepository.save_if_high(
                        conn,
                        username="数据仓库",
                        user_id=0,
                        source_type="watch_data",
                        source_name=row["source_name"] or "瞭望数据",
                        ref_id=row["id"],
                        content=text,
                        risk=risk,
                    )
                    data.append(self._build_item(row, risk))

                conn.commit()
            self._json({"success": True, "data": data, "summary": self._summary(data)})
        except Exception as exc:
            self._json({"success": False, "message": str(exc)})

    def _build_item(self, row, risk):
        return {
            "id": row["id"],
            "keyword": row["keyword"] or "",
            "title": row["title"] or "",
            "source_name": row["source_name"] or "",
            "url": row["url"] or "",
            "create_at": row["create_at"] or "",
            "risk_level": risk["risk_level"],
            "risk_score": risk["risk_score"],
            "warning_count": risk["warning_count"],
            "keyword_total": risk["keyword_total"],
            "analysis": risk["analysis"],
        }

    def _summary(self, data):
        return {
            "high": sum(1 for item in data if item["risk_level"] == "high"),
            "medium": sum(1 for item in data if item["risk_level"] == "medium"),
            "low": sum(1 for item in data if item["risk_level"] == "low"),
        }

    def _json(self, payload):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(payload, ensure_ascii=False, default=str))


class ChatDataSentimentHandler(AdminBaseHandler):
    """Analyze 智能问数 and 智能聊天 historical records."""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        try:
            with get_connection() as conn:
                qa_rows, im_rows = ChatDataCollector.fetch_all(conn, qa_limit=50, im_limit=50)
                qa_data = self._analyze_rows(conn, qa_rows)
                im_data = self._analyze_rows(conn, im_rows)
                conn.commit()

            all_data = qa_data + im_data
            all_data.sort(key=lambda item: item.get("create_at") or "", reverse=True)
            self._json(
                {
                    "success": True,
                    "data": all_data,
                    "qa_data": qa_data,
                    "im_data": im_data,
                    "summary": self._summary(all_data),
                    "qa_summary": self._summary(qa_data),
                    "im_summary": self._summary(im_data),
                }
            )
        except Exception as exc:
            self._json({"success": False, "message": str(exc)})

    def _analyze_rows(self, conn, rows):
        data = []
        for item in rows:
            risk = RiskAnalyzer.analyze(item.get("content", ""))
            is_user_content = (
                item.get("role") == "user"
                or item.get("source_type") in ("im_private", "im_group")
                or (item.get("source_type") == "im_employee" and item.get("user_id"))
            )
            if risk["risk_level"] == "high" and is_user_content:
                RiskRecordRepository.save_if_high(
                    conn,
                    username=item.get("sender", "未知用户"),
                    user_id=item.get("user_id", 0),
                    source_type=item.get("source_type", "chat"),
                    source_name=item.get("source", ""),
                    ref_id=item.get("id"),
                    content=item.get("content", ""),
                    risk=risk,
                )
            data.append(
                {
                    "id": item.get("id"),
                    "source": item.get("source"),
                    "sender": item.get("sender", ""),
                    "conversation_title": item.get("conversation_title", ""),
                    "content_preview": self._preview(item.get("content", "")),
                    "create_at": item.get("create_at", ""),
                    "risk_level": risk["risk_level"],
                    "risk_score": risk["risk_score"],
                    "warning_count": risk["warning_count"],
                    "keyword_total": risk["keyword_total"],
                    "keyword_warnings": risk["keyword_warnings"],
                    "analysis": risk["analysis"],
                }
            )
        return data

    def _summary(self, data):
        return {
            "high": sum(1 for item in data if item["risk_level"] == "high"),
            "medium": sum(1 for item in data if item["risk_level"] == "medium"),
            "low": sum(1 for item in data if item["risk_level"] == "low"),
        }

    def _preview(self, text):
        text = (text or "").strip().replace("\n", " ")
        return text[:100] + ("..." if len(text) > 100 else "")

    def _json(self, payload):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(payload, ensure_ascii=False, default=str))


class RiskStatsHandler(AdminBaseHandler):
    """Return aggregated high-risk user statistics and recent records."""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        try:
            with get_connection() as conn:
                high_stats = RiskRecordRepository.user_stats(conn, risk_level="high")
                all_stats = RiskRecordRepository.user_stats(conn)
                recent = RiskRecordRepository.recent_records(conn, limit=30)
            self._json(
                {
                    "success": True,
                    "high_risk_users": high_stats,
                    "all_risk_users": all_stats,
                    "recent_records": recent,
                }
            )
        except Exception as exc:
            self._json({"success": False, "message": str(exc)})

    def _json(self, payload):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(payload, ensure_ascii=False, default=str))
