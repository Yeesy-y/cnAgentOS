# 数智大屏控制器
import tornado.web
import json
from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection
import random
from datetime import datetime, timedelta


class DashboardIndexHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        # current_user 可能是字符串或字典，根据实际类型处理
        username = self.current_user
        if isinstance(username, dict):
            username = username.get('username', 'Admin')
        elif isinstance(username, str):
            username = username
        else:
            username = 'Admin'
        
        self.render('admin_dashboard.html', 
                    title='数智大屏 - AI 智能瞭望系统',
                    username=username,
                    active_menu='dashboard')


class DashboardDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        data_type = self.get_argument('type', 'overview')
        
        try:
            if data_type == 'keywords':
                # 获取数据仓库中的关键词统计数据
                conn = get_connection()
                cursor = conn.execute("""
                    SELECT keyword, COUNT(*) as count, MAX(create_at) as last_collect
                    FROM watch_data
                    GROUP BY keyword
                    ORDER BY count DESC
                    LIMIT 50
                """)
                keywords = [dict(row) for row in cursor.fetchall()]
                
                # 统计前 10 个高频关键词的词云数据
                word_cloud_data = []
                top_keywords = keywords[:10] if keywords else []
                for kw in top_keywords:
                    word_cloud_data.append({
                        'name': kw['keyword'],
                        'value': int(kw['count'])
                    })
                
                result = {
                    'success': True,
                    'data': word_cloud_data
                }
                
            elif data_type == 'overview':
                # 获取整体数据统计
                conn = get_connection()
                
                # 总采集量
                total_count_result = conn.execute("SELECT COUNT(*) as total FROM watch_data").fetchone()
                total_records = int(total_count_result['total']) if total_count_result.get('total') else 0
                
                # 关键词总数
                keyword_count_result = conn.execute("SELECT COUNT(DISTINCT keyword) as total FROM watch_data").fetchone()
                keyword_total = int(keyword_count_result['total']) if keyword_count_result.get('total') else 0
                
                # 今日新增
                today = datetime.now().strftime('%Y-%m-%d')
                today_count_result = conn.execute(
                    "SELECT COUNT(*) as total FROM watch_data WHERE DATE(create_at) = ?",
                    (today,)
                ).fetchone()
                today_records = int(today_count_result['total']) if today_count_result.get('total') else 0
                
                # 采集源数量
                source_count_result = conn.execute("SELECT COUNT(*) as total FROM watch_sources").fetchone()
                source_total = int(source_count_result['total']) if source_count_result.get('total') else 0
                
                # 7 天趋势数据（模拟）
                trend_dates = []
                trend_values = []
                for i in range(6, -1, -1):
                    date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                    trend_dates.append(date.split('-')[2])  # 只显示日期数字
                    # 模拟生成趋势数据
                    value = random.randint(50, 200)
                    trend_values.append(value)
                
                result = {
                    'success': True,
                    'data': {
                        'total_records': total_records,
                        'keyword_total': keyword_total,
                        'today_records': today_records,
                        'source_total': source_total,
                        'trend_dates': trend_dates,
                        'trend_values': trend_values
                    }
                }
                
            elif data_type == 'chart_stats':
                # 图表统计数据
                conn = get_connection()
                
                # 按周统计
                weekly_data = []
                week_labels = []
                for i in range(3, -1, -1):
                    date = (datetime.now() - timedelta(days=i*7)).strftime('%Y-%m-%d')
                    week_start = datetime.strptime(date, '%Y-%m-%d')
                    week_end = week_start + timedelta(days=6)
                    
                    week_labels.append(f'{date.split("-")[1]}-{date.split("-")[2]}')
                    
                    count_result = conn.execute(
                        """
                        SELECT COUNT(*) as total FROM watch_data 
                        WHERE DATE(create_at) >= ? AND DATE(create_at) <= ?
                        """,
                        (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d'))
                    ).fetchone()
                    
                    weekly_data.append(int(count_result['total']) if count_result.get('total') else 0)
                
                # 采集来源分布
                source_dist_result = conn.execute("""
                    SELECT ws.source_name, COUNT(wd.id) as count
                    FROM watch_sources ws
                    LEFT JOIN watch_data wd ON ws.id = wd.source_id
                    GROUP BY ws.id, ws.source_name
                    ORDER BY count DESC
                    LIMIT 8
                """).fetchall()
                
                source_names = [row['source_name'] or '未分类' for row in source_dist_result]
                source_counts = [int(row['count']) if row['count'] else 0 for row in source_dist_result]
                
                # 数据类型分布（模拟）
                type_distribution = [
                    {'type': '新闻报道', 'value': random.randint(80, 150)},
                    {'type': '社交媒体', 'value': random.randint(100, 200)},
                    {'type': '政府公告', 'value': random.randint(40, 90)},
                    {'type': '学术文章', 'value': random.randint(30, 70)}
                ]
                
                result = {
                    'success': True,
                    'data': {
                        'weekly_data': weekly_data,
                        'week_labels': week_labels,
                        'source_names': source_names,
                        'source_counts': source_counts,
                        'type_distribution': type_distribution
                    }
                }
                
            elif data_type == 'earth_model':
                # 3D 地球模型相关数据（真实地理位置坐标）
                locations = [
                    {'name': '北京', 'value': random.randint(80, 150), 'coordinates': [116.4074, 39.9042, 100]},
                    {'name': '上海', 'value': random.randint(100, 180), 'coordinates': [121.4737, 31.2304, 150]},
                    {'name': '广州', 'value': random.randint(70, 130), 'coordinates': [113.2644, 23.1291, 120]},
                    {'name': '深圳', 'value': random.randint(90, 160), 'coordinates': [114.0579, 22.5431, 130]},
                    {'name': '成都', 'value': random.randint(60, 120), 'coordinates': [104.0668, 30.5728, 100]},
                    {'name': '杭州', 'value': random.randint(75, 140), 'coordinates': [120.1551, 30.2741, 110]},
                    {'name': '武汉', 'value': random.randint(55, 110), 'coordinates': [114.3055, 30.5928, 90]},
                    {'name': '西安', 'value': random.randint(50, 100), 'coordinates': [108.9398, 34.3416, 80]},
                    {'name': '重庆', 'value': random.randint(70, 140), 'coordinates': [106.5515, 29.5630, 100]},
                    {'name': '天津', 'value': random.randint(65, 125), 'coordinates': [117.2009, 39.0842, 110]},
                    {'name': '南京', 'value': random.randint(70, 135), 'coordinates': [118.7969, 32.0603, 115]},
                    {'name': '沈阳', 'value': random.randint(60, 120), 'coordinates': [123.4315, 41.8057, 95]},
                ]
                
                result = {
                    'success': True,
                    'data': locations
                }
                
            else:
                result = {
                    'success': False,
                    'message': '未知的数据类型'
                }
                
        except Exception as e:
            result = {
                'success': False,
                'message': str(e)
            }
        
        self.write(json.dumps(result, ensure_ascii=False, default=str))
