import tornado.web
import json
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import quote
from app.controllers.admin_base import AdminBaseHandler
from app.models.watch_service import WatchSourceRepository, WatchDataRepository, WatchDataDetailRepository, WatchAutoTaskRepository

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

    def clean_text(text):
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('\u3000', ' ')
        return text

    def is_garbled(text):
        if not text:
            return True
        bad_markers = ['\ufffd', '锟', '鈥', '�']
        bad = sum(text.count(m) for m in bad_markers)
        ratio = bad / max(1, len(text))
        return ratio > 0.03

    try:
        soup = BeautifulSoup(html_content, "lxml")
        cards = soup.select("div.result, div.news-item")
        if not cards:
            cards = soup.select("article, div")[:120]

        for card in cards[:60]:
            a = card.select_one("h3 a") or card.select_one("a")
            if not a:
                continue
            title = clean_text(a.get_text(" ", strip=True))
            url = (a.get("href") or "").strip()

            if not title or len(title) < 4:
                continue
            if is_garbled(title):
                continue

            content = ""
            abs_node = card.select_one(".c-abstract") or card.select_one(".content") or card.select_one(".summary") or card.select_one("p")
            if abs_node:
                content = clean_text(abs_node.get_text(" ", strip=True))
                if is_garbled(content):
                    content = ""

            publish_time = ""
            txt = clean_text(card.get_text(" ", strip=True))
            tm = re.search(r'(\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{1,2})?)', txt)
            if tm:
                publish_time = tm.group(1)

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
            for url, text in matches[:40]:
                text = clean_text(re.sub(r'<[^>]+>', ' ', text))
                if len(text) > 5 and len(text) < 120 and 'http' not in text and not is_garbled(text):
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

class AdminWatchDeepCollectHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		ids_str = (self.get_argument("ids", "") or "").strip()
		if not ids_str:
			self.set_header("Content-Type", "application/json")
			self.write(json.dumps({"success": False, "message": "请选择要深度采集的数据"}))
			return

		data_ids = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
		if not data_ids:
			self.set_header("Content-Type", "application/json")
			self.write(json.dumps({"success": False, "message": "未找到有效数据ID"}))
			return

		self.set_header("Content-Type", "text/event-stream")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		self.set_header("X-Accel-Buffering", "no")

		default_model = self._get_default_model()
		if not default_model:
			self._sse_event("error", {"message": "未找到默认模型服务，请先在模型引擎中设置默认模型"})
			self._sse_event("done", {"total": len(data_ids), "completed": 0, "failed": len(data_ids), "total_tokens": 0})
			self.finish()
			return

		total = len(data_ids)
		completed = 0
		failed = 0
		total_tokens = 0

		self._sse_event("start", {"total": total, "model": default_model.get("model_name", "未知模型")})

		for idx, data_id in enumerate(data_ids):
			current = idx + 1
			self._sse_event("progress", {
				"current": current,
				"total": total,
				"data_id": data_id,
				"message": f"正在深度采集 ({current}/{total}) ..."
			})
			self.flush()

			try:
				data_item = WatchDataRepository.get_data_by_id(data_id)
				if not data_item:
					self._sse_event("item_log", {"data_id": data_id, "status": "failed", "message": f"#{data_id}: 数据不存在"})
					failed += 1
					continue

				target_url = data_item.get("url", "") or ""
				existing_title = data_item.get("title", "") or ""
				existing_content = data_item.get("content", "") or ""

				self._sse_event("item_log", {"data_id": data_id, "status": "crawling", "message": f"#{data_id}: 正在抓取网页内容..."})
				self.flush()

				crawled_content = self._crawl_url(target_url)

				page_text = crawled_content if crawled_content else existing_content

				self._sse_event("item_log", {"data_id": data_id, "status": "analyzing", "message": f"#{data_id}: 正在用AI模型深度解析..."})
				self.flush()

				ai_result = self._deep_analyze(default_model, existing_title, existing_content, page_text, target_url)

				if ai_result.get("success"):
					source_id = data_item.get("source_id", 0)
					detail_id = WatchDataDetailRepository.create_detail(
						data_id=data_id,
						source_id=source_id,
						detail_title=ai_result.get("title", existing_title),
						detail_content=ai_result.get("content", page_text),
						detail_summary=ai_result.get("summary", ""),
						detail_keywords=ai_result.get("keywords", ""),
						source_url=target_url,
						ai_model=default_model.get("model_id", ""),
						tokens_used=ai_result.get("tokens", 0)
					)
					WatchDataDetailRepository.update_detail(detail_id, deep_status=2)
					tokens_used = ai_result.get("tokens", 0)
					total_tokens += tokens_used
					if tokens_used and default_model.get("id"):
						try:
							from app.models.model_service import ModelServiceRepository
							ModelServiceRepository.increment_token_usage(default_model["id"], tokens_used)
						except Exception:
							pass
					completed += 1
					self._sse_event("item_log", {"data_id": data_id, "status": "completed", "message": f"#{data_id}: 深度采集完成 (tokens: {tokens_used})"})
				else:
					detail_id = WatchDataDetailRepository.create_detail(
						data_id=data_id,
						source_id=data_item.get("source_id", 0),
						detail_title=existing_title,
						detail_content=page_text,
						source_url=target_url,
						ai_model=default_model.get("model_id", ""),
						tokens_used=0
					)
					WatchDataDetailRepository.update_detail(detail_id, deep_status=3, error_msg=ai_result.get("message", "AI解析失败"))
					failed += 1
					self._sse_event("item_log", {"data_id": data_id, "status": "failed", "message": f"#{data_id}: AI解析失败 - {ai_result.get('message', '')}"})
			except Exception as e:
				failed += 1
				self._sse_event("item_log", {"data_id": data_id, "status": "failed", "message": f"#{data_id}: 异常 - {str(e)}"})

			self.flush()

		stats = {"total": total, "completed": completed, "failed": failed, "total_tokens": total_tokens}
		self._sse_event("summary", stats)
		self._sse_event("done", stats)
		self.finish()

	def _sse_event(self, event_type: str, data: dict):
		line = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
		self.write(line)

	def _get_default_model(self):
		try:
			from app.models.model_service import ModelServiceRepository
			return ModelServiceRepository.get_default_model()
		except Exception:
			return None

	def _crawl_url(self, url: str) -> str:
		if not url:
			return ""
		try:
			headers = {
				"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
				"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
				"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
			}
			resp = requests.get(url, headers=headers, timeout=15)
			resp.raise_for_status()
			resp.encoding = resp.apparent_encoding or "utf-8"
			html = resp.text

			from bs4 import BeautifulSoup
			soup = BeautifulSoup(html, "lxml")
			for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
				tag.decompose()

			body = soup.find("body")
			if not body:
				body = soup

			text_parts = []
			for tag in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "span", "div"]):
				txt = tag.get_text(strip=True)
				if txt and len(txt) > 3:
					text_parts.append(txt)

			full_text = "\n".join(text_parts)
			if len(full_text) > 6000:
				full_text = full_text[:6000]
			return full_text
		except Exception:
			return ""

	def _deep_analyze(self, model: dict, title: str, original_content: str, page_content: str, source_url: str) -> dict:
		try:
			prompt = f"""请对以下采集到的网页内容进行深度解析，并以JSON格式返回结果。
解析要求：
1. 提取文章的准确标题
2. 对全文内容进行深度摘要（300字以内）
3. 提取5-10个关键词（逗号分隔）
4. 保留原文核心内容（精简至2000字以内）

原始标题: {title[:200] if title else '无'}
原文URL: {source_url[:200] if source_url else '无'}

网页正文内容:
{page_content[:5000] if page_content else ''}

原始摘要:
{original_content[:1000] if original_content else '无'}

请严格按照以下JSON格式返回（不要包含markdown标记）：
{{"title":"提取的标题","summary":"深度摘要内容","keywords":"关键词1,关键词2,关键词3","content":"精简后的核心内容"}}"""

			headers = {
				"Content-Type": "application/json",
				"Authorization": f"Bearer {model['api_key']}"
			}
			data = {
				"model": model["model_id"],
				"messages": [{"role": "user", "content": prompt}],
				"stream": False,
				"temperature": 0.3,
				"max_tokens": 3000
			}

			base = model['base_url'].rstrip('/')
			if base.endswith('/chat/completions'):
				url = base
			elif base.endswith('/v1'):
				url = base + '/chat/completions'
			else:
				url = base + '/v1/chat/completions'

			response = requests.post(url, headers=headers, json=data, timeout=120)
			response.raise_for_status()
			result_data = response.json()

			ai_content = result_data["choices"][0]["message"]["content"]
			tokens = result_data.get("usage", {}).get("total_tokens", 0)

			json_match = re.search(r'\{[^{}]*\}', ai_content, re.DOTALL)
			if json_match:
				parsed = json.loads(json_match.group())
				return {
					"success": True,
					"title": parsed.get("title", title),
					"summary": parsed.get("summary", ""),
					"keywords": parsed.get("keywords", ""),
					"content": parsed.get("content", page_content[:2000]),
					"tokens": tokens
				}

			if len(ai_content) > 20:
				return {
					"success": True,
					"title": title,
					"summary": ai_content[:600],
					"keywords": "",
					"content": ai_content[:2000],
					"tokens": tokens
				}

			return {"success": False, "message": "AI返回内容为空"}

		except requests.exceptions.HTTPError as e:
			err_text = ""
			try:
				err_json = e.response.json()
				err_text = err_json.get("error", {}).get("message", "") or str(err_json)
			except Exception:
				err_text = e.response.text[:300] if e.response is not None else str(e)
			return {"success": False, "message": f"模型API错误: {err_text}"}
		except requests.exceptions.RequestException as e:
			return {"success": False, "message": f"网络请求失败: {str(e)}"}
		except Exception as e:
			return {"success": False, "message": str(e)}


class AdminWatchAutoTaskHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.set_header("Content-Type", "application/json")
		tasks = WatchAutoTaskRepository.list_tasks()
		self.write(json.dumps({"success": True, "tasks": tasks}, ensure_ascii=False))

	@tornado.web.authenticated
	def post(self):
		self.set_header("Content-Type", "application/json")
		action = (self.get_body_argument("action", "") or "").strip()
		try:
			if action == "create":
				task_name = (self.get_body_argument("task_name", "") or "").strip()
				keyword = (self.get_body_argument("keyword", "") or "").strip()
				source_ids = [int(x) for x in self.get_body_arguments("source_ids") if str(x).isdigit()]
				count_per_page = int(self.get_body_argument("count_per_page", "10"))
				pages = int(self.get_body_argument("pages", "1"))
				interval_minutes = int(self.get_body_argument("interval_minutes", "60"))
				if not task_name or not keyword or not source_ids:
					self.write(json.dumps({"success": False, "message": "参数不完整"}, ensure_ascii=False))
					return
				tid = WatchAutoTaskRepository.create_task(task_name, keyword, source_ids, count_per_page, pages, interval_minutes)
				self.write(json.dumps({"success": True, "task_id": tid}, ensure_ascii=False))
				return
			if action == "toggle":
				task_id = int(self.get_body_argument("task_id", "0"))
				status = int(self.get_body_argument("status", "1"))
				WatchAutoTaskRepository.update_status(task_id, status)
				self.write(json.dumps({"success": True}, ensure_ascii=False))
				return
			if action == "delete":
				task_id = int(self.get_body_argument("task_id", "0"))
				WatchAutoTaskRepository.delete_task(task_id)
				self.write(json.dumps({"success": True}, ensure_ascii=False))
				return
			if action == "run_now":
				task_id = int(self.get_body_argument("task_id", "0"))
				tasks = [t for t in WatchAutoTaskRepository.list_tasks() if t.get("id") == task_id]
				if not tasks:
					self.write(json.dumps({"success": False, "message": "任务不存在"}, ensure_ascii=False))
					return
				result = execute_auto_task(tasks[0])
				self.write(json.dumps({"success": True, "message": result}, ensure_ascii=False))
				return
		except Exception as e:
			self.write(json.dumps({"success": False, "message": str(e)}, ensure_ascii=False))
			return
		self.write(json.dumps({"success": False, "message": "未知操作"}, ensure_ascii=False))


