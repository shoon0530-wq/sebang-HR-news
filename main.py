import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import ssl
from datetime import datetime, timedelta
import time

try:
    import feedparser
except ImportError:
    os.system('pip install feedparser')
    import feedparser

try:
    import requests
except ImportError:
    os.system('pip install requests')
    import requests

def get_hr_news():
    # 🔍 수동 키워드를 전부 제거하고, 대한민국 인사/노무 전반을 아우르는 '그물망 검색어' 하나로 통일합니다.
    # 구글이 실시간으로 그날의 가장 핫한 HR 뉴스를 알아서 정렬해 줍니다.
    broad_query = '"인사노무" OR "인사담당자" OR "근로기준법" OR "고용노동부" OR "노동법" OR "조직문화"'
    
    encoded_keyword = urllib.parse.quote(broad_query)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    news_list = []
    
    # 🚫 [동적 이슈 쏠림 방지 장치] 
    # 특정 단어가 포함된 기사가 뉴스레터 전체에서 2개를 넘지 못하도록 실시간으로 감시하는 카운터입니다.
    issue_keywords = ["파업", "노란봉투", "임단협", "성과급", "삼성전자", "연말정산", "종합소득세"]
    issue_counts = {word: 0 for word in issue_keywords}
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    now = datetime.now()
    # 주말 공백 및 기사 고갈을 막기 위해 항상 7일간의 넉넉한 데이터를 스캔합니다.
    time_limit = now - timedelta(days=7)
    
    print("📰 [실시간 HR 트렌드 스캐닝] 특정 이슈 쏠림 감지 및 동적 필터링 시작...")
    
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            # 최종 뉴스레터에는 가장 신선하고 퀄리티 높은 기사 12~15개 안팎을 조화롭게 담습니다.
            if len(news_list) >= 15:
                break
                
            title = entry.title
            link = entry.link
            source = entry.source.title if hasattr(entry, 'source') else "언론사"
            
            # 날짜 필터링
            is_recent = True
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                if pub_dt < time_limit:
                    is_recent = False
            
            if not is_recent or not link:
                continue
                
            clean_title = title.split(" - ")[0].strip()
            if " < " in clean_title:
                clean_title = clean_title.split(" < ")[0].strip()
            
            # 💡 [핵심] 특정 시사 이슈가 너무 몰려있는지 검사 (최대 2개 제한 규칙 적용)
            skip_this_article = False
            for word in issue_keywords:
                if word in clean_title:
                    if issue_counts[word] >= 2:
                        skip_this_article = True  # 이미 해당 이슈 기사가 2개 차서 이 기사는 버립니다.
                        break
            
            if skip_this_article:
                continue
                
            # 중복 기사가 아니라면 최종 리스트에 추가
            if not any(n['url'] == link for n in news_list):
                news_list.append({
                    "title": clean_title,
                    "url": link,
                    "source": source
                })
                
                # 감시 카운터 증가
                for word in issue_keywords:
                    if word in clean_title:
                        issue_counts[word] += 1
                        
                print(f"   ✅ [수집 성공] {source} | {clean_title[:28]}...")
                
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")
        
    print(f"📊 이슈 편중 없이 최종 조율된 실시간 뉴스 총합: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대기업의 수석 인사노무 전문가이자 뉴스레터 편집자입니다.
    아래 제공되는 실시간 뉴스 데이터를 바탕으로 경영진을 위한 종합 데일리 리포트를 작성해 주세요.
    특정 속보에 편중되지 않고 인사 제도, 노동법, 채용 트렌드 등이 골고루 섞여 있으니 이 결을 그대로 살려 작성해야 합니다.
    
    [핵심 작성 규칙]
    1. 답변은 반드시 아래의 포맷 양식으로만 구성해야 하며, 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 각 기사에 대해 날카롭고 명확한 핵심 요점을 정확히 2줄(불릿포인트)로 작성해 주세요.
    3. 각 기사 본문 작성이 끝나면 다음 기사로 넘어가기 전에 [구분자] 코드를 반드시 새 행에 적어주세요.
    
    [출력 양식 예시]
    언론사이름 | 기사제목
    • 첫 번째 요약 문장입니다.
    • 두 번째 요약 문장입니다.
    기사링크주소
    [구분자]
    
    [실시간 뉴스 데이터]
    {raw_news_text}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=40)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return None
    except Exception as e:
        print(f"AI 호출 오류: {e}")
        return None

