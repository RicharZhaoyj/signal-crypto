import os
import json
import time
import base64
import random
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import ssl
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _get_access_token_from_service_account(key_path: str, scopes: list) -> Optional[str]:
    """通过服务账号JSON密钥直接请求access_token，避免依赖google-auth库。"""
    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            sa_info = json.load(f)

        now = int(time.time())
        header = {'alg': 'RS256', 'typ': 'JWT'}
        payload = {
            'iss': sa_info['client_email'],
            'scope': ' '.join(scopes),
            'aud': sa_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
            'iat': now,
            'exp': now + 3600,
        }

        header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
        payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            private_key = serialization.load_pem_private_key(
                sa_info['private_key'].encode('utf-8'),
                password=None,
            )
            signature = private_key.sign(
                signing_input,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except ImportError:
            try:
                import rsa
            except ImportError:
                print("GA4签名缺少加密库: 请 pip install cryptography")
                return None
            key = rsa.PrivateKey.load_pkcs1(sa_info['private_key'].encode('utf-8'))
            signature = rsa.sign(signing_input, key, 'SHA-256')

        jwt_token = f'{header_b64}.{payload_b64}.{_base64url_encode(signature)}'

        token_uri = sa_info.get('token_uri', 'https://oauth2.googleapis.com/token')
        body = urllib.parse.urlencode({
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': jwt_token,
        }).encode('ascii')

        resp_body = _https_post_with_retry(
            token_uri,
            body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
        )
        if not resp_body:
            return None
        return json.loads(resp_body.decode('utf-8')).get('access_token')
    except Exception as e:
        print(f"GA4令牌生成失败: {type(e).__name__}: {e}")
        return None


def _https_post_with_retry(url: str, body: bytes, headers: dict = None, timeout: int = 30, max_retries: int = 3) -> Optional[bytes]:
    """使用urllib发送HTTPS POST请求，自带重试。"""
    last_err = None
    if headers is None:
        headers = {}
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method='POST',
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        except (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError) as e:
            last_err = e
            print(f"GA4 HTTPS请求重试 {attempt}/{max_retries}: {type(e).__name__}: {e}")
            time.sleep(1 * attempt)
    print(f"GA4 HTTPS请求最终失败: {type(last_err).__name__}: {last_err}")
    return None

SITES = {
    'ai-link-cn': {
        'name': 'AI资讯新闻',
        'url': 'https://ai.link.cn',
        'host': 'ai.link.cn',
        'ga4_id': 'G-2F2V94W35E',
        'property_id': '545176332',
        'color': '#a855f7',
        'icon': '📰',
    },
    'signal-crypto': {
        'name': '加密货币分析',
        'url': 'https://signal.link.cn',
        'host': 'signal.link.cn',
        'ga4_id': 'G-2F2V94W35E',
        'property_id': '545176332',
        'color': '#f97316',
        'icon': '₿',
    },
    'tool-link-cn': {
        'name': 'AI工具LTD',
        'url': 'https://tool.link.cn',
        'host': 'tool.link.cn',
        'ga4_id': 'G-2F2V94W35E',
        'property_id': '545176332',
        'color': '#06b6d4',
        'icon': '⚡',
    },
    'ai-tool-hub': {
        'name': 'AI工具推荐',
        'url': 'https://tools.link.cn',
        'host': 'tools.link.cn',
        'ga4_id': 'G-2F2V94W35E',
        'property_id': '545176332',
        'color': '#3b82f6',
        'icon': '🛠️',
    },
    'prompts-repo': {
        'name': 'AI提示词市场',
        'url': 'https://prompts.link.cn',
        'host': 'prompts.link.cn',
        'ga4_id': 'G-2F2V94W35E',
        'property_id': '545176332',
        'color': '#22c55e',
        'icon': '✍️',
    },
}

CROSSLINK_STATUS = {
    'ai-link-cn': {'navbar': True, 'footer': True, 'home_section': True},
    'signal-crypto': {'navbar': True, 'footer': True, 'home_section': True},
    'tool-link-cn': {'navbar': True, 'footer': True, 'home_section': True},
    'ai-tool-hub': {'navbar': True, 'footer': True, 'home_section': True},
    'prompts-repo': {'navbar': True, 'footer': True, 'home_section': True},
}


def generate_mock_data(site_id: str, days: int = 7) -> Dict[str, Any]:
    random.seed(hash(site_id + datetime.now().strftime('%Y-%m-%d')))
    
    base_sessions = {
        'ai-link-cn': 120,
        'signal-crypto': 85,
        'tool-link-cn': 65,
        'ai-tool-hub': 200,
        'prompts-repo': 90,
    }
    
    base = base_sessions.get(site_id, 100)
    
    daily_data = []
    total_sessions = 0
    total_users = 0
    total_pageviews = 0
    
    for i in range(days):
        variance = random.uniform(0.7, 1.3)
        sessions = int(base * variance)
        users = int(sessions * random.uniform(0.6, 0.85))
        pageviews = int(sessions * random.uniform(1.8, 3.2))
        avg_duration = int(random.uniform(45, 180))
        bounce_rate = round(random.uniform(35, 65), 1)
        
        date = (datetime.now() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
        daily_data.append({
            'date': date,
            'sessions': sessions,
            'users': users,
            'pageviews': pageviews,
            'avg_duration': avg_duration,
            'bounce_rate': bounce_rate,
        })
        
        total_sessions += sessions
        total_users += users
        total_pageviews += pageviews
    
    avg_duration = int(sum(d['avg_duration'] for d in daily_data) / len(daily_data))
    avg_bounce_rate = round(sum(d['bounce_rate'] for d in daily_data) / len(daily_data), 1)
    
    prev_week_sessions = int(total_sessions * random.uniform(0.85, 1.15))
    sessions_change = round(((total_sessions - prev_week_sessions) / prev_week_sessions) * 100, 1)
    users_change = round(sessions_change + random.uniform(-2, 2), 1)
    pageviews_change = round(sessions_change + random.uniform(-3, 3), 1)
    
    return {
        'site_id': site_id,
        'name': SITES[site_id]['name'],
        'url': SITES[site_id]['url'],
        'ga4_id': SITES[site_id]['ga4_id'],
        'color': SITES[site_id]['color'],
        'icon': SITES[site_id]['icon'],
        'summary': {
            'sessions': total_sessions,
            'users': total_users,
            'pageviews': total_pageviews,
            'avg_duration': avg_duration,
            'bounce_rate': avg_bounce_rate,
            'sessions_change': sessions_change,
            'users_change': users_change,
            'pageviews_change': pageviews_change,
        },
        'daily': daily_data,
        'crosslink': CROSSLINK_STATUS.get(site_id, {}),
        'is_mock': True,
    }


def get_ga4_client():
    try:
        key_path = os.environ.get('GA4_KEY_FILE', r'C:\Users\zhaoy\Downloads\ga4-dashboard-502617-e1ecabec9222.json')
        if not os.path.exists(key_path):
            print(f"GA4密钥文件不存在: {key_path}")
            return None

        access_token = _get_access_token_from_service_account(
            key_path,
            scopes=['https://www.googleapis.com/auth/analytics.readonly'],
        )
        if not access_token:
            return None

        print(f"GA4令牌获取成功 (前10字符): {access_token[:10]}...")
        return {'token': access_token, 'expiry': time.time() + 3500}
    except Exception as e:
        print(f"GA4客户端初始化失败: {type(e).__name__}: {e}")
        return None


def fetch_ga4_data(credentials, site_id: str, days: int = 7) -> Optional[Dict[str, Any]]:
    if not credentials:
        return None

    property_id = SITES[site_id].get('property_id', '')
    if not property_id:
        print(f"站点 {site_id} 未配置property_id")
        return None

    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days - 1)).strftime('%Y-%m-%d')

        # 按子站host过滤，使各子站只返回自己的流量数据
        host = SITES[site_id].get('host', '')
        request_body = {
            'dimensions': [{'name': 'date'}],
            'metrics': [
                {'name': 'sessions'},
                {'name': 'activeUsers'},
                {'name': 'screenPageViews'},
                {'name': 'averageSessionDuration'},
                {'name': 'bounceRate'},
            ],
            'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
        }
        if host:
            request_body['dimensionFilter'] = {
                'filter': {
                    'fieldName': 'hostName',
                    'stringFilter': {'matchType': 'EXACT', 'value': host},
                }
            }

        url = f'https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport'
        body = json.dumps(request_body).encode('utf-8')

        resp_body = _https_post_with_retry(
            url,
            body,
            headers={
                'Authorization': f'Bearer {credentials["token"]}',
                'Content-Type': 'application/json',
            },
            timeout=30,
        )
        if not resp_body:
            return None

        data = json.loads(resp_body.decode('utf-8'))
        print(f"GA4 [{site_id}] host={host} 返回行数={len(data.get('rows', []))}")
        
        daily_data = []
        for row in data.get('rows', []):
            date_str = row['dimensionValues'][0]['value']
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            formatted_date = date_obj.strftime('%Y-%m-%d')
            
            daily_data.append({
                'date': formatted_date,
                'sessions': int(row['metricValues'][0]['value']),
                'users': int(row['metricValues'][1]['value']),
                'pageviews': int(row['metricValues'][2]['value']),
                'avg_duration': float(row['metricValues'][3]['value']),
                'bounce_rate': float(row['metricValues'][4]['value']) * 100,
            })
        
        daily_data.sort(key=lambda x: x['date'])
        
        total_sessions = sum(d['sessions'] for d in daily_data)
        total_users = sum(d['users'] for d in daily_data)
        total_pageviews = sum(d['pageviews'] for d in daily_data)
        avg_duration = int(sum(d['avg_duration'] for d in daily_data) / len(daily_data)) if daily_data else 0
        avg_bounce_rate = round(sum(d['bounce_rate'] for d in daily_data) / len(daily_data), 1) if daily_data else 0
        
        return {
            'site_id': site_id,
            'name': SITES[site_id]['name'],
            'url': SITES[site_id]['url'],
            'ga4_id': SITES[site_id]['ga4_id'],
            'color': SITES[site_id]['color'],
            'icon': SITES[site_id]['icon'],
            'summary': {
                'sessions': total_sessions,
                'users': total_users,
                'pageviews': total_pageviews,
                'avg_duration': avg_duration,
                'bounce_rate': avg_bounce_rate,
                'sessions_change': 0,
                'users_change': 0,
                'pageviews_change': 0,
            },
            'daily': daily_data,
            'crosslink': CROSSLINK_STATUS.get(site_id, {}),
            'is_mock': False,
        }
    except Exception as e:
        print(f"获取GA4数据失败 ({site_id}, property_id={property_id}): {type(e).__name__}: {e}")
        return None


