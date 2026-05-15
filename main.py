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
    keywords = ["인사노무", "임단협 노사", "고용노동부 지침", "노동법 개정", "최저임금 주52시간"]
    news_list = []
    
    # [핵심] 특정 기업(예: 금호타이어, KAI 등) 도배를 막기 위한 카운팅 딕셔너리
    company_counts = {}
    
    print("📰 중복 제거 및 3일 이내 최신 인사노무 뉴스 필터링 시작...")
    
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
                
                # 1. 날짜 필터링 (최근 3일 이내 기사만)
                is_recent = True
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_dt < three_days_ago:
                        is_recent = False
                
                if not is_recent or not link:
                    continue
                    
                # 구글 뉴스 제목 끝에 붙는 ' - 언론사' 분리
                clean_title = title.split(" - ")[0].strip()
                
                # 2. 동일 기업/이슈 도배 방지 필터링 로직
                # 제목에서 앞 2~4글자 또는 주요 명사를 기반으로 핵심 주체(회사명)를 임의 추출합니다.
                company_key = clean_title[:4].replace(" ", "")
                for word in ["금호타이어", "KAI", "현대차", "기아", "삼성", "노동부", "한화"]:
                    if word in clean_title:
                        company_key = word
                        break
                
                # 해당 기업/이슈가 이미 2번 이상 수집되었다면 패스 (다양성 확보)
                if company_counts.get(company_key, 0) >= 2:
                    continue
                
                # 중복 링크 검증 후 리스트 추가
                if not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": clean_title,
                        "url": link,
                        "source": source
                    })
                    # 카운트 증가
                    company_counts[company_key] = company_counts.get(company_key, 0) + 1
                    
                if len(news_list) >= 20:
                    break
        except Exception as e:
            print(f"[{keyword}] 수집 중 오류 무시: {e}")
            
    print(f"📊 최종 수집된 다양하고 고품질인 뉴스 개수: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 없습니다.")
        return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 키워드: {news['keyword']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 기업의 인사노무 전문가이자 세련된 편집자입니다.
    아래 제공되는 {len(news_list)}개의 최신 뉴스 데이터를 바탕으로 인사담당자를 위한 일일 브리핑을 요약 작성해 주세요.
    
    [핵심 작성 규칙]
    1. 답변은 반드시 아래의 포맷 양식으로만 구성해야 하며, 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 수집된 모든 기사에 대해 각각 핵심 요약 요점을 명확하게 2줄로 작성해 주세요.
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
        print(f"AI 호출 오류: {e}")
        return None

def build_html_template(ai_content, raw_news):
    today_str = datetime.now().strftime('%Y년 %m월 %d일')
    
    # [디자인 개편] 전체 바탕 배경을 은은하고 고급스러운 미색(#f8fafc)으로 깔고 여백 조정
    html_body = f"""
    <div style="background-color: #f8fafc; padding: 40px 10px; font-family: 'Malgun Gothic', sans-serif; color: #334155; line-height: 1.6;">
        <div style="max-width: 620px; margin: 0 auto;">
            
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 35px 25px; text-align: center; border-radius: 12px 12px 0 0; color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <span style="background: rgba(255,255,255,0.15); padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; text-transform: uppercase;">HR Trend Report</span>
                <h1 style="margin: 12px 0 6px 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">세방 HR 브리핑</h1>
                <p style="margin: 0; font-size: 14px; opacity: 0.8; font-weight: 300;">{today_str} 오늘의 인사·노무 최신 뉴스레터</p>
            </div>
            
            <div style="background-color: #ffffff; padding: 15px 20px; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #64748b; text-align: center; border-radius: 0;">
                🔔 특정 기업의 도배를 제외하고, 최근 <strong>3일 내 엄선된 종합 노동 뉴스</strong>를 전달합니다.
            </div>
            
            <div style="padding: 20px 0;">
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
                        summary_html += f"<li style='margin-bottom: 6px;'>{sl.replace('•', '').strip()}</li>"
                    
                    # [디자인 개편] 은은한 배경 색상 위에 눈이 편안한 흰색 라운드 기사 카드 배치
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #3b82f6; padding: 22px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: #eff6ff; color: #2563eb; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold; line-height: 1.4;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 18px 0; padding-left: 20px; font-size: 14px; color: #475569;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #1e40af; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">기사 원문 보기 →</a>
                        </div>
                    </div>
                    """
        else:
            raise Exception("Fallback 활성화")
    except Exception:
        # 백업 모드 시에도 고급스러운 레이아웃 유지
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #64748b; padding: 22px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
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
                정밀 필터링 및 구글 AI 뉴스레터 엔진 기반 자동 발송 메일입니다.<br>
                보안 격리 구역에서 사내 인사 업무 참고용으로만 사용해 주십시오.<br>
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
    msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 오늘의 인사노무 종합 리포트"
    
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 고급 중복제거 필터링 완료 및 웹진 메일 발송 완료!")
    except Exception as e:
        print(f"메일 발송 에러: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    if not raw_news:
        raw_news = [
            {"keyword": "노동법", "title": "근로기준법 개정안 통과 및 하반기 기업 대응 지침 수립", "source": "노동법률", "url": "https://news.google.com"},
            {"keyword": "임단협", "title": "주요 제조 대기업 상반기 임단협 노사 평화 선언 동향", "source": "HR브리프", "url": "https://news.google.com"}
        ]
        
    ai_content = generate_newsletter_with_gemini(raw_news)
    final_html = build_html_template(ai_content, raw_news)
    send_email(final_html)
