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
    keywords = [
        "노란봉투법", 
        "삼성전자 노사", 
        "근로기준법 개정 국회", 
        "대기업 임단협 파업", 
        "고용노동부 장관 지침",
        "인사노무 트렌드"
    ]
    news_list = []
    
    # [핵심 교정] 기업명뿐만 아니라 주요 대형 이슈 키워드까지 카운팅하는 통합 딕셔너리
    issue_counts = {}
    
    print("📰 기업 및 시사 이슈별 중복 제거(최대 2개 제한) 필터링 시작...")
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    now = datetime.now()
    three_days_ago = now - timedelta(days=3)
        
    for keyword in keywords:
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                source = entry.source.title if hasattr(entry, 'source') else "언론사"
                
                # 1. 날짜 필터링 (최근 3일 이내)
                is_recent = True
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_dt < three_days_ago:
                        is_recent = False
                
                if not is_recent or not link:
                    continue
                    
                clean_title = title.split(" - ")[0].strip()
                
                # 2. [강력한 필터링] 특정 단어가 제목에 포함되어 있다면 동일 이슈군으로 묶어 버립니다.
                issue_key = clean_title[:4].replace(" ", "") # 기본 키값
                
                # 체크할 메이저 이슈 및 기업 리스트
                macro_topics = [
                    "노란봉투법", "노란봉투", "삼성전자", "삼성", "근로기준법", 
                    "최저임금", "주52시간", "임단협", "파업", "노동부", "금호타이어", "KAI"
                ]
                
                for topic in macro_topics:
                    if topic in clean_title:
                        issue_key = topic
                        break
                
                # 해당 이슈나 기업이 이미 메일 리스트에 2개 이상 들어있다면 무조건 패스(탈락)
                if issue_counts.get(issue_key, 0) >= 2:
                    continue
                
                # 중복 링크 검증 후 추가
                if not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": clean_title,
                        "url": link,
                        "source": source
                    })
                    # 카운트 누적
                    issue_counts[issue_key] = issue_counts.get(issue_key, 0) + 1
                    
                if len(news_list) >= 15:
                    break
        except Exception as e:
            print(f"[{keyword}] 뉴스 파싱 중 스킵: {e}")
            
    print(f"📊 최종 필터링을 통과한 균형 잡힌 뉴스 개수: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 토픽: {news['keyword']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대기업의 수석 인사노무 전문가이자 뉴스레터 편집자입니다.
    아래 제공되는 {len(news_list)}개의 최신 메이저 뉴스 데이터를 바탕으로 경영진 및 인사담당자를 위한 데일리 리포트를 작성해 주세요.
    다양한 주제가 골고루 섞여 있으니, 각 주제의 맥락을 살려 깔끔하게 요약해야 합니다.
    
    [핵심 작성 규칙]
    1. 답변은 반드시 아래의 포맷 양식으로만 구성해야 하며, 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 각 기사에 대해 날카롭고 명확한 핵심 요약 요점을 정확히 2줄로 작성해 주세요.
    3. 각 기사 본문 작성이 끝나면 다음 기사로 넘어가기 전에 [구분자] 코드를 반드시 적어주세요.
    
    [출력 양식 예시]
    언론사이름 | 기사제목
    • 첫 번째 요약 문장입니다.
    • 두 번째 요약 문장입니다.
    기사링크주소
    [구분자]
    
    [실시간 메이저 뉴스 데이터]
    {raw_news_text}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
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
    <div style="background-color: #f8fafc; padding: 0px 10px 40px 10px; font-family: 'Malgun Gothic', sans-serif; color: #334155; line-height: 1.6; margin: 0;">
        <div style="max-width: 620px; margin: 0 auto; padding-top: 15px;">
            
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 28px 20px; text-align: center; border-radius: 12px; color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 20px;">
                <span style="display: inline-block; background: rgba(255,255,255,0.15); padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 6px; color: #ffffff;">EXECUTIVE HR BRIEFING</span>
                <h1 style="margin: 0px 0 4px 0; font-size: 25px; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;">세방 HR 브리핑</h1>
                <p style="margin: 0; font-size: 13px; opacity: 0.85; font-weight: 300; color: #ffffff;">{today_str} 주요 인사·노무 및 시사 트렌드 동향</p>
            </div>
            
            <div style="padding: 0px 0;">
    """
    
    try:
        if ai_content and "[구분자]" in ai_content:
            articles = ai_content.strip().split("[구분자]")
            for article in articles:
                lines = [line.strip() for line in article.strip().split('\n') if line.strip()]
                if len(lines) >= 3:
                    header_line = lines[0]
                    link_line = lines[-1]
                    summary_lines = lines[1:-1]
                    
                    source_name = "종합이슈"
                    title_name = header_line
                    if "|" in header_line:
                        source_name, title_name = header_line.split("|", 1)
                    
                    summary_html = ""
                    for sl in summary_lines:
                        summary_html += f"<li style='margin-bottom: 6px;'>{sl.replace('•', '').strip()}</li>"
                    
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #2563eb; padding: 22px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: #eff6ff; color: #2563eb; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold; line-height: 1.4;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 18px 0; padding-left: 20px; font-size: 14px; color: #475569;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #1e40af; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                        </div>
                    </div>
                    """
        else:
            raise Exception("Fallback Trigger")
    except Exception:
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #64748b; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{news['source']}</span>
                <h3 style="margin: 8px 0 14px 0; font-size: 15px; color: #1e293b; font-weight: bold;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="color: #2563eb; font-size: 13px; font-weight: bold; text-decoration: none;">기사 원문 보기 →</a>
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
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 주요 시사 및 인사노무 종합 리포트"
    
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 이슈별 중복제거가 완벽 조율된 뉴스레터 발송 완료!")
    except Exception as e:
        print(f"메일 발송 오류: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    if not raw_news:
        raw_news = [
            {"keyword": "시사이슈", "title": "주요 대기업 하반기 임단협 주요 쟁점 조율 및 정부 지침 전달", "source": "노동일보", "url": "https://news.google.com"}
        ]
        
    ai_content = generate_newsletter_with_gemini(raw_news)
    final_html = build_html_template(ai_content, raw_news)
    send_email(final_html)