def build_html_template(ai_content, raw_news):
    today_str = datetime.now().strftime('%Y년 %m월 %d일')
    
    html_body = f"""
    <div style="background-color: #f8fafc; padding: 20px 10px 40px 10px; font-family: 'Malgun Gothic', sans-serif; color: #334155; line-height: 1.6; margin: 0;">
        <div style="max-width: 620px; margin: 0 auto;">
            
            <div style="background-color: #0f172a; padding: 30px 20px; text-align: center; border-radius: 12px; color: #ffffff; margin-bottom: 20px;">
                <span style="display: inline-block; background-color: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; margin-bottom: 8px; color: #ffffff;">EXECUTIVE HR BRIEFING</span>
                <h1 style="margin: 0px 0 6px 0; font-size: 26px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">세방 HR 브리핑</h1>
                <p style="margin: 0; font-size: 13px; color: #ffffff; opacity: 0.85; font-weight: 300;">{today_str} 주요 인사·노무 및 시사 트렌드 동향</p>
            </div>
            
            <div style="padding: 0px 0;">
    """
    
    try:
        if ai_content and "[구분자]" in ai_content:
            articles = ai_content.strip().split("[구분자]")
            valid_count = 0
            
            for article in articles:
                lines = [line.strip() for line in article.strip().split('\n') if line.strip()]
                if len(lines) >= 3:
                    header_line = lines[0]
                    link_line = lines[-1]
                    summary_lines = lines[1:-1]
                    
                    if not link_line.startswith("http"):
                        continue
                        
                    source_name = "실시간 트렌드"
                    title_name = header_line
                    if "|" in header_line:
                        source_name, title_name = header_line.split("|", 1)
                    
                    summary_html = ""
                    for sl in summary_lines:
                        clean_sl = sl.replace('•', '').replace('-', '').strip()
                        if clean_sl:
                            summary_html += f"<li style='margin-bottom: 6px;'>{clean_sl}</li>"
                    
                    if not summary_html:
                        continue
                        
                    valid_count += 1
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #2563eb; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: #eff6ff; color: #2563eb; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 18px 0; padding-left: 20px; font-size: 14px; color: #475569;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #1e40af; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                        </div>
                    </div>
                    """
            
            if valid_count == 0:
                raise Exception("Fallback Trigger")
        else:
            raise Exception("Fallback Trigger")
            
    except Exception:
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #475569; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                <div style="margin-bottom: 10px;">
                    <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{news['source']}</span>
                </div>
                <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="display: inline-block; background-color: #64748b; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                </div>
            </div>
            """
            
    html_body += """
            </div>
            
            <div style="margin-top: 10px; padding: 25px; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #e2e8f0;">
                본 메일은 사내 인사 정보 참고 목적으로 생성형 AI 엔진을 통해 자동 발송되었습니다.<br>
                <strong style="color: #64748b;">© 2026 SEBANG HR Automation. All Rights Reserved.</strong>
            </div>
            
        </div>
    </div>
    """
    return html_body

def send_email(html_content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_raw = os.environ.get("RECEIVER_EMAIL")
    
    if not receiver_raw:
        print("❌ RECEIVER_EMAIL 설정이 비어있습니다.")
        return
        
    receiver_list = [email.strip() for email in receiver_raw.split(",") if email.strip()]
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            for receiver_email in receiver_list:
                msg = MIMEMultipart()
                msg['From'] = gmail_user
                msg['To'] = receiver_email
                msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 주요 시사 및 인사노무 종합 리포트"
                
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                server.sendmail(gmail_user, receiver_email, msg.as_string())
                print(f"📩 {receiver_email} 발송 완료!")
                
        print("🚀 모든 수신자에게 뉴스레터 발송 완료!")
    except Exception as e:
        print(f"메일 발송 오류: {e}")

if __name__ == "__main__":
    try:
        raw_news = get_hr_news()
        
        if not raw_news:
            print("⚠️ 새로운 뉴스 기사가 없습니다.")
            today_str = datetime.now().strftime('%Y년 %m월 %d일')
            no_news_html = f"""
            <div style="background-color: #f8fafc; padding: 40px 20px; font-family: 'Malgun Gothic', sans-serif; text-align: center;">
                <div style="max-width: 620px; margin: 0 auto; background: #ffffff; padding: 35px 30px; border-radius: 12px; border-top: 5px solid #64748b; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                    <h2 style="color: #1e293b; margin-top: 0; font-size: 20px;">세방 HR 브리핑 시스템 알림</h2>
                    <p style="font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 20px;">
                        안녕하세요. 오늘({today_str}) 인사노무 분야에<br>
                        <strong>새로 발행된 주요 시사 트렌드 기사가 발견되지 않았습니다.</strong>
                    </p>
                </div>
            </div>
            """
            send_email(no_news_html)
        else:
            ai_content = generate_newsletter_with_gemini(raw_news)
            final_html = build_html_template(ai_content, raw_news)
            send_email(final_html)
            
    except Exception as main_error:
        print(f"❌ 시스템 치명적 오류 발생: {main_error}")
