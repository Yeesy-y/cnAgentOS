import tornado.web
from app.controllers.user_base import UserBaseHandler


class UserQaHandler(UserBaseHandler):
    """智能问数页面控制器"""

    @tornado.web.authenticated
    def get(self):
        """渲染智能问数页面"""
        self.render(
            "user_chat.html",
            title="智能问数",
            username=self.current_user
        )
