import tornado.web
import json
import requests
import re
from urllib.parse import quote
from app.controllers.admin_base import AdminBaseHandler
from app.models.watch_service import WatchSourceRepository, WatchDataRepository

ABNORMAL_PAGE_MARKERS = ["问题反馈", "安全验证", "请输入验证码", "访问受限", "百度安全验证", "network-error"]
DEFAULT_SOURCE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
}


def is_abnormal_page(text):
    return any(marker in (text or "") for marker in ABNORMAL_PAGE_MARKERS)


def render_with_context(value, context):
    if value is None:
        return value
    if isinstance(value, str):
        result = value
        for key, val in context.items():
            result = result.replace("{" + key + "}", str(val))
        return result
    if isinstance(value, dict):
        return {k: render_with_context(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_with_context(v, context) for v in value]
    return value


def decode_html_response(response, keyword_raw=""):
    content = response.content or b""
    content_type = response.headers.get("Content-Type", "").lower()
    encodings = []
    charset_match = re.search(r"charset=([\w\-]+)", content_type)
    if charset_match:
        encodings.append(charset_match.group(1).strip())
    if response.encoding:
        encodings.append(response.encoding)
    if getattr(response, "apparent_encoding", None):
        encodings.append(response.apparent_encoding)
    encodings.extend(["utf-8", "gb18030", "gbk"])

    tried = set()
    best_text = ""
    best_score = -10**9
    for enc in encodings:
        if not enc:
            continue
        enc_key = enc.lower()
        if enc_key in tried:
            continue
        tried.add(enc_key)
        try:
            text = content.decode(enc, errors="ignore")
        except Exception:
            continue
        score = 0
        if keyword_raw and keyword_raw in text:
            score += 10
        if "百度" in text:
            score += 4
        if "新闻" in text:
            score += 3
        if "��" in text:
            score -= 8
        if is_abnormal_page(text):
            score -= 6
        if score > best_score:
            best_score = score
            best_text = text
    return best_text or response.text

def parse_baidu_news(html_content):
    news_items = []

    if is_abnormal_page(html_content):
        return []

    try:
        block_pattern = re.compile(r'<div[^>]*class="[^"]*(result|news-item)[^"]*"[^>]*>(.*?)</div>\s*</div>', re.DOTALL | re.IGNORECASE)
        blocks = block_pattern.findall(html_content)
        if not blocks:
            blocks = [("", html_content)]

        for _, block in blocks[:30]:
            title = ""
            url = ""
            content = ""
            publish_time = ""

            h3_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL | re.IGNORECASE)
            if h3_match:
                h3_html = h3_match.group(1)
                link_match = re.search(r'href="([^"]+)"', h3_html, re.IGNORECASE)
                if link_match:
                    url = link_match.group(1).strip()
                title_text = re.sub(r'<[^>]+>', ' ', h3_html)
                title_text = re.sub(r'\s+', ' ', title_text).strip()
                title = title_text

            if not title:
                a_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
                if a_match:
                    url = a_match.group(1).strip()
                    title_text = re.sub(r'<[^>]+>', ' ', a_match.group(2))
                    title_text = re.sub(r'\s+', ' ', title_text).strip()
                    title = title_text

            abs_match = re.search(r'<div[^>]*class="[^"]*(c-abstract|content|summary)[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL | re.IGNORECASE)
            if abs_match:
                content = re.sub(r'<[^>]+>', ' ', abs_match.group(2))
                content = re.sub(r'\s+', ' ', content).strip()

            if not content:
                p_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL | re.IGNORECASE)
                if p_match:
                    content = re.sub(r'<[^>]+>', ' ', p_match.group(1))
                    content = re.sub(r'\s+', ' ', content).strip()

            if not publish_time:
                time_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{1,2})?)', block)
                if time_match:
                    publish_time = time_match.group(1)

            if not title and content:
                title = content[:50]

            if title and len(title) >= 4:
                news_items.append({
                    "title": title[:200],
                    "url": url,
                    "content": content[:800],
                    "time": publish_time
                })

        dedup = []
        seen = set()
        for item in news_items:
            key = (item.get("title", ""), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
        news_items = dedup[:20]

    except Exception:
        pass

    if not news_items:
        try:
            pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            matches = pattern.findall(html_content)
            for url, text in matches[:20]:
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 5 and len(text) < 120 and 'http' not in text:
                    news_items.append({
                        "title": text,
                        "url": url if url.startswith('http') else "",
                        "content": "",
                        "time": ""
                    })
        except Exception:
            pass

    return news_items

class AdminWatchSourceListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		result = WatchSourceRepository.list_sources(page, 20)
		for s in result["data"]:
			if "create_at" in s and s["create_at"]:
				ca = s["create_at"]
				if len(ca) > 10:
					s["create_at"] = ca[:10] + " " + ca[11:19]
		self.render("admin_watch_source_list.html",
			title="采集源管理",
			username=self.current_user,
			active_menu="watch_source",
			sources=result["data"],
			total=result["total"],
			page=result["page"],
			page_size=result["page_size"])
	
	def post(self):
		action = self.get_body_argument("action", "")
		source_id_str = self.get_body_argument("source_id", "")
		if action == "delete" and source_id_str:
			source_id = int(source_id_str)
			WatchSourceRepository.delete_source(source_id)
		return self.redirect("/admin/watch/source/list")

class AdminWatchSourceAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin_watch_source_form.html",
			title="新增采集源",
			username=self.current_user,
			active_menu="watch_source",
			source=None,
			mode="add")
	
	def post(self):
		source_name = (self.get_body_argument("source_name", "") or "").strip()
		source_code = (self.get_body_argument("source_code", "") or "").strip()
		url_template = (self.get_body_argument("url_template", "") or "").strip()
		headers_json = self.get_body_argument("headers_json", "")
		cookie = self.get_body_argument("cookie", "")
		
		if not source_name or not source_code or not url_template:
			return self.redirect("/admin/watch/source/add")
		
		WatchSourceRepository.create_source(source_name, source_code, url_template, headers_json or None, cookie or None)
		return self.redirect("/admin/watch/source/list")

class AdminWatchSourceEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		source_id = int(self.get_argument("id", "0"))
		if not source_id:
			return self.redirect("/admin/watch/source/list")
		source = WatchSourceRepository.get_source_by_id(source_id)
		if not source:
			return self.redirect("/admin/watch/source/list")
		self.render("admin_watch_source_form.html",
			title="编辑采集源",
			username=self.current_user,
			active_menu="watch_source",
			source=dict(source),
			mode="edit")
	
	def post(self):
		source_id = int(self.get_body_argument("id", "0"))
		if not source_id:
			return self.redirect("/admin/watch/source/list")
		
		source_name = (self.get_body_argument("source_name", "") or "").strip()
		source_code = (self.get_body_argument("source_code", "") or "").strip()
		url_template = (self.get_body_argument("url_template", "") or "").strip()
		headers_json = self.get_body_argument("headers_json", "")
		cookie = self.get_body_argument("cookie", "")
		status = int(self.get_body_argument("status", "1"))
		
		WatchSourceRepository.update_source(
			source_id,
			source_name=source_name,
			source_code=source_code,
			url_template=url_template,
			headers_json=headers_json or None,
			cookie=cookie or None,
			status=status
		)
		return self.redirect("/admin/watch/source/list")

class AdminWatchCollectHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		sources = WatchSourceRepository.list_all_sources()
		self.render("admin_watch_collect.html",
			title="瞭望采集",
			username=self.current_user,
			active_menu="watch_collect",
			sources=sources)
	
	@tornado.web.authenticated
	def post(self):
		try:
			self.set_header("Content-Type", "application/json")
			
			keyword = (self.get_body_argument("keyword", "") or "").strip()
			source_ids = self.get_body_arguments("source_ids")
			count_per_page = int(self.get_body_argument("count_per_page", "10"))
			pages = int(self.get_body_argument("pages", "1"))
			
			if not keyword or not source_ids:
				self.write(json.dumps({"success": False, "message": "请输入关键词并选择采集源"}))
				return
			
			results = []
			for source_id_str in source_ids:
				source_id = int(source_id_str)
				source = WatchSourceRepository.get_source_by_id(source_id)
				if not source:
					continue
				
				for page in range(pages):
					pn = page * 10
					context = {
						"keyword": quote(keyword),
						"keyword_raw": keyword,
						"pn": pn,
						"page": page + 1
					}
					url = render_with_context(source["url_template"], context)
					
					final_result = None
					for attempt in range(3):
						try:
							headers = dict(DEFAULT_SOURCE_HEADERS)
							if source.get("headers_json"):
								try:
									custom_headers = json.loads(source["headers_json"])
									if isinstance(custom_headers, dict):
										headers.update(render_with_context(custom_headers, context))
								except:
									pass
							
							if source.get("cookie"):
								headers["Cookie"] = render_with_context(source["cookie"], context)
							
							referers = [
								url,
								f"https://www.baidu.com/s?ie=utf-8&tn=news&wd={context['keyword']}&pn={pn}",
								f"https://www.baidu.com/s?wd={context['keyword']}",
								"https://www.baidu.com/",
							]
							headers["Referer"] = referers[attempt % len(referers)]
							
							response = requests.get(url, headers=headers, timeout=30)
							response.raise_for_status()
							
							html_content = decode_html_response(response, keyword)
							
							if is_abnormal_page(html_content):
								if attempt < 2:
									continue
								final_result = {
									"source": source["source_name"],
									"page": page + 1,
									"status": "error",
									"message": "目标站点返回了异常页/验证页（已自动重试3次），本页未入库，请在采集源中补充有效 cookie / referer"
								}
								break
							
							news_items = parse_baidu_news(html_content)
							
							if not news_items:
								if attempt < 2:
									continue
								final_result = {
									"source": source["source_name"],
									"page": page + 1,
									"status": "error",
									"message": "未解析到有效新闻结果（已自动重试3次），本页未入库"
								}
								break
							
							for item in news_items:
								content_text = (item.get("content", "") or "").strip()
								if not content_text:
									plain_text = re.sub(r"<[^>]+>", " ", html_content)
									plain_text = re.sub(r"\s+", " ", plain_text).strip()
									content_text = plain_text[:500]
								WatchDataRepository.create_data(
									source_id=source_id,
									keyword=keyword,
									title=item.get("title", ""),
									content=content_text,
									url=item.get("url", ""),
									publish_time=item.get("time", "")
								)
							final_result = {
								"source": source["source_name"],
								"page": page + 1,
								"status": "success",
								"count": len(news_items)
							}
							break
						except requests.exceptions.RequestException as e:
							if attempt < 2:
								continue
							final_result = {
								"source": source["source_name"],
								"page": page + 1,
								"status": "error",
								"message": f"请求失败（已自动重试3次）: {e}"
							}
						except Exception as e:
							final_result = {
								"source": source["source_name"],
								"page": page + 1,
								"status": "error",
								"message": str(e)
							}
							break
					
					if final_result:
						results.append(final_result)
			
			self.write(json.dumps({"success": True, "results": results}))
		except Exception as e:
			self.set_header("Content-Type", "application/json")
			self.write(json.dumps({"success": False, "message": str(e)}))

class AdminWatchDataListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		result = WatchDataRepository.list_data(page, 20)
		for d in result["data"]:
			if "create_at" in d and d["create_at"]:
				ca = d["create_at"]
				if len(ca) > 10:
					d["create_at"] = ca[:10] + " " + ca[11:19]
		self.render("admin_watch_data_list.html",
			title="数据仓库",
			username=self.current_user,
			active_menu="watch_data",
			data_list=result["data"],
			total=result["total"],
			page=result["page"],
			page_size=result["page_size"])
	
	def post(self):
		action = self.get_body_argument("action", "")
		ids_str = self.get_body_argument("ids", "")
		if action == "delete" and ids_str:
			ids = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
			WatchDataRepository.delete_datas(ids)
		return self.redirect("/admin/watch/data/list")
