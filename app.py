#程序的主入口
#承担服务器容器+程序作用
#服务器容器:提供http容器服务,程序放置于该容器中运行
#程序:本体-智能瞭望与智能问数系统 B/s架构
from tornado.options import define, options
import os
import tornado.ioloop
import tornado.web
import logging
from tornado.httpserver import HTTPServer
from tornado.ioloop import PeriodicCallback

# 导入 user_profile
from app.controllers.user_profile import UserProfileHandler, UserProfileSaveHandler, UserProfileAvatarHandler

# 导入 user_home
from app.controllers.user_home import UserHomeHandler

# 导入 user_qa
from app.controllers.user_qa import UserQaHandler

# 导入 user_chat 中的所有 Handler
from app.controllers.user_chat import (
    UserChatHandler,
    ChatWebSocketHandler,
    UserSearchHandler,
    UserFriendAddHandler,
    UserFriendRequestHandler,
    UserFriendAcceptHandler,
    UserFriendRejectHandler,
    UserFriendPendingHandler,
    UserFriendClearHandler,
    UserGroupCreateHandler,
	UserGroupInviteHandler,
	UserGroupMembersHandler,
	UserGroupClearHandler,
	UserFriendsHandler,
	UserGroupsHandler,
	UserEmployeesHandler,
    UserFileUploadHandler,
    UserMessageHistoryHandler,
    UserInfoHandler,
    UserUnreadCountHandler,
    UserMarkReadHandler,
    UserMessageSearchHandler,
    UserMessageForwardHandler,
    UserMessageReferenceHandler,
    UserFriendsWithUnreadHandler,
    UserGroupsWithUnreadHandler,
)

#引入admin-controller层
from app.controllers.admin_auth import AdminLoginHandler,AdminLogoutHandler
from app.controllers.admin_home import AdminIndexHandler
from app.controllers.admin_user import AdminUserListHandler,AdminUserAddHandler,AdminUserEditHandler,AdminProfileHandler,AdminSecurityHandler
from app.controllers.admin_rbac import AdminPermissionListHandler,AdminPermissionAddHandler,AdminPermissionEditHandler
from app.controllers.admin_rbac import AdminRoleListHandler,AdminRoleAddHandler,AdminRoleEditHandler
from app.controllers.admin_model import AdminModelListHandler,AdminModelAddHandler,AdminModelEditHandler,AdminModelTestHandler
from app.controllers.admin_employee import AdminEmployeeListHandler,AdminEmployeeAddHandler,AdminEmployeeEditHandler
from app.controllers.admin_group import AdminGroupListHandler,AdminGroupDetailHandler,AdminGroupMembersHandler,AdminGroupMessagesHandler
from app.controllers.admin_file import AdminFileListHandler,AdminFileStatsHandler
from app.controllers.admin_server import AdminServerListHandler,AdminServerStatusHandler,AdminServerSwitchHandler
from app.controllers.admin_tool import AdminToolListHandler,AdminToolBindHandler
from app.controllers.admin_watch import AdminWatchSourceListHandler,AdminWatchSourceAddHandler,AdminWatchSourceEditHandler
from app.controllers.admin_watch import AdminWatchCollectHandler,AdminWatchDataListHandler,AdminWatchDeepCollectHandler,AdminWatchAutoTaskHandler
from app.controllers.admin_api import AdminApiListHandler,AdminApiAddHandler,AdminApiEditHandler,AdminApiTestHandler
from app.controllers.user_auth import UserLoginHandler,UserLogoutHandler,UserRegisterHandler
from app.controllers.user_api import UserModelsHandler,UserConversationsHandler,UserMessagesHandler,UserSendHandler,UserStreamHandler,UserConversationActionHandler,UserMediaProxyHandler
#引入db-model层
#数智大屏相关导入
from app.controllers.admin_dashboard import DashboardIndexHandler,DashboardDataHandler
#智能舆情相关导入
from app.controllers.admin_public_sentiment import PublicSentimentIndexHandler,SentimentAnalysisHandler,WatchDataSentimentHandler,ChatDataSentimentHandler,RiskStatsHandler
from app.controllers.admin_watch import execute_auto_task
#引入 db-model 层
from app.models.db import init_db
from app.models.watch_service import WatchAutoTaskRepository



# class HealthHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write({"status":"ok"})

# class LoginHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write(f"""<h3>模拟登录验证测试BaseHandler</h3>

# 			<form method="post">
# 			{self.xsrf_form_html()}
# 			<button type="submit">登录admin</button>
# 			</form>
# 			""")

