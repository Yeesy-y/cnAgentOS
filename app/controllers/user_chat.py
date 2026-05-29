import tornado.web
import tornado.websocket
import json
import logging
from app.controllers.user_base import UserBaseHandler

# 全局存储在线用户连接
online_users = {}  # {username: WebSocketHandler}


class UserChatHandler(UserBaseHandler):
    """用户聊天页面控制器"""

    @tornado.web.authenticated
    def get(self):
        """渲染聊天页面"""
        self.render(
            "chat.html",
            title="智能聊天",
            username=self.current_user
        )


class UserSearchHandler(UserBaseHandler):
    """搜索用户（用于添加好友）"""

    @tornado.web.authenticated
    def get(self):
        username = self.get_argument("username", "")
        if not username:
            self.write({"success": False, "message": "请输入用户名"})
            return
        
        from app.models.user import UserRepository
        user = UserRepository.get_user_by_username(username)
        
        if user and user["username"] != self.current_user:
            self.write({
                "success": True, 
                "user": {
                    "id": user["id"],
                    "username": user["username"]
                }
            })
        else:
            self.write({"success": False, "message": "未找到该用户"})


class UserFriendAddHandler(UserBaseHandler):
    """发送好友请求"""

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        username = data.get("username")
        
        if not username:
            self.write({"success": False, "message": "请输入用户名"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        target_user = UserRepository.get_user_by_username(username)
        
        if not target_user:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        if current_user["id"] == target_user["id"]:
            self.write({"success": False, "message": "不能添加自己为好友"})
            return
        
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (current_user["id"], target_user["id"])
            ).fetchone()
            
            reverse_existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (target_user["id"], current_user["id"])
            ).fetchone()
            
            if existing:
                if existing["status"] == "pending":
                    self.write({"success": False, "message": "您已经发送过好友请求了"})
                    return
                elif existing["status"] == "accepted":
                    self.write({"success": False, "message": "该用户已经是您的好友"})
                    return
                elif existing["status"] == "rejected":
                    conn.execute(
                        "UPDATE friends SET status = 'pending' WHERE id = ?",
                        (existing["id"],)
                    )
                    conn.commit()
                    self.write({"success": True, "message": "好友请求已重新发送"})
                    return
            
            if reverse_existing:
                if reverse_existing["status"] == "pending":
                    self.write({"success": False, "message": "该用户已经向您发送了好友请求，请前往处理"})
                    return
                elif reverse_existing["status"] == "accepted":
                    self.write({"success": False, "message": "该用户已经是您的好友"})
                    return
                elif reverse_existing["status"] == "rejected":
                    conn.execute(
                        "UPDATE friends SET status = 'pending' WHERE id = ?",
                        (reverse_existing["id"],)
                    )
                    conn.commit()
                    self.write({"success": True, "message": "好友请求已重新发送"})
                    return
            
            conn.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'pending')",
                (current_user["id"], target_user["id"])
            )
            conn.commit()
        
        self.write({"success": True, "message": "好友请求已发送，等待对方同意"})


class UserFriendsHandler(UserBaseHandler):
    """获取好友列表"""

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT u.id, u.username 
                FROM users u
                JOIN friends f ON u.id = f.friend_id
                WHERE f.user_id = ? AND f.status = 'accepted'
            """, (current_user["id"],)).fetchall()
            
            friends = []
            for row in rows:
                friends.append({
                    "id": row["id"],
                    "name": row["username"],
                    "avatar": row["username"][0].upper() if row["username"] else "U",
                    "preview": "好友",
                    "time": "刚刚",
                    "badge": 0,
                    "type": "friend"
                })
            
            self.write({"success": True, "friends": friends})


class UserFriendRequestHandler(UserBaseHandler):
    """发送好友请求"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        username = data.get("username")
        
        if not username:
            self.write({"success": False, "message": "请输入用户名"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        target_user = UserRepository.get_user_by_username(username)
        
        if not target_user:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        if current_user["id"] == target_user["id"]:
            self.write({"success": False, "message": "不能添加自己为好友"})
            return
        
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (current_user["id"], target_user["id"])
            ).fetchone()
            
            reverse_existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (target_user["id"], current_user["id"])
            ).fetchone()
            
            if existing:
                if existing["status"] == "pending":
                    self.write({"success": False, "message": "您已经发送过好友请求了"})
                    return
                elif existing["status"] == "accepted":
                    self.write({"success": False, "message": "该用户已经是您的好友"})
                    return
                elif existing["status"] == "rejected":
                    conn.execute(
                        "UPDATE friends SET status = 'pending' WHERE id = ?",
                        (existing["id"],)
                    )
                    conn.commit()
                    self.write({"success": True, "message": "好友请求已重新发送"})
                    return
            
            if reverse_existing:
                if reverse_existing["status"] == "pending":
                    self.write({"success": False, "message": "该用户已经向您发送了好友请求，请前往处理"})
                    return
                elif reverse_existing["status"] == "accepted":
                    self.write({"success": False, "message": "该用户已经是您的好友"})
                    return
                elif reverse_existing["status"] == "rejected":
                    conn.execute(
                        "UPDATE friends SET status = 'pending' WHERE id = ?",
                        (reverse_existing["id"],)
                    )
                    conn.commit()
                    self.write({"success": True, "message": "好友请求已重新发送"})
                    return
            
            conn.execute(
                "INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, 'pending')",
                (current_user["id"], target_user["id"])
            )
            conn.commit()
        
        self.write({"success": True, "message": "好友请求已发送，等待对方同意"})


class UserFriendAcceptHandler(UserBaseHandler):
    """同意好友请求"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        requester_username = data.get("username")
        
        if not requester_username:
            self.write({"success": False, "message": "请指定要同意的好友请求"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        requester_user = UserRepository.get_user_by_username(requester_username)
        
        if not requester_user:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (requester_user["id"], current_user["id"])
            ).fetchone()
            
            if not existing:
                self.write({"success": False, "message": "不存在来自该用户的好友请求"})
                return
            
            if existing["status"] != "pending":
                self.write({"success": False, "message": "该好友请求已经被处理过了"})
                return
            
            conn.execute(
                "UPDATE friends SET status = 'accepted' WHERE id = ?",
                (existing["id"],)
            )
            conn.commit()
        
        self.write({"success": True, "message": "已同意好友请求"})


class UserFriendRejectHandler(UserBaseHandler):
    """拒绝好友请求"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        requester_username = data.get("username")
        
        if not requester_username:
            self.write({"success": False, "message": "请指定要拒绝的好友请求"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        requester_user = UserRepository.get_user_by_username(requester_username)
        
        if not requester_user:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, status FROM friends WHERE user_id = ? AND friend_id = ?",
                (requester_user["id"], current_user["id"])
            ).fetchone()
            
            if not existing:
                self.write({"success": False, "message": "不存在来自该用户的好友请求"})
                return
            
            if existing["status"] != "pending":
                self.write({"success": False, "message": "该好友请求已经被处理过了"})
                return
            
            conn.execute(
                "UPDATE friends SET status = 'rejected' WHERE id = ?",
                (existing["id"],)
            )
            conn.commit()
        
        self.write({"success": True, "message": "已拒绝好友请求"})


class UserFriendPendingHandler(UserBaseHandler):
    """获取待处理的好友请求"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT u.id, u.username, f.id as request_id, f.created_at
                FROM users u
                JOIN friends f ON u.id = f.user_id
                WHERE f.friend_id = ? AND f.status = 'pending'
                ORDER BY f.created_at DESC
            """, (current_user["id"],)).fetchall()
            
            pending_requests = []
            for row in rows:
                pending_requests.append({
                    "id": row["id"],
                    "username": row["username"],
                    "request_id": row["request_id"],
                    "avatar": row["username"][0].upper() if row["username"] else "U",
                    "time": row["created_at"]
                })
            
            sent_rows = conn.execute("""
                SELECT u.id, u.username, f.id as request_id, f.created_at
                FROM users u
                JOIN friends f ON u.id = f.friend_id
                WHERE f.user_id = ? AND f.status = 'pending'
                ORDER BY f.created_at DESC
            """, (current_user["id"],)).fetchall()
            
            sent_requests = []
            for row in sent_rows:
                sent_requests.append({
                    "id": row["id"],
                    "username": row["username"],
                    "request_id": row["request_id"],
                    "avatar": row["username"][0].upper() if row["username"] else "U",
                    "time": row["created_at"]
                })
            
            self.write({
                "success": True,
                "received": pending_requests,
                "sent": sent_requests
            })