def execute_auto_task(task: dict) -> str:
	keyword = (task.get("keyword", "") or "").strip()
	if not keyword:
		return "任务缺少关键词"
	try:
		source_ids = json.loads(task.get("source_ids_json", "[]") or "[]")
	except Exception:
		source_ids = []
	if not isinstance(source_ids, list) or not source_ids:
		return "任务缺少采集源"
	count_per_page = int(task.get("count_per_page") or 10)
	pages = int(task.get("pages") or 1)
	saved_count = 0
	error_count = 0

	for source_id in source_ids:
		source = WatchSourceRepository.get_source_by_id(int(source_id))
		if not source:
			error_count += 1
			continue
		for page in range(max(1, pages)):
			pn = page * 10
			context = {
				"keyword": quote(keyword),
				"keyword_raw": keyword,
				"pn": pn,
				"page": page + 1
			}
			url = render_with_context(source["url_template"], context)
			page_saved = 0
			last_html = ""
			ok = False
			for attempt in range(3):
				try:
					headers = dict(DEFAULT_SOURCE_HEADERS)
					if source.get("headers_json"):
						try:
							custom_headers = json.loads(source["headers_json"])
							if isinstance(custom_headers, dict):
								headers.update(render_with_context(custom_headers, context))
						except Exception:
							pass
					if source.get("cookie"):
						headers["Cookie"] = render_with_context(source["cookie"], context)
					response = requests.get(url, headers=headers, timeout=30)
					response.raise_for_status()
					html_content = decode_html_response(response, keyword)
					last_html = html_content
					if is_abnormal_page(html_content):
						if attempt < 2:
							continue
						error_count += 1
						break
					news_items = parse_baidu_news(html_content)
					if count_per_page > 0:
						news_items = news_items[:count_per_page]
					if not news_items and attempt < 2:
						continue
					for item in news_items:
						title = (item.get("title", "") or "").strip()
						content = (item.get("content", "") or "").strip()
						if not title and not content:
							continue
						WatchDataRepository.create_data(
							source_id=int(source_id),
							keyword=keyword,
							title=title[:200],
							content=content[:1000],
							url=(item.get("url", "") or "")[:500],
							publish_time=(item.get("time", "") or "")[:50]
						)
						page_saved += 1
					ok = True
					break
				except Exception:
					if attempt >= 2:
						error_count += 1
			if not ok and page_saved == 0 and last_html:
				try:
					soup = BeautifulSoup(last_html, "lxml")
					title = (soup.title.get_text(" ", strip=True) if soup.title else "") or f"{keyword} 自动采集结果"
					text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:700]
					if text:
						WatchDataRepository.create_data(
							source_id=int(source_id),
							keyword=keyword,
							title=title[:200],
							content=text,
							url=url[:500],
							publish_time=""
						)
						page_saved += 1
				except Exception:
					pass
			saved_count += page_saved

	result = f"自动采集完成：成功入库 {saved_count} 条，异常 {error_count} 次"
	WatchAutoTaskRepository.mark_run_result(int(task.get("id")), int(task.get("interval_minutes") or 60), result)
	return result


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
