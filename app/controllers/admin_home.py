import tornado.web

from app.controllers.admin_base import AdminBaseHandler

class AdminIndexHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin_index.html",
			title="系统首页",
			username=self.current_user,
			active_menu="index")