class UserGroupsHandler(UserBaseHandler):
    """获取群聊列表"""

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT g.id, g.name 
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = ?
            """, (current_user["id"],)).fetchall()
            
            groups = []
            for row in rows:
                groups.append({
                    "id": row["id"],
                    "name": row["name"],
                    "avatar": "G",
                    "preview": "群聊",
                    "time": "刚刚",
                    "badge": 0,
                    "type": "group"
                })
            
            self.write({"success": True, "groups": groups})


class UserGroupCreateHandler(UserBaseHandler):
    """创建群聊"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        group_name = data.get("name")
        friends = data.get("friends", [])
        employees = data.get("employees", [])
        
        if not group_name:
            self.write({"success": False, "message": "请输入群名称"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO groups (name, creator_id) VALUES (?, ?)",
                (group_name, current_user["id"])
            )
            group_id = cursor.lastrowid
            
            conn.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                (group_id, current_user["id"])
            )
            
            for username in friends:
                target_user = UserRepository.get_user_by_username(username)
                if target_user:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
                            (group_id, target_user["id"])
                        )
                    except:
                        pass
            
            for employee_id in employees:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO group_employees (group_id, employee_id) VALUES (?, ?)",
                        (group_id, int(employee_id))
                    )
                except:
                    pass
            
            conn.commit()
        
        self.write({
            "success": True, 
            "message": "群聊创建成功",
            "group_id": group_id,
            "group_name": group_name
        })


class UserGroupInviteHandler(UserBaseHandler):
    """邀请好友或数字员工加入群聊"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        group_id = data.get("group_id")
        friends = data.get("friends", [])
        employees = data.get("employees", [])
        
        if not group_id:
            self.write({"success": False, "message": "请选择要邀请的群聊"})
            return
        
        if (not friends or len(friends) == 0) and (not employees or len(employees) == 0):
            self.write({"success": False, "message": "请选择要邀请的好友或数字员工"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            invited_count = 0
            for username in friends:
                target_user = UserRepository.get_user_by_username(username)
                if not target_user:
                    continue
                
                existing = conn.execute(
                    "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                    (group_id, target_user["id"])
                ).fetchone()
                if existing:
                    continue
                
                conn.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                    (group_id, target_user["id"])
                )
                invited_count += 1
            
            for employee_id in employees:
                existing = conn.execute(
                    "SELECT id FROM group_employees WHERE group_id = ? AND employee_id = ?",
                    (group_id, int(employee_id))
                ).fetchone()
                if existing:
                    continue
                
                try:
                    conn.execute(
                        "INSERT INTO group_employees (group_id, employee_id) VALUES (?, ?)",
                        (group_id, int(employee_id))
                    )
                    invited_count += 1
                except:
                    pass
            
            conn.commit()
        
        self.write({
            "success": True,
            "message": f"成功邀请 {invited_count} 位成员"
        })


class UserGroupMembersHandler(UserBaseHandler):
    """获取群成员列表（包括用户和数字员工）"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        group_id = self.get_argument("group_id", None)
        
        if not group_id:
            self.write({"success": False, "message": "请指定群聊ID"})
            return
        
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        with get_connection() as conn:
            user_rows = conn.execute(
                "SELECT user_id FROM group_members WHERE group_id = ?",
                (group_id,)
            ).fetchall()
            
            employee_rows = conn.execute(
                """
                SELECT de.id, de.employee_name, de.at_alias
                FROM group_employees ge
                JOIN digital_employees de ON de.id = ge.employee_id
                WHERE ge.group_id = ?
                """,
                (group_id,)
            ).fetchall()
        
        members = []
        for row in user_rows:
            user = UserRepository.get_user_by_id(row["user_id"])
            if user:
                members.append({
                    "id": user["id"],
                    "name": user["username"],
                    "avatar": user["username"][0].upper() if user["username"] else "U",
                    "type": "user"
                })
        
        for row in employee_rows:
            members.append({
                "id": row["id"],
                "name": row["employee_name"],
                "at_alias": row["at_alias"],
                "avatar": row["employee_name"][0].upper() if row["employee_name"] else "E",
                "type": "employee"
            })
        
        self.write({
            "success": True,
            "members": members
        })


class UserFriendClearHandler(UserBaseHandler):
    """清空私聊记录"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        friend_name = self.get_body_argument("friend_name", "")
        
        if not friend_name:
            self.write({"success": False, "message": "请指定好友名称"})
            return
        
        friend = UserRepository.get_user_by_username(friend_name)
        if not friend:
            self.write({"success": False, "message": "好友不存在"})
            return
        
        with get_connection() as conn:
            conn.execute("""
                DELETE FROM private_messages
                WHERE (sender_id = ? AND receiver_id = ?)
                   OR (sender_id = ? AND receiver_id = ?)
            """, (current_user["id"], friend["id"], friend["id"], current_user["id"]))
        
        self.write({"success": True, "message": "聊天记录已清空"})


class UserGroupClearHandler(UserBaseHandler):
    """清空群聊记录"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        from app.models.db import get_connection
        
        group_id = self.get_body_argument("group_id", "")
        
        if not group_id:
            self.write({"success": False, "message": "请指定群聊ID"})
            return
        
        with get_connection() as conn:
            conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        
        self.write({"success": True, "message": "群聊记录已清空"})


