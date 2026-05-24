import tornado.web
import json
import requests
import re
from app.controllers.admin_base import AdminBaseHandler
from app.models.watch_service import WatchSourceRepository, WatchDataRepository

def parse_baidu_news(html_content):
    news_items = []
    
    try:
        pattern = re.compile(r'<h3[^>]*class="[^"]*news-title[^"]*"[^>]*>.*?</h3>', re.DOTALL)
        matches = pattern.findall(html_content)
        
        for match in matches[:10]:
            try:
                title = ""
                url = ""
                
                link_pattern = re.compile(r'href="([^"]+)"')
                link_match = link_pattern.search(match)
                if link_match:
                    url = link_match.group(1)
                
                text_pattern = re.compile(r'>([^<]+)<')
                text_matches = text_pattern.findall(match)
                if text_matches:
                    title = "".join([t for t in text_matches if t.strip()])
                
                if title:
                    news_items.append({
                        "title": title.strip(),
                        "url": url,
                        "content": "",
                        "time": ""
                    })
            except:
                continue
    except:
        pass
    
    if not news_items:
        try:
            pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            matches = pattern.findall(html_content)
            for url, text in matches[:15]:
                text = text.strip()
                if len(text) > 5 and len(text) < 100 and 'http' not in text:
                    news_items.append({
                        "title": text,
                        "url": url if url.startswith('http') else "",
                        "content": "",
                        "time": ""
                    })
        except:
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
					url = source["url_template"].format(keyword=keyword, pn=pn)
					
					try:
						headers = {}
						if source.get("headers_json"):
							try:
								headers = json.loads(source["headers_json"])
							except:
								pass
						
						if source.get("cookie"):
							headers["Cookie"] = source["cookie"]
						
						response = requests.get(url, headers=headers, timeout=30)
						html_content = response.text
						
						news_items = parse_baidu_news(html_content)
						
						if news_items:
							for item in news_items:
								WatchDataRepository.create_data(
									source_id=source_id,
									keyword=keyword,
									title=item.get("title", ""),
									content=item.get("content", ""),
									url=item.get("url", ""),
									publish_time=item.get("time", "")
								)
							results.append({
								"source": source["source_name"],
								"page": page + 1,
								"status": "success",
								"count": len(news_items)
							})
						else:
							WatchDataRepository.create_data(
								source_id=source_id,
								keyword=keyword,
								title=f"{source['source_name']} - {keyword} - 第{page+1}页",
								content=html_content[:500] + "..." if len(html_content) > 500 else html_content,
								url=url
							)
							results.append({
								"source": source["source_name"],
								"page": page + 1,
								"status": "success",
								"count": 1
							})
					except Exception as e:
						results.append({
							"source": source["source_name"],
							"page": page + 1,
							"status": "error",
							"message": str(e)
						})
			
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