def get_site_data(site_id: str, days: int = 7, credentials=None) -> Dict[str, Any]:
    if credentials:
        real_data = fetch_ga4_data(credentials, site_id, days)
        if real_data:
            return real_data
    
    return generate_mock_data(site_id, days)


def get_all_sites_data(days: int = 7) -> Dict[str, Any]:
    sites_data = {}
    has_real_data = False
    
    credentials = get_ga4_client()
    
    for site_id in SITES:
        data = get_site_data(site_id, days, credentials)
        sites_data[site_id] = data
        if not data.get('is_mock', True):
            has_real_data = True
    
    total_sessions = sum(d['summary']['sessions'] for d in sites_data.values())
    total_users = sum(d['summary']['users'] for d in sites_data.values())
    total_pageviews = sum(d['summary']['pageviews'] for d in sites_data.values())
    
    summary = {
        'total_sites': len(SITES),
        'ga4_configured': sum(1 for d in sites_data.values() if not d.get('is_mock', True)),
        'auto_updates': 4,
        'crosslink_complete': all(
            d['crosslink'].get('navbar', False) and d['crosslink'].get('footer', False)
            for d in sites_data.values()
        ),
        'total_sessions': total_sessions,
        'total_users': total_users,
        'total_pageviews': total_pageviews,
        'has_real_data': has_real_data,
    }
    
    return {
        'summary': summary,
        'sites': sites_data,
        'generated_at': datetime.now().isoformat(),
    }


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f'{minutes}m {secs}s'
    hours = minutes // 60
    mins = minutes % 60
    return f'{hours}h {mins}m'


if __name__ == '__main__':
    data = get_all_sites_data()
    print(json.dumps(data, indent=2, ensure_ascii=False))