class UserFileUploadHandler(UserBaseHandler):
    """文件上传处理器"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        import uuid
        import os

        if 'file' not in self.request.files:
            self.write({"success": False, "message": "请选择要上传的文件"})
            return

        file_info = self.request.files['file'][0]
        original_filename = file_info['filename']
        file_body = file_info['body']
        content_type = file_info['content_type']

        file_ext = os.path.splitext(original_filename)[1]
        new_filename = f"{uuid.uuid4().hex}{file_ext}"

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "static", "uploads")
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(upload_dir, new_filename)

        with open(file_path, 'wb') as f:
            f.write(file_body)

        file_url = f"/static/uploads/{new_filename}"

        self.write({
            "success": True,
            "message": "文件上传成功",
            "file_url": file_url,
            "file_name": original_filename,
            "file_size": len(file_body),
            "file_type": content_type
        })


class UserEmployeesHandler(UserBaseHandler):
    """获取数字员工列表"""

    @tornado.web.authenticated
    def get(self):
        from app.models.db import get_connection
        
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, employee_name, at_alias FROM digital_employees WHERE status = 1"
            ).fetchall()
            
            employees = []
            for row in rows:
                employees.append({
                    "id": row["id"],
                    "name": row["employee_name"],
                    "avatar": row["employee_name"][0].upper() if row["employee_name"] else "B",
                    "preview": "数字员工",
                    "time": "在线",
                    "badge": 0,
                    "type": "bot",
                    "is_employee": True,
                    "at_alias": row["at_alias"]
                })
            
            self.write({"success": True, "employees": employees})

class UserMessageHistoryHandler(UserBaseHandler):
    """获取消息历史"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        chat_type = self.get_argument("type", "")
        chat_id = self.get_argument("id", "")
        
        if not chat_type or not chat_id:
            self.write({"success": False, "message": "缺少参数"})
            return
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        if not current_user:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        messages = []
        
        with get_connection() as conn:
            if chat_type == "private":
                # 获取私聊消息
                rows = conn.execute("""
                    SELECT 
                        m.id,
                        m.conversation_id,
                        m.role as sender,
                        m.content,
                        m.create_at as time,
                        CASE WHEN m.role = ? THEN 1 ELSE 0 END as is_own
                    FROM chat_messages m
                    JOIN chat_conversations c ON m.conversation_id = c.id
                    WHERE c.user_id = ? AND c.title = ?
                    ORDER BY m.create_at ASC
                """, (self.current_user, current_user["id"], chat_id)).fetchall()
                
                for row in rows:
                    messages.append({
                        "id": row["id"],
                        "sender": row["sender"],
                        "content": row["content"],
                        "time": row["time"],
                        "is_own": bool(row["is_own"])
                    })
            elif chat_type == "group":
                # 获取群聊消息
                rows = conn.execute("""
                    SELECT 
                        m.id,
                        m.role as sender,
                        m.content,
                        m.create_at as time,
                        CASE WHEN m.role = ? THEN 1 ELSE 0 END as is_own
                    FROM chat_messages m
                    WHERE m.conversation_id = ?
                    ORDER BY m.create_at ASC
                """, (self.current_user, chat_id)).fetchall()
                
                for row in rows:
                    messages.append({
                        "id": row["id"],
                        "sender": row["sender"],
                        "content": row["content"],
                        "time": row["time"],
                        "is_own": bool(row["is_own"])
                    })
        
        self.write({"success": True, "messages": messages})

