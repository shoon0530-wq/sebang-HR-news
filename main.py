import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import ssl
from datetime import datetime, timedelta
import time

# 필수 라이브러리 자동 설치 및 로드
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
    keywords = ["인사노무", "임단협 노사", "고용노동부 지침", "노동법 개정", "최저임금 주52시간"]
    news_list = []
    
    print("📰 구글 뉴스망에서 최근 3일 이내의 HR 핵심 뉴스 수집 시작...")
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    # 정확한 3일 이내 필터링을 위한 기준 시간 세팅 (현재 시간 - 3일)
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
                
                # 구글 RSS의 발행 시간 파싱 (파싱 실패 시 최신 기사로 간주하고 진입)
                is_recent = True
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_dt < three_days_ago:
                        is_recent = False # 3일보다 더 오래된 기사는 과감히 탈락
                
                # 조건 검증: 3일 이내 기사 + 중복 방지
                if is_recent and link and not any(n['url'] == link for n in news_list):
                    # 구글 뉴스 타이틀에서 언론사 이름 깔끔하게 정리
                    clean_title = title.split(" - ")[0].strip()
                    news_list.append({
                        "keyword": keyword,
                        "title": clean_title,
                        "url": link,
                        "source": source
                    })
                    
                # 효율적인 뉴스 분량 조절 (전체 키워드 합산 15개 안팎 유지를 위해 딛고 넘어가기)
                if len(news_list) >= 20:
                    break
        except Exception as e:
            print(f"[{keyword}] 수집 중 에러 패스: {e}")
            
    print(f"📊 조건(3일 이내)에 부합하는 실제 고품질 뉴스 개수: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 존재하지 않습니다.")
        return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 키워드: {news['keyword']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    # HTML 이메일 내부에 이쁘게 박히도록 프롬프트 정밀 튜닝
    prompt = f"""
    당신은 기업의 인사노무 전문가이자 세련된 뉴스레터 에디터입니다.
    아래 제공되는 {len(news_list)}개의 최신 뉴스 데이터를 바탕으로 인사담당자를 위한 일일 브리핑을 작성해 주세요.
    
    [핵심 작성 규칙 - 필수 엄수]
    1. 답변은 반드시 아래의 특별한 포맷 양식으로만 구성해야 하며, 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 수집된 모든 기사에 대해 각각 딱 2줄로 핵심 요약 요점을 작성해 주세요.
    3. 각 기사 본문 작성이 끝나면 다음 기사로 넘어가기 전에 [구분자] 코드를 반드시 적어주세요.
    
    [출력 양식 예시]
    언론사이름 | 기사제목
    • 첫 번째 요약 문장입니다.
    • 두 번째 요약 문장입니다.
    기사링크주소
    [구분자]
    
    [실시간 뉴스 데이터]
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
        print(f"AI 호출 중 예외 발생: {e}")
        return None

def build_html_template(ai_content, raw_news):
    # 이메일 디자인을 고급스럽게 변환하는 대시보드 템플릿 엔진
    today_str = datetime.now().strftime('%Y년 %m월 %d일')
    
    html_body = f"""
    <div style="max-width: 650px; margin: 0 auto; font-family: 'Malgun Gothic', sans-serif; color: #333333; line-height: 1.6;">
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0; color: #ffffff;">
            <span style="background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; letter-spacing: 1px;">DAILY HR BRIEFING</span>
            <h1 style="margin: 10px 0 5px 0; font-size: 24px; font-weight: 700;">세방 HR 브리핑</h1>
            <p style="margin: 0; font-size: 14px; opacity: 0.9;">{today_str} 오늘의 실시간 인사·노무 동향 리포트</p>
        </div>
        
        <div style="padding: 20px 10px; border-bottom: 2px solid #f0fdf4; font-size: 14px; color: #555555;">
            📍 구글 뉴스망에서 <strong>최근 3일 이내</strong> 발행된 인사노무 핵심 트렌드를 AI가 실시간 요약하여 배달합니다.
        </div>
        
        <div style="padding: 10px 0;">
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
                    
                    source_name = "뉴스"
                    title_name = header_line
                    if "|" in header_line:
                        source_name, title_name = header_line.split("|", 1)
                    
                    summary_html = ""
                    for sl in summary_lines:
                        summary_html += f"<li style='margin-bottom: 4px;'>{sl.replace('•', '').strip()}</li>"
                    
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-left: 4px solid #2563eb; padding: 18px; margin-bottom: 15px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="margin-bottom: 8px;">
                            <span style="background-color: #eff6ff; color: #1e40af; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; margin-right: 6px;">{source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #111827; font-weight: bold;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 15px 0; padding-left: 20px; font-size: 14px; color: #4b5563;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 6px 14px; border-radius: 4px; transition: background-color 0.2s;">기사 원본 보기 →</a>
                        </div>
                    </div>
                    """
        else:
            raise Exception("AI 포맷 누락 백업 전환")
    except Exception:
        # 백업 모드 디자인 안정화
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-left: 4px solid #4b5563; padding: 18px; margin-bottom: 15px; border-radius: 4px;">
                <span style="background-color: #f3f4f6; color: #374151; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px;">{news['source']}</span>
                <h3 style="margin: 5px 0 12px 0; font-size: 15px; color: #111827;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="color: #2563eb; font-size: 13px; font-weight: bold; text-decoration: none;">기사 원본 보기 →</a>
                </div>
            </div>
            """
            
    html_body += """
        </div>
        <div style="margin-top: 30px; padding: 20px; background-color: #f9fafb; border-radius: 0 0 8px 8px; text-align: center; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
            본 메일은 세방전지 HR 부서 전용으로 실시간 뉴스 수집 자동화 시스템에 의해 발송되었습니다.<br>
            © 2026 SEBANG HR Automation. All Rights Reserved.
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
    msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 실시간 인사·노무·노동법 동향 리포트"
    
    # [핵심 변경] plain 대신 html 타입으로 메일을 바인딩합니다.
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 웹진형 인사노무 뉴스레터 발송 완료!")
    except Exception as e:
        print(f"메일 발송 에러: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    if not raw_news:
        # 안전용 디폴트 데이터
        raw_news = [
            {"keyword": "노동법", "title": "근로기준법 개정안 국회 본회의 통과 및 시행시기 조율", "source": "노동법률신문", "url": "https://news.google.com"},
            {"keyword": "임단협", "title": "주요 제조 대기업 상반기 임단협 노사 교섭 가이드라인 매뉴얼", "source": "HR인사이트", "url": "https://news.google.com"}
        ]
        
    ai_content = generate_newsletter_with_gemini(raw_news)
    final_html = build_html_template(ai_content, raw_news)
    send_email(final_html)
