# Digital dashboard controller.
import json
import re
from collections import Counter
from datetime import datetime, timedelta

import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection
from app.models.risk_service import ChatDataCollector, RiskAnalyzer


def _row_value(row, key, default=0):
    try:
        value = row[key]
    except Exception:
        value = default
    return default if value is None else value


def _fetch_count(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return int(_row_value(row, "total", 0)) if row else 0


class DashboardIndexHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        username = self.current_user
        if isinstance(username, dict):
            username = username.get("username", "Admin")
        elif not isinstance(username, str):
            username = "Admin"

        self.render(
            "admin_dashboard.html",
            title="数智大屏 - AI 智能瞭望系统",
            username=username,
            active_menu="dashboard",
        )


class DashboardDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        data_type = self.get_argument("type", "overview")

        try:
            with get_connection() as conn:
                if data_type == "overview":
                    result = self._overview(conn)
                elif data_type == "keywords":
                    result = self._keywords(conn)
                elif data_type == "chart_stats":
                    result = self._chart_stats(conn)
                elif data_type == "risk":
                    result = self._risk_stats(conn)
                else:
                    result = {"success": False, "message": "未知的数据类型"}
        except Exception as exc:
            result = {"success": False, "message": str(exc)}

        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(result, ensure_ascii=False, default=str))

    def _overview(self, conn):
        today = datetime.now().strftime("%Y-%m-%d")
        watch_total = _fetch_count(conn, "SELECT COUNT(*) AS total FROM watch_data")
        keyword_total = _fetch_count(conn, "SELECT COUNT(DISTINCT keyword) AS total FROM watch_data")
        today_watch = _fetch_count(
            conn,
            "SELECT COUNT(*) AS total FROM watch_data WHERE DATE(create_at)=?",
            (today,),
        )
        source_total = _fetch_count(conn, "SELECT COUNT(*) AS total FROM watch_sources")
        chat_counts = ChatDataCollector.source_counts(conn)
        chat_total = sum(chat_counts.values())
        qa_total = chat_counts.get(ChatDataCollector.QA_SOURCE, 0)
        im_total = chat_total - qa_total

        trend_dates = []
        trend_watch = []
        trend_chat = []
        trend_values = []
        for i in range(6, -1, -1):
            day = datetime.now() - timedelta(days=i)
            date_text = day.strftime("%Y-%m-%d")
            trend_dates.append(day.strftime("%m-%d"))
            watch_count = _fetch_count(
                conn,
                "SELECT COUNT(*) AS total FROM watch_data WHERE DATE(create_at)=?",
                (date_text,),
            )
            chat_count = ChatDataCollector.count_by_date(conn, date_text)
            trend_watch.append(watch_count)
            trend_chat.append(chat_count)
            trend_values.append(watch_count + chat_count)

        return {
            "success": True,
            "data": {
                "total_records": watch_total + chat_total,
                "watch_total": watch_total,
                "chat_total": chat_total,
                "qa_total": qa_total,
                "im_total": im_total,
                "keyword_total": keyword_total,
                "today_records": today_watch + ChatDataCollector.count_by_date(conn, today),
                "today_watch": today_watch,
                "today_chat": ChatDataCollector.count_by_date(conn, today),
                "source_total": source_total + len([v for v in chat_counts.values() if v > 0]),
                "trend_dates": trend_dates,
                "trend_values": trend_values,
                "trend_watch": trend_watch,
                "trend_chat": trend_chat,
            },
        }

    def _keywords(self, conn):
        watch_rows = conn.execute(
            """
            SELECT keyword, COUNT(*) AS count, MAX(create_at) AS last_collect
            FROM watch_data
            WHERE COALESCE(keyword, '') <> ''
            GROUP BY keyword
            ORDER BY count DESC, last_collect DESC
            LIMIT 40
            """
        ).fetchall()

        counter = Counter()
        for row in watch_rows:
            counter[row["keyword"]] += int(row["count"] or 0)

        chat_items = ChatDataCollector.recent_contents(conn, limit=150)
        for item in chat_items:
            for word in self._extract_terms(item.get("content", "")):
                counter[word] += 1

        data = [
            {"name": name, "value": count, "last_collect": ""}
            for name, count in counter.most_common(60)
        ]
        return {"success": True, "data": data}

    def _chart_stats(self, conn):
        days = []
        watch_values = []
        chat_values = []
        combined_values = []
        for i in range(6, -1, -1):
            day = datetime.now() - timedelta(days=i)
            date_text = day.strftime("%Y-%m-%d")
            days.append(day.strftime("%m-%d"))
            watch_count = _fetch_count(
                conn,
                "SELECT COUNT(*) AS total FROM watch_data WHERE DATE(create_at)=?",
                (date_text,),
            )
            chat_count = ChatDataCollector.count_by_date(conn, date_text)
            watch_values.append(watch_count)
            chat_values.append(chat_count)
            combined_values.append(watch_count + chat_count)

        source_names = []
        source_counts = []
        source_rows = conn.execute(
            """
            SELECT COALESCE(ws.source_name, '未分类') AS source_name, COUNT(wd.id) AS count
            FROM watch_data wd
            LEFT JOIN watch_sources ws ON ws.id=wd.source_id
            GROUP BY wd.source_id, ws.source_name
            ORDER BY count DESC
            LIMIT 6
            """
        ).fetchall()
        for row in source_rows:
            source_names.append(row["source_name"])
            source_counts.append(int(row["count"] or 0))

        for name, count in ChatDataCollector.source_counts(conn).items():
            if count > 0:
                source_names.append(name)
                source_counts.append(count)

        hours = [f"{h:02d}" for h in range(24)]
        hour_values = []
        for hour in hours:
            watch_hour = _fetch_count(
                conn,
                """
                SELECT COUNT(*) AS total FROM watch_data
                WHERE create_at >= datetime('now', '-24 hours')
                  AND strftime('%H', create_at)=?
                """,
                (hour,),
            )
            chat_hour = ChatDataCollector.count_by_hour(conn, hour)
            hour_values.append(watch_hour + chat_hour)

        type_distribution = self._content_distribution(conn)

        return {
            "success": True,
            "data": {
                "day_labels": days,
                "day_values": combined_values,
                "day_watch_values": watch_values,
                "day_chat_values": chat_values,
                "source_names": source_names,
                "source_counts": source_counts,
                "hour_labels": hours,
                "hour_values": hour_values,
                "type_distribution": type_distribution,
            },
        }

    def _risk_stats(self, conn):
        counts = {"high": 0, "medium": 0, "low": 0}

        watch_rows = conn.execute(
            """
            SELECT title, content, keyword
            FROM watch_data
            ORDER BY create_at DESC
            LIMIT 80
            """
        ).fetchall()
        for row in watch_rows:
            text = " ".join([row["keyword"] or "", row["title"] or "", row["content"] or ""])
            counts[RiskAnalyzer.risk_level(text)] += 1

        chat_items = ChatDataCollector.recent_contents(conn, limit=80)
        for item in chat_items:
            if item.get("role") == "assistant":
                continue
            counts[RiskAnalyzer.risk_level(item.get("content", ""))] += 1

        return {"success": True, "data": counts}

    def _content_distribution(self, conn):
        buckets = {
            "政策资讯": ["政策", "公告", "通知", "政府", "部门"],
            "校园动态": ["学校", "学院", "学生", "老师", "校园"],
            "社会热点": ["热点", "舆情", "事件", "社会", "公众"],
            "行业信息": ["行业", "市场", "企业", "技术", "产业"],
            "智能问数": ["查询", "数据", "统计", "分析", "报表"],
            "智能聊天": ["聊天", "消息", "回复", "对话", "群聊"],
        }
        counts = {name: 0 for name in buckets}
        counts["其他"] = 0

        watch_rows = conn.execute(
            """
            SELECT title, content, keyword
            FROM watch_data
            ORDER BY create_at DESC
            LIMIT 200
            """
        ).fetchall()
        for row in watch_rows:
            text = " ".join([row["keyword"] or "", row["title"] or "", row["content"] or ""])
            self._bucket_text(text, buckets, counts)

        chat_items = ChatDataCollector.recent_contents(conn, limit=100)
        for item in chat_items:
            source = item.get("source", "")
            if source == ChatDataCollector.QA_SOURCE:
                counts["智能问数"] += 1
            elif source in ChatDataCollector.IM_SOURCES:
                counts["智能聊天"] += 1
            else:
                self._bucket_text(item.get("content", ""), buckets, counts)

        return [{"type": key, "value": value} for key, value in counts.items() if value > 0]

    def _bucket_text(self, text, buckets, counts):
        matched = False
        for name, words in buckets.items():
            if name in ("智能问数", "智能聊天"):
                continue
            if any(word in text for word in words):
                counts[name] += 1
                matched = True
                break
        if not matched:
            counts["其他"] += 1

    def _extract_terms(self, text):
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text or "")
        parts = [part.strip() for part in text.split() if len(part.strip()) >= 2]
        return parts[:8]