class ChatWebSocketHandler(tornado.websocket.WebSocketHandler):
    """WebSocket聊天处理器"""

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.username = None

    def open(self):
        username = self.get_secure_cookie("username")
        if username:
            self.username = username.decode("utf-8")
            online_users[self.username] = self
            logging.info(f"用户 {self.username} 已连接")
            self.write_message(json.dumps({
                "type": "system",
                "content": "连接成功",
                "online_count": len(online_users)
            }))
        else:
            self.write_message(json.dumps({
                "type": "error",
                "content": "未登录，请先登录"
            }))
            self.close()

    def on_message(self, message):
        try:
            data = json.loads(message)
            message_type = data.get("type")
            content = data.get("content", "")
            
            if not self.username:
                self.write_message(json.dumps({
                    "type": "error",
                    "content": "未登录"
                }))
                return

            if message_type == "private":
                self.handle_private_message(data)
            elif message_type == "group":
                self.handle_group_message(data)
                self.handle_group_employee_mentions(data)
            else:
                self.write_message(json.dumps({
                    "type": "error",
                    "content": "未知消息类型"
                }))
        except json.JSONDecodeError:
            self.write_message(json.dumps({
                "type": "error",
                "content": "消息格式错误"
            }))
        except Exception as e:
            logging.error(f"消息处理错误: {e}")
            self.write_message(json.dumps({
                "type": "error",
                "content": "消息处理失败"
            }))

    def handle_digital_employee(self, message_type, data):
        content = data.get("content", "").strip()
        parts = content.split(" ", 1)
        if len(parts) < 1:
            self.write_message(json.dumps({
                "type": "error",
                "content": "命令格式错误，请使用 @数字员工名 消息内容"
            }))
            return
        
        employee_name = parts[0][1:]
        message_content = parts[1].strip() if len(parts) > 1 else ""
        
        # 先保存群聊消息到数据库
        if message_type == "group":
            self.save_group_message(data)
        
        if employee_name == "川农小助手":
            self.call_ai_assistant(message_content, message_type, data)
        elif employee_name == "天气小助手":
            self.call_weather_api(message_content, message_type, data)
        elif employee_name == "毒鸡汤助手":
            self.send_poison_chicken_soup(message_type, data)
        else:
            # 支持原有系统中的其他数字员工
            self.handle_other_employees(employee_name, message_content, message_type, data)

    def handle_group_employee_mentions(self, data):
        import re
        group_id = data.get("group_id")
        content = (data.get("content", "") or "").strip()
        if group_id is None or not content or "@" not in content:
            return
        from app.models.db import get_connection
        gid = int(group_id)
        mention_parts = re.findall(r"@([^\s@]+)", content)
        if not mention_parts:
            return
        punct = "，。,.!！？:：;；"
        mention_tokens = []
        seen = set()
        for p in mention_parts:
            token = (p or "").strip().strip(punct)
            if not token or token in seen:
                continue
            seen.add(token)
            mention_tokens.append(token)
        if not mention_tokens:
            return

        for token in mention_tokens:
            employee = None
            try:
                with get_connection() as conn:
                    row = conn.execute(
                        """
                        SELECT * FROM digital_employees
                        WHERE status = 1 AND (employee_name = ? OR at_alias = ?)
                        LIMIT 1
                        """,
                        (token, token)
                    ).fetchone()
                    if row:
                        employee = dict(row)
            except Exception as e:
                logging.error(f"读取数字员工失败({token}): {e}")
                employee = None

            if not employee:
                continue

            clean_message = content
            clean_message = re.sub(r"@" + re.escape(token) + r"(?=\s|$|[，。,.\!！\?？:：;；])", " ", clean_message)
            clean_message = clean_message.replace("@" + token, " ")
            clean_message = re.sub(r"\s+", " ", clean_message).strip()
            if not clean_message:
                clean_message = "你好"

            emp_name = (employee.get("employee_name") or "").strip()
            try:
                if emp_name == "天气小助手":
                    city = clean_message
                    try:
                        parts = [p for p in re.split(r"\s+", clean_message) if p]
                        if parts:
                            city = parts[-1].strip(punct)
                    except Exception:
                        city = clean_message
                    self.call_weather_api(city, "group", {"group_id": gid, "content": content})
                elif emp_name == "毒鸡汤助手":
                    self.send_poison_chicken_soup("group", {"group_id": gid, "content": content})
                else:
                    reply = self.generate_employee_reply_text(employee, clean_message)
                    if reply:
                        self.send_employee_response(emp_name, reply, "group", {"group_id": gid, "content": content})
            except Exception as e:
                logging.error(f"群聊数字员工回复失败({emp_name}): {e}")

    def generate_employee_reply_text(self, employee: dict, user_text: str) -> str:
        from app.models.chat_service import EmployeeOrchestrator
        parts = []
        for chunk in EmployeeOrchestrator.generate_employee_stream(employee, user_text, fallback_model_service_id=0):
            parts.append(chunk)
        return "".join(parts).strip()

    def call_ai_assistant(self, prompt, message_type, original_data):
        import urllib.request
        import urllib.error
        
        try:
            api_data = {
                "message": prompt,
                "conversation_id": 0,
                "model_service_id": ""
            }
            
            url = "http://localhost:10086/user/api/send"
            data_bytes = urllib.parse.urlencode(api_data).encode('utf-8')
            
            req = urllib.request.Request(url, data=data_bytes, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = response.read().decode('utf-8')
                try:
                    result_data = json.loads(result)
                    if result_data.get("success"):
                        self.send_employee_response("川农小助手", "这是AI助手的回复: " + prompt, message_type, original_data)
                    else:
                        self.write_message(json.dumps({
                            "type": "error",
                            "content": "AI助手调用失败: " + result_data.get("message", "未知错误")
                        }))
                except json.JSONDecodeError:
                    self.send_employee_response("川农小助手", "AI助手回复: " + result[:200], message_type, original_data)
        except urllib.error.URLError as e:
            logging.error(f"AI助手调用失败: {e}")
            self.send_employee_response("川农小助手", "AI助手暂时无法响应，请稍后再试", message_type, original_data)

    def call_weather_api(self, city, message_type, original_data):
        import urllib.request
        import urllib.error
        import random
        
        # 天气类型与特效映射
        weather_effects = {
            "晴": {"emoji": "☀️", "bg": "#FFE5B4", "effect": "sunny"},
            "多云": {"emoji": "⛅", "bg": "#B0C4DE", "effect": "cloudy"},
            "阴": {"emoji": "☁️", "bg": "#708090", "effect": "overcast"},
            "雨": {"emoji": "🌧️", "bg": "#4682B4", "effect": "rainy"},
            "雪": {"emoji": "❄️", "bg": "#F0F8FF", "effect": "snowy"},
            "雷阵雨": {"emoji": "⛈️", "bg": "#483D8B", "effect": "thunderstorm"},
            "雾": {"emoji": "🌫️", "bg": "#D3D3D3", "effect": "foggy"}
        }
        
        # 默认天气数据（如果API不可用）
        default_weathers = [
            {"city": city if city else "北京", "weather": "晴", "temp": 26, "wind": "微风", "humidity": "45%"},
            {"city": city if city else "北京", "weather": "多云", "temp": 22, "wind": "东北风3级", "humidity": "60%"},
            {"city": city if city else "北京", "weather": "小雨", "temp": 18, "wind": "东风2级", "humidity": "75%"},
            {"city": city if city else "北京", "weather": "阴", "temp": 20, "wind": "微风", "humidity": "70%"}
        ]
        
        try:
            url = f"http://localhost:10086/admin/api/test?api_id=2"
            
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                result = response.read().decode('utf-8')
                try:
                    weather_data = json.loads(result)
                    if weather_data.get("success"):
                        data = weather_data.get("data", {})
                        weather = data.get("weather", "晴")
                        temp = data.get("temp", "26")
                        humidity = data.get("humidity", "45%")
                        wind = data.get("wind", "微风")
                        city_name = data.get("city", city if city else "北京")
                        
                        self.send_weather_card(city_name, weather, str(temp), wind, humidity, weather_effects, message_type, original_data)
                    else:
                        # 使用默认数据
                        w_data = random.choice(default_weathers)
                        self.send_weather_card(w_data["city"], w_data["weather"], str(w_data["temp"]), w_data["wind"], w_data["humidity"], weather_effects, message_type, original_data)
                except json.JSONDecodeError:
                    w_data = random.choice(default_weathers)
                    self.send_weather_card(w_data["city"], w_data["weather"], str(w_data["temp"]), w_data["wind"], w_data["humidity"], weather_effects, message_type, original_data)
        except Exception as e:
            logging.error(f"天气接口调用失败: {e}")
            w_data = random.choice(default_weathers)
            self.send_weather_card(w_data["city"], w_data["weather"], str(w_data["temp"]), w_data["wind"], w_data["humidity"], weather_effects, message_type, original_data)
    
    def send_weather_card(self, city, weather, temp, wind, humidity, effects, message_type, original_data):
        effect_info = effects.get(weather, effects["晴"])
        
        weather_card = {
            "type": "weather_card",
            "city": city,
            "weather": weather,
            "temp": temp,
            "wind": wind,
            "humidity": humidity,
            "emoji": effect_info["emoji"],
            "bgColor": effect_info["bg"],
            "effect": effect_info["effect"]
        }
        
        self.send_employee_response("天气小助手", json.dumps(weather_card), message_type, original_data)

    def send_poison_chicken_soup(self, message_type, original_data):
        from app.models.api_service import ApiEndpointRepository
        try:
            result = ApiEndpointRepository.call_api("wl_yan_du", params={"type": "text"}, timeout=15)
            if result.get("success") is True:
                data = result.get("data")
                if isinstance(data, dict):
                    text = data.get("data") or data.get("text") or data.get("content")
                    if isinstance(text, str) and text.strip():
                        self.send_employee_response("毒鸡汤助手", text.strip(), message_type, original_data)
                        return
                if isinstance(data, str) and data.strip():
                    self.send_employee_response("毒鸡汤助手", data.strip(), message_type, original_data)
                    return
        except Exception:
            pass

        soup_list = [
            "努力不一定成功，但不努力一定会很舒服。",
            "你无法改变世界，但你可以改变自己——然后发现世界还是没变。",
            "比你优秀的人都在努力，那你努力还有什么用？",
            "不要抱怨生活，因为生活根本不知道你是谁。",
            "梦想还是要有的，万一实现不了呢？",
            "你以为你很努力了？别人只是没让你看到他们更努力。",
            "成功的路上并不拥挤，因为坚持的人不多——而你就是那个放弃的。",
            "世界上最遥远的距离不是生与死，而是别人的工资单和你的工资单。",
            "生活不止眼前的苟且，还有读不懂的诗和到不了的远方。",
            "小时候以为长大了能拯救世界，长大后发现世界都拯救不了我。",
            "如果你觉得自己不行，那你就真的不行了。",
            "有些人的起点，就是你一辈子的终点。",
            "不经历风雨怎么见彩虹？但有些人根本不需要经历风雨。",
            "当你觉得自己又穷又丑的时候，别担心，至少你的判断是对的。"
        ]
        
        import random
        soup = random.choice(soup_list)
        self.send_employee_response("毒鸡汤助手", soup, message_type, original_data)
    
    def handle_other_employees(self, employee_name, content, message_type, original_data):
        """处理原有系统中的其他数字员工"""
        from app.models.db import get_connection
        
        try:
            with get_connection() as conn:
                # 查询数字员工是否存在
                cursor = conn.execute("SELECT * FROM digital_employees WHERE employee_name = ?", (employee_name,))
                employee_row = cursor.fetchone()
                
                if employee_row:
                    employee = dict(employee_row)
                    # 数字员工存在，根据类型处理
                    service_type = employee["service_type"]
                    
                    if service_type == "LLM":
                        reply = self.generate_employee_reply_text(employee, content)
                        if reply:
                            self.send_employee_response(employee_name, reply, message_type, original_data)
                    elif service_type == "API":
                        reply = self.generate_employee_reply_text(employee, content)
                        if reply:
                            self.send_employee_response(employee_name, reply, message_type, original_data)
                        else:
                            self.send_employee_response(employee_name, f"我是{employee_name}，很高兴为您服务！", message_type, original_data)
                    else:
                        self.send_employee_response(employee_name, f"我是{employee_name}，{employee.get('description', '')}", message_type, original_data)
                else:
                    # @的不是数字员工（可能是普通好友），不报错，仅记录日志
                    logging.info(f"@了非数字员工: {employee_name}")
                    # 如果是群聊，发送成功响应
                    if message_type == "group":
                        self.write_message(json.dumps({
                            "type": "success",
                            "content": "消息已发送",
                            "message_id": original_data.get("message_id", 0)
                        }))
        except Exception as e:
            logging.error(f"处理数字员工 {employee_name} 失败: {e}")
            # 不向客户端发送错误，避免干扰正常聊天
            if message_type == "group":
                self.write_message(json.dumps({
                    "type": "success",
                    "content": "消息已发送",
                    "message_id": original_data.get("message_id", 0)
                }))
    
    def call_api_employee(self, employee, content, message_type, original_data):
        """调用API类型的数字员工"""
        employee_name = employee["employee_name"]
        self.send_employee_response(employee_name, f"{employee_name}正在处理您的请求：{content}", message_type, original_data)

    def send_employee_response(self, employee_name, content, message_type, original_data):
        response = {
            "type": message_type,
            "from": employee_name,
            "content": content
        }
        if message_type == "group":
            from app.models.db import get_connection
            from app.models.user import UserRepository
            group_id = original_data.get("group_id")
            if group_id is None:
                self.write_message(json.dumps(response, ensure_ascii=False))
                return
            group_id_int = int(group_id)
            employee_id = 0
            message_id = None
            try:
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT id FROM digital_employees WHERE employee_name = ?",
                        (employee_name,)
                    ).fetchone()
                    if row:
                        employee_id = int(row["id"])
                    if employee_id:
                        cursor = conn.execute(
                            """
                            INSERT INTO group_messages (group_id, sender_id, sender_type, content, message_type, referenced_message_id)
                            VALUES (?, ?, 'employee', ?, 'text', NULL)
                            """,
                            (group_id_int, employee_id, content)
                        )
                        message_id = cursor.lastrowid
                        conn.commit()
            except Exception as e:
                logging.error(f"保存数字员工群聊消息失败: {e}")

            try:
                with get_connection() as conn:
                    rows = conn.execute(
                        "SELECT user_id FROM group_members WHERE group_id = ?",
                        (group_id_int,)
                    ).fetchall()
                member_usernames = []
                for r in rows:
                    u = UserRepository.get_user_by_id(r["user_id"])
                    if u:
                        member_usernames.append(u["username"])
                response["group_id"] = group_id_int
                response["message_id"] = message_id or 0
                for uname in member_usernames:
                    if uname in online_users:
                        online_users[uname].write_message(json.dumps(response, ensure_ascii=False))
            except Exception as e:
                logging.error(f"推送数字员工群聊消息失败: {e}")
            return

        self.write_message(json.dumps(response, ensure_ascii=False))

    def handle_private_message(self, data):
        to_user = data.get("to")
        content = data.get("content")
        referenced_message_id = data.get("referenced_message_id", None)
        is_employee = data.get("is_employee", False)
        
        if not to_user or not content:
            self.write_message(json.dumps({
                "type": "error",
                "content": "缺少必要参数"
            }))
            return

        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.username)
        
        # 根据前端标记判断是否是数字员工
        if is_employee:
            # 前端标记为数字员工，处理数字员工消息
            employee = None
            with get_connection() as conn:
                employee_row = conn.execute(
                    "SELECT * FROM digital_employees WHERE employee_name = ?", (to_user,)
                ).fetchone()
                if employee_row:
                    employee = dict(employee_row)
            
            if employee:
                self.write_message(json.dumps({
                    "type": "success",
                    "content": "消息已发送",
                    "message_id": 0
                }))

                employee_name = employee["employee_name"]
                message_type = "private"
                original_data = {"to": to_user, "content": content}
                if employee_name == "天气小助手":
                    self.call_weather_api(content, message_type, original_data)
                elif employee_name == "毒鸡汤助手":
                    self.send_poison_chicken_soup(message_type, original_data)
                else:
                    reply = self.generate_employee_reply_text(employee, content)
                    if reply:
                        self.send_employee_response(employee_name, reply, message_type, original_data)
                    else:
                        self.send_employee_response(employee_name, f"我是{employee_name}，很高兴为您服务！", message_type, original_data)
                return
            else:
                # 前端标记为数字员工但数据库中不存在，返回错误
                self.write_message(json.dumps({
                    "type": "error",
                    "content": f"未知的数字员工: {to_user}"
                }))
                return
        
        # 是真实用户，继续原有逻辑
        target_user = UserRepository.get_user_by_username(to_user)
        
        if not target_user:
            employee = None
            try:
                with get_connection() as conn:
                    employee_row = conn.execute(
                        "SELECT * FROM digital_employees WHERE employee_name = ? AND status = 1",
                        (to_user,)
                    ).fetchone()
                    if employee_row:
                        employee = dict(employee_row)
            except Exception:
                employee = None
            if employee:
                self.write_message(json.dumps({
                    "type": "success",
                    "content": "消息已发送",
                    "message_id": 0
                }, ensure_ascii=False))
                employee_name = employee["employee_name"]
                message_type = "private"
                original_data = {"to": to_user, "content": content}
                if employee_name == "天气小助手":
                    self.call_weather_api(content, message_type, original_data)
                elif employee_name == "毒鸡汤助手":
                    self.send_poison_chicken_soup(message_type, original_data)
                else:
                    reply = self.generate_employee_reply_text(employee, content)
                    if reply:
                        self.send_employee_response(employee_name, reply, message_type, original_data)
                    else:
                        self.send_employee_response(employee_name, f"我是{employee_name}，很高兴为您服务！", message_type, original_data)
                return

            self.write_message(json.dumps({
                "type": "error",
                "content": f"用户 {to_user} 不存在"
            }, ensure_ascii=False))
            return
        
        # 保存消息到数据库
        message_id = None
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO private_messages (sender_id, receiver_id, content, message_type, referenced_message_id)
                VALUES (?, ?, ?, 'text', ?)
            """, (current_user["id"], target_user["id"], content, referenced_message_id))
            message_id = cursor.lastrowid
            conn.commit()
        
        # 如果用户在线，实时推送
        if to_user in online_users:
            # 检查是否是文件消息
            is_file = False
            try:
                parsed_content = json.loads(content)
                if isinstance(parsed_content, dict) and 'file_url' in parsed_content and 'file_name' in parsed_content:
                    is_file = True
            except (json.JSONDecodeError, TypeError):
                pass
            
            online_users[to_user].write_message(json.dumps({
                "type": "private",
                "from": self.username,
                "content": content,
                "is_file": is_file,
                "message_id": message_id,
                "referenced_message_id": referenced_message_id
            }))
            self.write_message(json.dumps({
                "type": "success",
                "content": "消息已发送",
                "message_id": message_id
            }))
        else:
            self.write_message(json.dumps({
                "type": "success",
                "content": "消息已保存，等待对方上线",
                "message_id": message_id
            }))

    def save_group_message(self, data):
        """保存群聊消息到数据库"""
        group_id = data.get("group_id")
        content = data.get("content")
        referenced_message_id = data.get("referenced_message_id", None)
        
        if group_id is None or not content:
            return None
        
        from app.models.db import get_connection
        from app.models.user import UserRepository
        
        current_user = UserRepository.get_user_by_username(self.username)
        
        message_id = None
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO group_messages (group_id, sender_id, sender_type, content, message_type, referenced_message_id)
                VALUES (?, ?, 'user', ?, 'text', ?)
            """, (int(group_id), current_user["id"], content, referenced_message_id))
            message_id = cursor.lastrowid
            conn.commit()
        
        return message_id

    def handle_group_message(self, data):
        group_id = data.get("group_id")
        content = data.get("content")
        referenced_message_id = data.get("referenced_message_id", None)
        
        if group_id is None or not content:
            self.write_message(json.dumps({
                "type": "error",
                "content": "缺少必要参数"
            }))
            return

        from app.models.db import get_connection
        from app.models.user import UserRepository
        
        current_user = UserRepository.get_user_by_username(self.username)
        
        # 保存消息到数据库
        message_id = self.save_group_message(data)
        
        # 从数据库获取群成员
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT user_id FROM group_members WHERE group_id = ?",
                (group_id,)
            ).fetchall()
            members = [row["user_id"] for row in rows]
        
        # 获取群成员的用户名
        member_usernames = []
        for user_id in members:
            user = UserRepository.get_user_by_id(user_id)
            if user:
                member_usernames.append(user["username"])
        
        sent_count = 0
        for member in member_usernames:
            if member != self.username and member in online_users:
                # 检查是否是文件消息
                is_file = False
                try:
                    parsed_content = json.loads(content)
                    if isinstance(parsed_content, dict) and 'file_url' in parsed_content and 'file_name' in parsed_content:
                        is_file = True
                except (json.JSONDecodeError, TypeError):
                    pass
                
                online_users[member].write_message(json.dumps({
                    "type": "group",
                    "group_id": group_id,
                    "from": self.username,
                    "content": content,
                    "is_file": is_file,
                    "message_id": message_id,
                    "referenced_message_id": referenced_message_id
                }))
                sent_count += 1

        self.write_message(json.dumps({
            "type": "success",
            "content": f"消息已发送给 {sent_count} 位在线成员",
            "message_id": message_id
        }))

    def on_close(self):
        if self.username and self.username in online_users:
            del online_users[self.username]
            logging.info(f"用户 {self.username} 已断开连接")

    def check_origin(self, origin):
        return True