# 	def post(self):
# 		next_url=self.get_argument("next","/private")
# 		self.set_secure_cookie("username","admin")
# 		#写完安全的cookie以后,跳转到目标地址
# 		self.redirect(next_url)

# class PrivateHandler(BaseHandler):
# 	@tornado.web. authenticated
# 	def get(self):
# 		self.write(self.current_user)





def run_auto_tasks():
	try:
		tasks = WatchAutoTaskRepository.list_due_tasks()
		if not tasks:
			return
		for task in tasks:
			try:
				result = execute_auto_task(task)
				logging.info("[AUTO_TASK] id=%s name=%s result=%s", task.get("id"), task.get("task_name"), result)
			except Exception as e:
				logging.exception("[AUTO_TASK] 执行异常 id=%s err=%s", task.get("id"), e)
				try:
					WatchAutoTaskRepository.mark_run_result(int(task.get("id")), int(task.get("interval_minutes") or 60), f"执行异常: {e}")
				except Exception:
					pass
	except Exception as e:
		logging.exception("[AUTO_TASK] 轮询异常: %s", e)


def make_app():
	# return tornado.web.Application([
	# 	("/abc",HealthHandler),
	# 	("/login.jsp",HealthHandler),
	# 	("/",HealthHandler),
	# 	("/login.php",HealthHandler)
	# ],debug=True)
	# return tornado.web.Application([
	# 	    (r"/",LoginHandler),
	# 	    (r"/abc",HealthHandler),
	# 	    (r"/private",PrivateHandler)
	#     ],
	#     cookie_secret="demo-cookie-secret-change-me",
	#     login_url="/",
	#     xsrf_cookies=True,
	#     debug=True
	# )
	base_url = os.path.dirname(os.path.abspath(__file__))
	settings = dict(
		#预留view层的内容配置
		template_path=os.path.join(base_url,"app","templates"),
		static_path=os.path.join(base_url,"app","static"),
		cookie_secret="demo-cookie-secret-change-me",
		login_url="/auth/login",
		xsrf_cookies=True,
		debug=True,
		autoreload=True
	)
	return tornado.web.Application([
		# 用户侧路由
		(r"/",UserHomeHandler),
		(r"/home",UserHomeHandler),
		(r"/login",UserLoginHandler),
		(r"/register",UserRegisterHandler),
		(r"/logout",UserLogoutHandler),
		(r"/chat",UserChatHandler),
		(r"/user_chat",UserQaHandler),
		(r"/chat/ws", ChatWebSocketHandler),
		(r"/profile", UserProfileHandler),
		(r"/user/profile", UserProfileHandler),
		(r"/user/profile/save", UserProfileSaveHandler),
		(r"/user/profile/avatar", UserProfileAvatarHandler),
		(r"/user/api/friends", UserFriendsHandler),
		(r"/user/api/groups", UserGroupsHandler),
		(r"/user/api/employees", UserEmployeesHandler),	
		(r"/user/api/models",UserModelsHandler),
		(r"/user/api/search", UserSearchHandler),
		(r"/user/api/conversations",UserConversationsHandler),
		(r"/user/api/messages",UserMessagesHandler),
		(r"/user/api/messages/history", UserMessageHistoryHandler),
		(r"/user/api/info", UserInfoHandler),
		(r"/user/api/send",UserSendHandler),
		(r"/user/api/conversation/action",UserConversationActionHandler),
		(r"/user/api/stream",UserStreamHandler),
		(r"/user/api/media/proxy",UserMediaProxyHandler),
		(r"/user/api/friend/add", UserFriendAddHandler),
		(r"/user/api/friend/request", UserFriendRequestHandler),
		(r"/user/api/friend/accept", UserFriendAcceptHandler),
		(r"/user/api/friend/reject", UserFriendRejectHandler),
		(r"/user/api/friend/pending", UserFriendPendingHandler),
		(r"/user/api/group/create", UserGroupCreateHandler),
		(r"/user/api/group/invite", UserGroupInviteHandler),
		(r"/user/api/group/members", UserGroupMembersHandler),
		(r"/user/api/group/clear", UserGroupClearHandler),
		(r"/user/api/friend/clear", UserFriendClearHandler),
		(r"/user/api/file/upload", UserFileUploadHandler),
		(r"/user/api/message/history", UserMessageHistoryHandler),
		(r"/user/api/unread/count", UserUnreadCountHandler),
		(r"/user/api/mark/read", UserMarkReadHandler),
		(r"/user/api/message/search", UserMessageSearchHandler),
		(r"/user/api/message/forward", UserMessageForwardHandler),
		(r"/user/api/message/reference", UserMessageReferenceHandler),
		(r"/user/api/friends/unread", UserFriendsWithUnreadHandler),
		(r"/user/api/groups/unread", UserGroupsWithUnreadHandler),
		# admin后台路由
		(r"/admin/login",AdminLoginHandler),
		(r"/admin/logout",AdminLogoutHandler),
		(r"/admin/index",AdminIndexHandler),
		(r"/admin/user/list",AdminUserListHandler),
		(r"/admin/user/add",AdminUserAddHandler),
		(r"/admin/user/edit",AdminUserEditHandler),
		(r"/admin/user/profile",AdminProfileHandler),
		(r"/admin/user/security",AdminSecurityHandler),
		# 模型引擎路由
		(r"/admin/model/list",AdminModelListHandler),
		(r"/admin/model/add",AdminModelAddHandler),
		(r"/admin/model/edit",AdminModelEditHandler),
		(r"/admin/model/test",AdminModelTestHandler),
		# 智能服务路由
		(r"/admin/employee/list",AdminEmployeeListHandler),
		(r"/admin/employee/add",AdminEmployeeAddHandler),
		(r"/admin/employee/edit",AdminEmployeeEditHandler),
		(r"/admin/group/list",AdminGroupListHandler),
		(r"/admin/group/detail",AdminGroupDetailHandler),
		(r"/admin/api/group/members",AdminGroupMembersHandler),
		(r"/admin/api/group/messages",AdminGroupMessagesHandler),
		(r"/admin/file/list",AdminFileListHandler),
		(r"/admin/api/file/stats",AdminFileStatsHandler),
		(r"/admin/server/list",AdminServerListHandler),
		(r"/admin/api/server/status",AdminServerStatusHandler),
		(r"/admin/api/server/switch",AdminServerSwitchHandler),
		(r"/admin/tool/list",AdminToolListHandler),
		(r"/admin/api/tool/bind",AdminToolBindHandler),
		# 瞭望管理路由
		(r"/admin/watch/source/list",AdminWatchSourceListHandler),
		(r"/admin/watch/source/add",AdminWatchSourceAddHandler),
		(r"/admin/watch/source/edit",AdminWatchSourceEditHandler),
		(r"/admin/watch/collect",AdminWatchCollectHandler),
		(r"/admin/watch/data/list",AdminWatchDataListHandler),
		(r"/admin/watch/deep/collect",AdminWatchDeepCollectHandler),
		(r"/admin/watch/auto-task",AdminWatchAutoTaskHandler),
		# RBAC路由
		(r"/admin/perm/list",AdminPermissionListHandler),
		(r"/admin/perm/add",AdminPermissionAddHandler),
		(r"/admin/perm/edit",AdminPermissionEditHandler),
		(r"/admin/role/list",AdminRoleListHandler),
		(r"/admin/role/add",AdminRoleAddHandler),
		(r"/admin/role/edit",AdminRoleEditHandler),
		# 接口管理路由
(r"/admin/api/list", AdminApiListHandler),
(r"/admin/api/add", AdminApiAddHandler),
(r"/admin/api/edit", AdminApiEditHandler),
(r"/admin/api/test", AdminApiTestHandler),
# 数智大屏路由
(r"/admin/dashboard", DashboardIndexHandler),
(r"/api/dashboard/data", DashboardDataHandler),
# 智能舆情路由
(r"/admin/public-sentiment", PublicSentimentIndexHandler),
(r"/api/public-sentiment/analyze", SentimentAnalysisHandler),
(r"/api/public-sentiment/watch-data", WatchDataSentimentHandler),
(r"/api/public-sentiment/chat-data", ChatDataSentimentHandler),
(r"/api/public-sentiment/risk-stats", RiskStatsHandler)
], **settings
)





	
if __name__=="__main__":
	#启动服务前，检查并初始化数据库表
	init_db()
	app=make_app()
	server = HTTPServer(app)
	server.bind(10086)
	#自动CPU核心数
	server.start()

	print("===== Server 启动成功 ======= 端口：10086 ======",flush=True)
	# 自动任务轮询：每60秒检查一次
	auto_task_timer = PeriodicCallback(run_auto_tasks, 60 * 1000)
	auto_task_timer.start()
	run_auto_tasks()
	tornado.ioloop.IOLoop.current().start()
