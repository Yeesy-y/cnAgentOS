import tornado.web
from app.controllers.user_base import UserBaseHandler

class UserChatPageHandler(UserBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("user_chat.html",
			title="智能问数",
			username=self.current_user)