class UserProfileHandler(UserBaseHandler):
    """用户个人信息页面"""

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        
        user = UserRepository.get_user_by_username(self.current_user)
        
        self.render(
            "profile.html",
            title="个人中心",
            username=self.current_user,
            user=user if user else {}
        )


class UserMessageHistoryHandler(UserBaseHandler):
    """获取聊天历史记录"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        chat_type = self.get_argument("type", "")
        target_id = self.get_argument("id", None)
        limit = int(self.get_argument("limit", 50))
        
        if not chat_type or not target_id:
            self.write({"success": False, "message": "请指定聊天类型和ID"})
            return
        
        messages = []
        
        with get_connection() as conn:
            if chat_type == "private":
                # 获取私聊消息
                target_user = UserRepository.get_user_by_username(target_id)
                if not target_user:
                    self.write({"success": False, "message": "用户不存在"})
                    return
                
                rows = conn.execute("""
                    SELECT 
                        m.id, m.sender_id, m.receiver_id, m.content, m.message_type,
                        m.is_read, m.read_at, m.referenced_message_id, m.created_at,
                        s.username as sender_name, r.username as receiver_name
                    FROM private_messages m
                    JOIN users s ON m.sender_id = s.id
                    JOIN users r ON m.receiver_id = r.id
                    WHERE 
                        (m.sender_id = ? AND m.receiver_id = ?) OR
                        (m.sender_id = ? AND m.receiver_id = ?)
                    ORDER BY m.created_at DESC
                    LIMIT ?
                """, (current_user["id"], target_user["id"], target_user["id"], current_user["id"], limit)).fetchall()
                
                for row in rows:
                    content = row["content"]
                    # 检查是否是文件消息（JSON格式包含file_url和file_name）
                    try:
                        parsed_content = json.loads(content)
                        if isinstance(parsed_content, dict) and 'file_url' in parsed_content and 'file_name' in parsed_content:
                            content = parsed_content
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    messages.append({
                        "id": row["id"],
                        "content": content,
                        "type": row["message_type"],
                        "sender": row["sender_name"],
                        "receiver": row["receiver_name"],
                        "is_own": row["sender_id"] == current_user["id"],
                        "is_read": bool(row["is_read"]),
                        "read_at": row["read_at"],
                        "referenced_message_id": row["referenced_message_id"],
                        "time": row["created_at"]
                    })
                
            elif chat_type == "group":
                # 获取群聊消息
                rows = conn.execute("""
                    SELECT 
                        m.id, m.group_id, m.sender_id, m.sender_type, m.content,
                        m.message_type, m.referenced_message_id, m.created_at,
                        u.username as sender_name, de.employee_name as employee_name
                    FROM group_messages m
                    LEFT JOIN users u ON m.sender_id = u.id AND m.sender_type = 'user'
                    LEFT JOIN digital_employees de ON m.sender_id = de.id AND m.sender_type = 'employee'
                    WHERE m.group_id = ?
                    ORDER BY m.created_at DESC
                    LIMIT ?
                """, (int(target_id), limit)).fetchall()
                
                for row in rows:
                    sender_name = row["sender_name"] if row["sender_type"] == "user" else row["employee_name"]
                    content = row["content"]
                    # 检查是否是文件消息（JSON格式包含file_url和file_name）
                    try:
                        parsed_content = json.loads(content)
                        if isinstance(parsed_content, dict) and 'file_url' in parsed_content and 'file_name' in parsed_content:
                            content = parsed_content
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    messages.append({
                        "id": row["id"],
                        "content": content,
                        "type": row["message_type"],
                        "sender": sender_name,
                        "sender_type": row["sender_type"],
                        "is_own": row["sender_type"] == "user" and row["sender_id"] == current_user["id"],
                        "referenced_message_id": row["referenced_message_id"],
                        "time": row["created_at"]
                    })
        
        # 反转消息顺序（从旧到新）
        messages.reverse()
        
        self.write({"success": True, "messages": messages})


class UserInfoHandler(UserBaseHandler):
    """获取用户信息"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        
        username = self.get_argument("username", "")
        if not username:
            self.write({"success": False, "message": "缺少用户名参数"})
            return
        
        user_row = UserRepository.get_user_by_username(username)
        if not user_row:
            self.write({"success": False, "message": "用户不存在"})
            return
        
        user = dict(user_row) if user_row else {}
        
        self.write({
            "success": True,
            "user": {
                "username": user.get("username", ""),
                "real_name": user.get("real_name", ""),
                "email": user.get("email", ""),
                "phone": user.get("phone", ""),
                "create_at": user.get("create_at", "")
            }
        })


