import tornado.web
import json
import os
from app.controllers.user_base import UserBaseHandler


class UserProfileHandler(UserBaseHandler):
    """用户个人信息页面控制器"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def get(self):
        """渲染个人信息页面"""
        from app.models.user import UserRepository
        
        user = UserRepository.get_user_by_username(self.current_user)
        
        if not user:
            user = {}
        
        self.render(
            "profile.html",
            title="个人中心",
            username=self.current_user,
            user=user
        )

    @tornado.web.authenticated
    def post(self):
        """处理保存个人信息请求"""
        action = self.get_argument("action", None)
        
        if action == "upload-avatar":
            self.upload_avatar()
        else:
            self.save_profile()

    def save_profile(self):
        """保存个人信息"""
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        try:
            data = json.loads(self.request.body)
            username = data.get("username", "").strip()
            nickname = data.get("nickname", "").strip()
            signature = data.get("signature", "").strip()
            bio = data.get("bio", "").strip()
            
            current_user = UserRepository.get_user_by_username(self.current_user)
            if not current_user:
                self.write({"success": False, "message": "用户不存在"})
                return
            
            if username != self.current_user:
                existing_user = UserRepository.get_user_by_username(username)
                if existing_user and existing_user["id"] != current_user["id"]:
                    self.write({"success": False, "message": "用户名已被使用"})
                    return
            
            with get_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(users)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                
                if "nickname" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT DEFAULT ''")
                if "signature" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN signature TEXT DEFAULT ''")
                if "bio" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
                if "avatar_url" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
                
                conn.execute(
                    "UPDATE users SET username = ?, nickname = ?, signature = ?, bio = ? WHERE id = ?",
                    (username, nickname, signature, bio, current_user["id"])
                )
                conn.commit()
            
            if username != self.current_user:
                self.set_secure_cookie("username", username)
            
            self.write({"success": True, "message": "保存成功"})
        except Exception as e:
            self.write({"success": False, "message": str(e)})

    def upload_avatar(self):
        """上传头像"""
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        try:
            file_info = self.request.files.get("avatar", None)
            if not file_info:
                self.write({"success": False, "message": "请选择图片"})
                return
            
            file = file_info[0]
            filename = file["filename"]
            ext = os.path.splitext(filename)[1].lower()
            
            if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                self.write({"success": False, "message": "不支持的图片格式"})
                return
            
            upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "avatars")
            os.makedirs(upload_dir, exist_ok=True)
            
            import hashlib
            import time
            timestamp = str(int(time.time()))
            hash_suffix = hashlib.md5((self.current_user + timestamp).encode()).hexdigest()[:8]
            avatar_filename = f"avatar_{self.current_user}_{hash_suffix}{ext}"
            avatar_path = os.path.join(upload_dir, avatar_filename)
            
            with open(avatar_path, "wb") as f:
                f.write(file["body"])
            
            avatar_url = f"/static/uploads/avatars/{avatar_filename}"
            current_user = UserRepository.get_user_by_username(self.current_user)
            
            with get_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(users)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if "avatar_url" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
                
                conn.execute(
                    "UPDATE users SET avatar_url = ? WHERE id = ?",
                    (avatar_url, current_user["id"])
                )
                conn.commit()
            
            self.write({"success": True, "message": "上传成功", "avatar_url": avatar_url})
        except Exception as e:
            self.write({"success": False, "message": str(e)})


class UserProfileSaveHandler(UserBaseHandler):
    """保存个人信息控制器"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        """处理保存个人信息请求"""
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        try:
            data = json.loads(self.request.body)
            username = data.get("username", "").strip()
            nickname = data.get("nickname", "").strip()
            signature = data.get("signature", "").strip()
            bio = data.get("bio", "").strip()
            
            current_user = UserRepository.get_user_by_username(self.current_user)
            if not current_user:
                self.write({"success": False, "message": "用户不存在"})
                return
            
            if username != self.current_user:
                existing_user = UserRepository.get_user_by_username(username)
                if existing_user and existing_user["id"] != current_user["id"]:
                    self.write({"success": False, "message": "用户名已被使用"})
                    return
            
            with get_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(users)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                
                if "nickname" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT DEFAULT ''")
                if "signature" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN signature TEXT DEFAULT ''")
                if "bio" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
                if "avatar_url" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
                
                conn.execute(
                    "UPDATE users SET username = ?, nickname = ?, signature = ?, bio = ? WHERE id = ?",
                    (username, nickname, signature, bio, current_user["id"])
                )
                conn.commit()
            
            if username != self.current_user:
                self.set_secure_cookie("username", username)
            
            self.write({"success": True, "message": "保存成功"})
        except Exception as e:
            self.write({"success": False, "message": str(e)})


class UserProfileAvatarHandler(UserBaseHandler):
    """头像上传控制器"""

    def check_xsrf_cookie(self):
        pass

    @tornado.web.authenticated
    def post(self):
        """处理头像上传请求"""
        from app.models.user import UserRepository
        from app.models.db import get_connection
        
        try:
            file_info = self.request.files.get("avatar", None)
            if not file_info:
                self.write({"success": False, "message": "请选择图片"})
                return
            
            file = file_info[0]
            filename = file["filename"]
            ext = os.path.splitext(filename)[1].lower()
            
            if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                self.write({"success": False, "message": "不支持的图片格式"})
                return
            
            upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "avatars")
            os.makedirs(upload_dir, exist_ok=True)
            
            import hashlib
            import time
            timestamp = str(int(time.time()))
            hash_suffix = hashlib.md5((self.current_user + timestamp).encode()).hexdigest()[:8]
            avatar_filename = f"avatar_{self.current_user}_{hash_suffix}{ext}"
            avatar_path = os.path.join(upload_dir, avatar_filename)
            
            with open(avatar_path, "wb") as f:
                f.write(file["body"])
            
            avatar_url = f"/static/uploads/avatars/{avatar_filename}"
            current_user = UserRepository.get_user_by_username(self.current_user)
            
            with get_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(users)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if "avatar_url" not in existing_cols:
                    conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
                
                conn.execute(
                    "UPDATE users SET avatar_url = ? WHERE id = ?",
                    (avatar_url, current_user["id"])
                )
                conn.commit()
            
            self.write({"success": True, "message": "上传成功", "avatar_url": avatar_url})
        except Exception as e:
            self.write({"success": False, "message": str(e)})