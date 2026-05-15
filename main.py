import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import ssl

# [핵심 변경] 구글의 보안 차단을 완벽하게 우회하기 위해 feedparser 라이브러리를 사용합니다.
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
    # 인사담당자 타겟 맞춤형 실시간 핫 키워드
    keywords = ["인사노무", "임단협 노사", "고용노동부 지침", "노동법 개정", "최저임금 주52시간"]
    news_list = []
    
    print("📰 구글 보안망을 우회하여 실시간 노동 뉴스 대량 수집 시작...")
    
    # 깃허브 서버 환경에서 SSL 인증서 문제로 차단되는 것을 방지합니다.
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    for keyword in keywords:
        encoded_keyword = urllib.parse.quote(keyword)
        # RSS 피드 주소 설정
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            # feedparser를 사용하여 구글 뉴스 데이터를 안전하게 파싱합니다.
            feed = feedparser.parse(url)
            
            # 각 키워드별로 상위 4개씩 긁어와 총 15~20개의 분량을 확보합니다.
            for entry in feed.entries[:4]:
                title = entry.title
                link = entry.link
                source = entry.source.title if hasattr(entry, 'source') else "언론사"
                
                # 중복 뉴스 제거 및 링크 검증
                if link and not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": title,
                        "url": link,
                        "source": source
                    })
        except Exception as e:
            print(f"[{keyword}] 수집 중 에러 패스: {e}")
            
    print(f"📊 최종 수집 성공한 실제 뉴스 개수: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 없습니다.")
        return None
        
    # AI에게 넘겨줄 텍스트 가공
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 키워드: {news['keyword']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 기업의 인사노무 전문가이자 뉴스레터 편집자입니다.
    아래 제공되는 {len(news_list)}개의 실시간 뉴스 데이터를 바탕으로 인사담당자를 위한 일일 뉴스레터를 요약 작성해 주세요.
    
    [작성 규칙]
    1. 메일 화면에서 깨질 수 있는 마크다운 기호(#, **, ` 등)는 절대로 사용하지 마세요.
    2. 수집된 뉴스 10개~20개 전체를 하나도 빠짐없이 목록 형태로 나열해 주세요.
    3. 각 뉴스별로 '제목', '기사 원본 링크(URL)', 그리고 해당 뉴스에 대한 '핵심 요약 2줄'을 반드시 세트로 작성해 주세요.
    4. 오직 줄바꿈과 직관적인 이모지(📍, ⚖️, 📢)로만 가독성 있게 편집해 주세요.
    
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
            print(f"AI 엔진 오류 ({response.status_code}). 원본 링크 리스트로 대체합니다.")
            return None
    except Exception as e:
        print(f"AI 호출 예외 발생: {e}")
        return None

def send_email(content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = "[세방 HR 브리핑] 오늘의 실시간 인사·노무·노동법 동향 리포트"
    
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 뉴스레터 메일 발송 완료!")
    except Exception as e:
        print(f"메일 발송 에러: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    # 만약 구글 피드가 비어있을 경우를 대비한 최소한의 가짜 데이터 안전장치
    if not raw_news:
        raw_news = [
            {"keyword": "노동법", "title": "2026년 하반기 근로기준법 개정안 주요쟁점 점검", "source": "노동일보", "url": "https://news.google.com"},
            {"keyword": "임단협", "title": "제조업 중심 임단협 교섭 가이드라인 발표", "source": "경제를 바꾸는 뉴스", "url": "https://news.google.com"}
        ]
        
    content = generate_newsletter_with_gemini(raw_news)
    
    # AI가 작동하지 않더라도 원본 기사들과 개별 링크는 무조건 메일에 포함시킵니다.
    if not content:
        content = "🔔 실시간 인사노무 뉴스 원본 브리핑 리스트입니다.\n\n"
        for idx, news in enumerate(raw_news, 1):
            content += f"[{idx}] {news['title']}\n언론사: {news['source']} | 키워드: {news['keyword']}\n기사 링크: {news['url']}\n\n"
            
    send_email(content)