class UserUnreadCountHandler(UserBaseHandler):
    """获取未读消息计数"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            # 获取私聊未读数
            private_unread = conn.execute("""
                SELECT sender_id, COUNT(*) as count
                FROM private_messages
                WHERE receiver_id = ? AND is_read = 0
                GROUP BY sender_id
            """, (current_user["id"],)).fetchall()
            
            # 获取群聊未读数
            group_unread = conn.execute("""
                SELECT gm.group_id, COUNT(DISTINCT gm.id) as count
                FROM group_messages gm
                JOIN group_members m ON gm.group_id = m.group_id
                WHERE m.user_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM group_message_reads r
                    WHERE r.message_id = gm.id AND r.user_id = ?
                )
                GROUP BY gm.group_id
            """, (current_user["id"], current_user["id"])).fetchall()
        
        unread_counts = {}
        
        # 处理私聊未读
        for row in private_unread:
            sender = UserRepository.get_user_by_id(row["sender_id"])
            if sender:
                unread_counts[sender["username"]] = row["count"]
        
        # 处理群聊未读
        for row in group_unread:
            unread_counts[f"group_{row['group_id']}"] = row["count"]
        
        self.write({"success": True, "unread_counts": unread_counts})


class UserMarkReadHandler(UserBaseHandler):
    """标记消息为已读"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        data = json.loads(self.request.body)
        chat_type = data.get("type", "")
        target_id = data.get("id", None)
        
        if not chat_type or not target_id:
            self.write({"success": False, "message": "请指定聊天类型和ID"})
            return
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            if chat_type == "private":
                target_user = UserRepository.get_user_by_username(target_id)
                if not target_user:
                    self.write({"success": False, "message": "用户不存在"})
                    return
                
                conn.execute("""
                    UPDATE private_messages 
                    SET is_read = 1, read_at = datetime('now')
                    WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
                """, (target_user["id"], current_user["id"]))
                
            elif chat_type == "group":
                # 标记所有群消息为已读
                rows = conn.execute("""
                    SELECT gm.id
                    FROM group_messages gm
                    WHERE gm.group_id = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM group_message_reads r
                        WHERE r.message_id = gm.id AND r.user_id = ?
                    )
                """, (int(target_id), current_user["id"])).fetchall()
                
                for row in rows:
                    try:
                        conn.execute("""
                            INSERT INTO group_message_reads (message_id, user_id)
                            VALUES (?, ?)
                        """, (row["id"], current_user["id"]))
                    except:
                        pass
            
            conn.commit()
        
        self.write({"success": True, "message": "已标记为已读"})


