import os
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# GitHub Secrets에 등록한 정보들을 가져옵니다.
CONFIG = {
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "GMAIL_USER": os.getenv("GMAIL_USER"),
    "GMAIL_APP_PW": os.getenv("GMAIL_APP_PW"),
    "RECEIVER_EMAIL": os.getenv("RECEIVER_EMAIL"),
}

def fetch_hr_news():
    print("네이버 뉴스에서 인사/노무 관련 최신 정보를 수집합니다...")
    search_url = "https://search.naver.com/search.naver?where=news&query=인사노무%20법령%20판례"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    try:
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = []
        # 상위 15개의 뉴스 제목과 링크 추출
        articles = soup.select('.news_tit')[:15]
        
        for article in articles:
            news_items.append({
                "title": article.get_text(),
                "link": article['href']
            })
        return news_items
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")
        return []

def get_ai_summary(news_list):
    print("Gemini AI를 사용하여 뉴스별 한 줄 요약을 생성합니다...")
    if not CONFIG["GEMINI_API_KEY"]:
        print("에러: GEMINI_API_KEY가 설정되지 않았습니다.")
        return []

    genai.configure(api_key=CONFIG["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    summarized_news = []
    
    for item in news_list:
        # 인사담당자 관점에서의 요약 프롬프트
        prompt = f"너는 노무법인 소속 전문가야. 인사담당자가 아래 뉴스를 읽었을 때 핵심이 무엇인지 '음'체나 '함'체로 딱 한 줄로 요약해줘: {item['title']}"
        try:
            response = model.generate_content(prompt)
            summary = response.text.strip()
        except Exception:
            summary = "요약을 생성할 수 없습니다."
        
        summarized_news.append({
            "title": item['title'],
            "link": item['link'],
            "summary": summary
        })
    return summarized_news

def create_html_content(news_data):
    today = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    items_html = ""
    
    for idx, item in enumerate(news_data, 1):
        items_html += f"""
        <div style="margin-bottom: 25px; padding: 15px; border-left: 5px solid #004a99; background-color: #f8f9fa; border-radius: 0 5px 5px 0;">
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px;">
                <span style="color: #004a99;">{idx}.</span> 
                <a href="{item['link']}" style="color: #333; text-decoration: none;">{item['title']}</a>
            </div>
            <div style="font-size: 14px; color: #555; line-height: 1.6;">
                <strong style="color: #e67e22;">[AI 요약]</strong> {item['summary']}
            </div>
        </div>
        """

    return f"""
    <html>
    <body style="margin: 0; padding: 0; font-family: 'Malgun Gothic', dotum, sans-serif;">
        <div style="max-width: 600px; margin: 20px auto; border: 1px solid #e0e0e0;">
            <div style="background-color: #004a99; color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">세방(SEBANG) 인사 노무 뉴스레터</h1>
                <p style="margin: 10px 0 0; opacity: 0.8;">{today} 데일리 브리핑</p>
            </div>
            <div style="padding: 20px;">
                <p style="font-size: 15px; color: #666; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                    오늘의 주요 인사/노무 관련 소식을 AI 요약과 함께 전달드립니다.
                </p>
                {items_html}
            </div>
            <div style="background-color: #f1f1f1; padding: 20px; text-align: center; font-size: 12px; color: #888;">
                본 메일은 시스템에 의해 자동 발송되었습니다.<br>
                문의: 인사팀 자동화 담당자
            </div>
        </div>
    </body>
    </html>
    """

def send_email(html_body):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if not CONFIG["GMAIL_USER"] or not CONFIG["GMAIL_APP_PW"]:
        print("에러: 메일 설정 정보가 부족합니다.")
        return

    msg = MIMEMultipart()
    msg['Subject'] = f'세방 인사 노무 뉴스레터 ({today})'
    msg['From'] = f"세방 인사 자동화 <{CONFIG['GMAIL_USER']}>"
    msg['To'] = CONFIG["RECEIVER_EMAIL"]
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        # 보안 연결(SSL)을 사용하여 메일 발송
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(CONFIG["GMAIL_USER"], CONFIG["GMAIL_APP_PW"])
            server.send_message(msg)
        print(f"성공: {today} 뉴스레터가 {CONFIG['RECEIVER_EMAIL']}로 발송되었습니다.")
    except Exception as e:
        print(f"실패: 메일 발송 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    raw_news = fetch_hr_news()
    if raw_news:
        processed_news = get_ai_summary(raw_news)
        html_content = create_html_content(processed_news)
        send_email(html_content)
    else:
        print("수집된 뉴스가 없어 발송을 중단합니다.")