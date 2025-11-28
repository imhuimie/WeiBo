#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微博超话批量签到脚本
作者: emper0r
版本: v1.2
cron: 0 8 * * *
new Env('微博超话签到');

支持多账户配置：
1. 单账户：WEIBO_COOKIE="cookie内容"
2. 多账户：WEIBO_COOKIES="cookie1@cookie2@cookie3" 或换行分割
"""

import os
import re
import sys
import json
import time
import random
import requests
from urllib.parse import urlencode, quote

class WeiboChaohuaSignin:
    def __init__(self, cookie, account_index=1, total_accounts=1):
        self.account_index = account_index
        self.total_accounts = total_accounts
        self.account_name = f"账户{account_index}"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        # 处理Cookie编码问题
        self.cookie = self.clean_cookie(cookie)
        self.session.headers['Cookie'] = self.cookie
        
        self.xsrf_token = self.get_xsrf_token()
        
        if self.xsrf_token:
            self.session.headers['X-XSRF-TOKEN'] = self.xsrf_token
        
        # 配置
        self.sign_interval = 1.5  # 签到间隔(秒)
        self.account_interval = 10  # 账户间间隔(秒)
    
    def clean_cookie(self, cookie):
        """清理Cookie，处理编码问题"""
        try:
            # 移除可能的换行符和多余空格
            cookie = cookie.strip().replace('\n', '').replace('\r', '')
            
            # 确保Cookie是字符串格式
            if isinstance(cookie, bytes):
                cookie = cookie.decode('utf-8', errors='ignore')
            
            # 移除可能的非ASCII字符
            cookie = ''.join(char for char in cookie if ord(char) < 128)
            
            return cookie
        except Exception as e:
            self.log(f"Cookie处理失败: {str(e)}", 'ERROR')
            return cookie
    
    def get_xsrf_token(self):
        """从Cookie中提取XSRF-TOKEN"""
        try:
            match = re.search(r'XSRF-TOKEN=([^;]+)', self.cookie)
            if match:
                return match.group(1)
        except:
            pass
        return None
    
    def get_user_info(self):
        """获取用户基本信息"""
        try:
            # 从Cookie中提取用户名或ID
            sub_match = re.search(r'SUB=([^;]+)', self.cookie)
            if sub_match:
                return f"用户{sub_match.group(1)[:8]}..."
        except:
            pass
        return "未知用户"
    
    def log(self, message, level='INFO'):
        """日志输出"""
        timestamp = time.strftime('%H:%M:%S', time.localtime())
        symbols = {
            'INFO': 'ℹ️',
            'SUCCESS': '✅', 
            'ERROR': '❌',
            'WARNING': '⚠️'
        }
        
        # 多账户时显示账户信息
        account_prefix = f"[{self.account_name}] " if self.total_accounts > 1 else ""
        print(f"[{timestamp}] {symbols.get(level, 'ℹ️')} {account_prefix}{message}")
    
    def fetch_chaohua_list(self, page=1, collected=None):
        """获取超话列表"""
        if collected is None:
            collected = []
            
        self.log(f"正在获取第 {page} 页超话列表...")
        
        url = f"https://weibo.com/ajax/profile/topicContent"
        params = {
            'tabid': '231093_-_chaohua',
            'page': page
        }
        
        try:
            # 更新请求头
            headers = {
                'Referer': 'https://weibo.com/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"HTTP Error: {response.status_code}")
            
            # 检查响应内容
            if not response.text:
                raise Exception("响应内容为空")
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                self.log(f"JSON解析失败，响应内容: {response.text[:200]}...", 'ERROR')
                raise Exception(f"JSON解析失败: {str(e)}")
            
            if data.get('ok') != 1:
                error_msg = data.get('msg', '未知错误')
                if 'login' in error_msg.lower() or 'cookie' in error_msg.lower():
                    raise Exception(f"登录状态失效，请更新Cookie: {error_msg}")
                raise Exception(f"API返回错误: {error_msg}")
            
            api_data = data.get('data', {})
            chaohua_list = api_data.get('list', [])
            
            if not chaohua_list:
                return collected
            
            # 提取超话ID和名称
            for item in chaohua_list:
                oid = item.get('oid', '')
                if oid.startswith('1022:'):
                    chaohua_id = oid[5:]  # 去掉前缀 "1022:"
                    chaohua_name = item.get('topic_name', '')
                    if chaohua_id and chaohua_name:
                        collected.append({
                            'id': chaohua_id,
                            'name': chaohua_name
                        })
            
            # 检查是否还有下一页
            max_page = api_data.get('max_page', 1)
            if page < max_page:
                time.sleep(0.8)  # 增加延迟
                return self.fetch_chaohua_list(page + 1, collected)
            
            return collected
            
        except requests.exceptions.RequestException as e:
            self.log(f"网络请求失败: {str(e)}", 'ERROR')
            raise
        except Exception as e:
            self.log(f"获取超话列表失败: {str(e)}", 'ERROR')
            raise
    
    def sign_chaohua(self, chaohua_id, chaohua_name):
        """签到单个超话"""
        url = "https://weibo.com/p/aj/general/button"
        
        params = {
            'api': 'http://i.huati.weibo.com/aj/super/checkin',
            'id': chaohua_id,
            'location': 'page_100808_super_index',
            '__rnd': int(time.time() * 1000)
        }
        
        try:
            headers = {
                'Referer': f'https://weibo.com/p/{chaohua_id}/super_index',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return {'success': False, 'msg': f'HTTP错误: {response.status_code}'}
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                return {'success': False, 'msg': '响应格式错误'}
            
            code = str(data.get('code', ''))
            msg = data.get('msg', '未知错误')
            
            # 成功的状态码: 100000(签到成功), 382004(今日已签到), 382010(其他成功状态)
            success_codes = ['100000', '382004', '382010']
            is_success = code in success_codes
            
            return {
                'success': is_success,
                'code': code,
                'msg': msg,
                'already_signed': code == '382004'
            }
            
        except requests.exceptions.RequestException as e:
            return {'success': False, 'msg': f'网络请求失败: {str(e)}'}
        except Exception as e:
            return {'success': False, 'msg': f'签到失败: {str(e)}'}
    
    def run(self):
        """单个账户执行签到"""
        user_info = self.get_user_info()
        self.log(f"🚀 开始执行签到任务 ({user_info})")
        
        # 检查Cookie和XSRF-TOKEN
        if not self.xsrf_token:
            self.log("⚠️ 未找到XSRF-TOKEN，可能影响签到功能", 'WARNING')
        
        try:
            # 获取超话列表
            self.log("📋 正在获取超话列表...")
            chaohua_list = self.fetch_chaohua_list()
            
            if not chaohua_list:
                self.log("未获取到超话列表，请检查Cookie是否有效", 'WARNING')
                return {
                    'success': False,
                    'total': 0,
                    'success_count': 0,
                    'already_signed_count': 0,
                    'fail_count': 0
                }
            
            self.log(f"📊 成功获取到 {len(chaohua_list)} 个超话")
            
            # 开始批量签到
            success_count = 0
            already_signed_count = 0
            fail_count = 0
            
            for i, chaohua in enumerate(chaohua_list, 1):
                chaohua_id = chaohua['id']
                chaohua_name = chaohua['name']
                
                self.log(f"📝 正在签到 ({i}/{len(chaohua_list)}): {chaohua_name}")
                
                result = self.sign_chaohua(chaohua_id, chaohua_name)
                
                if result['success']:
                    if result.get('already_signed'):
                        self.log(f"⚠️  [{chaohua_name}] {result['msg']}", 'WARNING')
                        already_signed_count += 1
                    else:
                        self.log(f"✅ [{chaohua_name}] {result['msg']}", 'SUCCESS')
                        success_count += 1
                else:
                    self.log(f"❌ [{chaohua_name}] {result['msg']}", 'ERROR')
                    fail_count += 1
                
                # 添加随机延迟，避免请求过快
                if i < len(chaohua_list):
                    delay = self.sign_interval + random.uniform(0.5, 1.0)
                    time.sleep(delay)
            
            # 输出统计结果
            self.log("=" * 30)
            self.log("📈 签到统计结果:")
            self.log(f"✅ 签到成功: {success_count} 个")
            self.log(f"⚠️  已签过: {already_signed_count} 个") 
            self.log(f"❌ 签到失败: {fail_count} 个")
            self.log(f"📊 总计处理: {len(chaohua_list)} 个超话")
            
            if success_count > 0 or already_signed_count > 0:
                self.log("🎉 账户签到任务完成!", 'SUCCESS')
            else:
                self.log("⚠️ 没有成功签到任何超话，请检查Cookie状态", 'WARNING')
            
            return {
                'success': True,
                'total': len(chaohua_list),
                'success_count': success_count,
                'already_signed_count': already_signed_count,
                'fail_count': fail_count
            }
            
        except Exception as e:
            self.log(f"任务执行失败: {str(e)}", 'ERROR')
            # 提供一些常见问题的解决建议
            if 'cookie' in str(e).lower() or 'login' in str(e).lower():
                self.log("💡 建议: 请重新获取微博Cookie并更新环境变量", 'INFO')
            elif 'network' in str(e).lower() or 'timeout' in str(e).lower():
                self.log("💡 建议: 检查网络连接或稍后重试", 'INFO')
            
            return {
                'success': False,
                'total': 0,
                'success_count': 0,
                'already_signed_count': 0,
                'fail_count': 0,
                'error': str(e)
            }

def get_cookies():
    """获取Cookie配置，支持多种分割方式"""
    # 优先使用多账户配置
    cookies_env = os.getenv('WEIBO_COOKIES')
    if cookies_env:
        cookies = []
        
        # 尝试不同的分割方式
        if '@' in cookies_env:
            # 使用@分割
            cookies = [cookie.strip() for cookie in cookies_env.split('@') if cookie.strip()]
        elif '\n' in cookies_env:
            # 使用换行分割
            cookies = [cookie.strip() for cookie in cookies_env.split('\n') if cookie.strip()]
        elif '----' in cookies_env:
            # 使用----分割（兼容旧版本）
            cookies = [cookie.strip() for cookie in cookies_env.split('----') if cookie.strip()]
        else:
            # 单个Cookie
            cookies = [cookies_env.strip()]
        
        if cookies:
            print(f"🔍 检测到多账户配置，共 {len(cookies)} 个账户")
            return cookies
    
    # 单账户配置
    cookie_env = os.getenv('WEIBO_COOKIE')
    if cookie_env:
        print("🔍 检测到单账户配置")
        return [cookie_env.strip()]
    
    return []

def main():
    """主函数"""
    print("=" * 60)
    print("🌟 微博超话批量签到脚本 v1.2")
    print("👨‍💻 作者: emper0r")
    print("📅 支持多账户批量签到")
    print("=" * 60)
    
    # 检查是否在青龙面板环境中
    if not os.getenv('QL_DIR'):
        print("⚠️  建议在青龙面板中运行此脚本")
    
    # 获取Cookie配置
    cookies = get_cookies()
    
    if not cookies:
        print("❌ 请设置环境变量 WEIBO_COOKIE 或 WEIBO_COOKIES")
        print("💡 单账户: WEIBO_COOKIE=\"cookie内容\"")
        print("💡 多账户: WEIBO_COOKIES=\"cookie1@cookie2@cookie3\" 或换行分割")
        sys.exit(1)
    
    # 总体统计
    total_accounts = len(cookies)
    all_results = []
    
    print(f"🎯 开始执行批量签到任务，共 {total_accounts} 个账户")
    print("=" * 60)
    
    # 逐个账户执行签到
    for i, cookie in enumerate(cookies, 1):
        if not cookie or len(cookie) < 50:  # 简单验证Cookie长度
            print(f"❌ 账户{i} Cookie无效，跳过")
            continue
        
        try:
            # 创建签到实例
            signin = WeiboChaohuaSignin(cookie, i, total_accounts)
            
            # 执行签到
            result = signin.run()
            all_results.append({
                'account': i,
                'result': result
            })
            
            # 账户间延迟
            if i < total_accounts:
                print(f"⏱️  等待 {signin.account_interval} 秒后处理下一个账户...")
                time.sleep(signin.account_interval)
            
        except Exception as e:
            print(f"❌ 账户{i} 执行失败: {str(e)}")
            all_results.append({
                'account': i,
                'result': {
                    'success': False,
                    'total': 0,
                    'success_count': 0,
                    'already_signed_count': 0,
                    'fail_count': 0,
                    'error': str(e)
                }
            })
        
        print("-" * 60)
    
    # 输出总体统计
    print("🏆 全部账户签到完成！")
    print("=" * 60)
    print("📊 总体统计结果:")
    
    total_success = 0
    total_already_signed = 0
    total_fail = 0
    total_topics = 0
    success_accounts = 0
    
    for account_result in all_results:
        account = account_result['account']
        result = account_result['result']
        
        if result['success']:
            success_accounts += 1
            total_success += result['success_count']
            total_already_signed += result['already_signed_count']
            total_fail += result['fail_count']
            total_topics += result['total']
            
            print(f"✅ 账户{account}: 成功{result['success_count']} | 已签{result['already_signed_count']} | 失败{result['fail_count']} | 总计{result['total']}")
        else:
            error_msg = result.get('error', '未知错误')
            print(f"❌ 账户{account}: 执行失败 - {error_msg}")
    
    print("-" * 60)
    print(f"🎯 成功执行账户: {success_accounts}/{total_accounts}")
    print(f"✅ 总签到成功: {total_success} 个超话")
    print(f"⚠️  总已签过: {total_already_signed} 个超话")
    print(f"❌ 总签到失败: {total_fail} 个超话")
    print(f"📊 总处理超话: {total_topics} 个超话")
    
    # 执行结果判断
    if success_accounts > 0:
        print("🎉 批量签到任务执行完成！")
        if total_success > 0:
            print(f"🌟 本次新增签到 {total_success} 个超话")
    else:
        print("⚠️  所有账户均执行失败，请检查Cookie配置")
        sys.exit(1)
    
    print("=" * 60)

if __name__ == "__main__":
    # 开始时间记录
    start_time = time.time()
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行异常: {str(e)}")
        sys.exit(1)
    finally:
        # 结束时间统计
        end_time = time.time()
        duration = int(end_time - start_time)
        print(f"⏱️  总耗时: {duration} 秒")