class UserMessageSearchHandler(UserBaseHandler):
    """搜索消息"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        data = json.loads(self.request.body)
        keyword = data.get("keyword", "").strip()
        chat_type = data.get("type", None)
        target_id = data.get("id", None)
        
        if not keyword:
            self.write({"success": False, "message": "请输入搜索关键词"})
            return
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        search_results = []
        
        with get_connection() as conn:
            # 搜索私聊消息
            if not chat_type or chat_type == "private":
                params = [f"%{keyword}%", current_user["id"], current_user["id"]]
                query = """
                    SELECT 
                        'private' as chat_type, m.id, m.sender_id, m.receiver_id,
                        m.content, m.created_at, s.username as sender_name, r.username as receiver_name
                    FROM private_messages m
                    JOIN users s ON m.sender_id = s.id
                    JOIN users r ON m.receiver_id = r.id
                    WHERE m.content LIKE ?
                    AND (m.sender_id = ? OR m.receiver_id = ?)
                """
                if target_id:
                    target_user = UserRepository.get_user_by_username(target_id)
                    if target_user:
                        query += """
                            AND (
                                (m.sender_id = ? AND m.receiver_id = ?) OR
                                (m.sender_id = ? AND m.receiver_id = ?)
                            )
                        """
                        params.extend([current_user["id"], target_user["id"], target_user["id"], current_user["id"]])
                
                query += " ORDER BY m.created_at DESC LIMIT 50"
                rows = conn.execute(query, params).fetchall()
                
                for row in rows:
                    search_results.append({
                        "chat_type": "private",
                        "chat_id": row["sender_name"] if row["sender_id"] != current_user["id"] else row["receiver_name"],
                        "chat_name": row["sender_name"] if row["sender_id"] != current_user["id"] else row["receiver_name"],
                        "message_id": row["id"],
                        "content": row["content"],
                        "time": row["created_at"],
                        "sender": row["sender_name"]
                    })
            
            # 搜索群聊消息
            if not chat_type or chat_type == "group":
                params = [f"%{keyword}%"]
                query = """
                    SELECT 
                        'group' as chat_type, m.id, m.group_id, m.content, m.created_at,
                        g.name as group_name, u.username as sender_name, de.employee_name as employee_name, m.sender_type
                    FROM group_messages m
                    JOIN groups g ON m.group_id = g.id
                    LEFT JOIN users u ON m.sender_id = u.id AND m.sender_type = 'user'
                    LEFT JOIN digital_employees de ON m.sender_id = de.id AND m.sender_type = 'employee'
                    WHERE m.content LIKE ?
                """
                if target_id:
                    query += " AND m.group_id = ?"
                    params.append(int(target_id))
                else:
                    query += """
                        AND EXISTS (
                            SELECT 1 FROM group_members gm
                            WHERE gm.group_id = m.group_id AND gm.user_id = ?
                        )
                    """
                    params.append(current_user["id"])
                
                query += " ORDER BY m.created_at DESC LIMIT 50"
                rows = conn.execute(query, params).fetchall()
                
                for row in rows:
                    sender_name = row["sender_name"] if row["sender_type"] == "user" else row["employee_name"]
                    search_results.append({
                        "chat_type": "group",
                        "chat_id": row["group_id"],
                        "chat_name": row["group_name"],
                        "message_id": row["id"],
                        "content": row["content"],
                        "time": row["created_at"],
                        "sender": sender_name
                    })
        
        self.write({"success": True, "results": search_results})


class UserMessageForwardHandler(UserBaseHandler):
    """转发消息"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        data = json.loads(self.request.body)
        message_id = data.get("message_id", None)
        message_type = data.get("message_type", "")  # private 或 group
        target_type = data.get("target_type", "")    # private 或 group
        target_id = data.get("target_id", None)
        
        if not message_id or not message_type or not target_type or not target_id:
            self.write({"success": False, "message": "参数不完整"})
            return
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        content = ""
        
        with get_connection() as conn:
            # 获取原始消息内容
            if message_type == "private":
                row = conn.execute("""
                    SELECT content, message_type FROM private_messages WHERE id = ?
                """, (int(message_id),)).fetchone()
            else:
                row = conn.execute("""
                    SELECT content, message_type FROM group_messages WHERE id = ?
                """, (int(message_id),)).fetchone()
            
            if not row:
                self.write({"success": False, "message": "消息不存在"})
                return
            
            content = row["content"]
            
            # 转发消息
            if target_type == "private":
                target_user = UserRepository.get_user_by_username(target_id)
                if not target_user:
                    self.write({"success": False, "message": "目标用户不存在"})
                    return
                
                conn.execute("""
                    INSERT INTO private_messages (sender_id, receiver_id, content, message_type, referenced_message_id)
                    VALUES (?, ?, ?, 'text', ?)
                """, (current_user["id"], target_user["id"], f"[转发] {content}", int(message_id)))
                
            else:
                conn.execute("""
                    INSERT INTO group_messages (group_id, sender_id, sender_type, content, message_type, referenced_message_id)
                    VALUES (?, ?, 'user', ?, 'text', ?)
                """, (int(target_id), current_user["id"], f"[转发] {content}", int(message_id)))
            
            conn.commit()
            
            # 实时推送消息
            new_message_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            
            if target_type == "private" and target_id in online_users:
                online_users[target_id].write_message(json.dumps({
                    "type": "private",
                    "from": self.current_user,
                    "content": f"[转发] {content}",
                    "message_id": new_message_id
                }))
            elif target_type == "group":
                # 获取群成员并推送
                rows = conn.execute("""
                    SELECT user_id FROM group_members WHERE group_id = ?
                """, (int(target_id),)).fetchall()
                for row in rows:
                    user = UserRepository.get_user_by_id(row["user_id"])
                    if user and user["username"] != self.current_user and user["username"] in online_users:
                        online_users[user["username"]].write_message(json.dumps({
                            "type": "group",
                            "group_id": int(target_id),
                            "from": self.current_user,
                            "content": f"[转发] {content}",
                            "message_id": new_message_id
                        }))
        
        self.write({"success": True, "message": "消息已转发"})


class UserMessageReferenceHandler(UserBaseHandler):
    """引用/回复消息（获取引用消息详情）"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        message_id = self.get_argument("message_id", None)
        message_type = self.get_argument("message_type", "private")
        
        if not message_id:
            self.write({"success": False, "message": "请指定消息ID"})
            return
        
        message_data = None
        
        with get_connection() as conn:
            if message_type == "private":
                row = conn.execute("""
                    SELECT 
                        m.id, m.sender_id, m.content, m.message_type, m.created_at,
                        s.username as sender_name
                    FROM private_messages m
                    JOIN users s ON m.sender_id = s.id
                    WHERE m.id = ?
                """, (int(message_id),)).fetchone()
            else:
                row = conn.execute("""
                    SELECT 
                        m.id, m.sender_id, m.sender_type, m.content, m.message_type, m.created_at,
                        u.username as sender_name, de.employee_name as employee_name
                    FROM group_messages m
                    LEFT JOIN users u ON m.sender_id = u.id AND m.sender_type = 'user'
                    LEFT JOIN digital_employees de ON m.sender_id = de.id AND m.sender_type = 'employee'
                    WHERE m.id = ?
                """, (int(message_id),)).fetchone()
            
            if row:
                sender_name = row.get("sender_name", "") if message_type == "private" else (
                    row["sender_name"] if row["sender_type"] == "user" else row["employee_name"]
                )
                content = row["content"]
                # 检查是否是文件消息（JSON格式包含file_url和file_name）
                try:
                    parsed_content = json.loads(content)
                    if isinstance(parsed_content, dict) and 'file_url' in parsed_content and 'file_name' in parsed_content:
                        content = parsed_content
                except (json.JSONDecodeError, TypeError):
                    pass
                
                message_data = {
                    "id": row["id"],
                    "content": content,
                    "type": row["message_type"],
                    "sender": sender_name,
                    "time": row["created_at"]
                }
        
        self.write({"success": True, "message": message_data})


class UserFriendsWithUnreadHandler(UserBaseHandler):
    """获取好友列表（包含未读消息计数）"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT u.id, u.username 
                FROM users u
                JOIN friends f ON u.id = f.friend_id
                WHERE f.user_id = ? AND f.status = 'accepted'
            """, (current_user["id"],)).fetchall()
            
            friends = []
            for row in rows:
                # 获取未读消息数
                unread_row = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM private_messages 
                    WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
                """, (row["id"], current_user["id"])).fetchone()
                
                # 获取最后一条消息
                last_msg_row = conn.execute("""
                    SELECT content, created_at
                    FROM private_messages
                    WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (current_user["id"], row["id"], row["id"], current_user["id"])).fetchone()
                
                preview = "好友"
                time_str = "刚刚"
                if last_msg_row:
                    preview = last_msg_row["content"][:30] + ("..." if len(last_msg_row["content"]) > 30 else "")
                    time_str = last_msg_row["created_at"]
                
                friends.append({
                    "id": row["id"],
                    "name": row["username"],
                    "avatar": row["username"][0].upper() if row["username"] else "U",
                    "preview": preview,
                    "time": time_str,
                    "badge": unread_row["count"] if unread_row else 0,
                    "type": "friend"
                })
            
            self.write({"success": True, "friends": friends})


class UserGroupsWithUnreadHandler(UserBaseHandler):
    """获取群聊列表（包含未读消息计数）"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        current_user = UserRepository.get_user_by_username(self.current_user)
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT g.id, g.name 
                FROM groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = ?
            """, (current_user["id"],)).fetchall()
            
            groups = []
            for row in rows:
                # 获取未读消息数
                unread_row = conn.execute("""
                    SELECT COUNT(DISTINCT gm.id) as count
                    FROM group_messages gm
                    WHERE gm.group_id = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM group_message_reads r
                        WHERE r.message_id = gm.id AND r.user_id = ?
                    )
                """, (row["id"], current_user["id"])).fetchone()
                
                # 获取最后一条消息
                last_msg_row = conn.execute("""
                    SELECT content, created_at
                    FROM group_messages
                    WHERE group_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (row["id"],)).fetchone()
                
                preview = "群聊"
                time_str = "刚刚"
                if last_msg_row:
                    preview = last_msg_row["content"][:30] + ("..." if len(last_msg_row["content"]) > 30 else "")
                    time_str = last_msg_row["created_at"]
                
                groups.append({
                    "id": row["id"],
                    "name": row["name"],
                    "avatar": "G",
                    "preview": preview,
                    "time": time_str,
                    "badge": unread_row["count"] if unread_row else 0,
                    "type": "group"
                })
            
            self.write({"success": True, "groups": groups})
