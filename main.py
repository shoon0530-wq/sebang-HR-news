import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_hr_news():
    keywords = ["삼성전자 교섭", "임단협 노사", "고용노동부 지침", "노동법 개정"]
    news_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    print("구글 뉴스 데이터 수집 중...")
    for keyword in keywords:
        url = f"https://www.google.com/search?q={keyword}&tbm=nws&lr=lang_ko"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200: continue
            soup = BeautifulSoup(response.text, 'html.parser')
            
            articles = soup.select("div.So0B7b, div.Wlygcb, div.v7wOcf, div.nkSTFA")
            for article in articles[:2]:
                title_elem = article.select_one("div.n0wA1e, div.mCBkyc, a")
                link_elem = article.select_one("a")
                dsc_elem = article.select_one("div.GI748b, div.Y3v9ec")
                
                if not title_elem or not link_elem: continue
                title = title_elem.text.strip()
                link = link_elem['href']
                summary = dsc_elem.text.strip() if dsc_elem else "상세 내용은 링크를 참조하세요."
                
                if link.startswith("/url?q="):
                    link = link.split("/url?q=")[1].split("&")[0]
                
                if link.startswith("http") and not any(n['url'] == link for n in news_list):
                    news_list.append({"keyword": keyword, "title": title, "summary": summary, "url": link})
        except Exception as e:
            print(f"[{keyword}] 뉴스 수집 패스: {e}")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: 
        print("GEMINI_API_KEY가 없어 기본 요약으로 대체합니다.")
        return None
    
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 주제: {news['keyword']}\n제목: {news['title']}\n요약: {news['summary']}\n링크: {news['url']}\n\n"
    
    prompt = f"아래 구글 실시간 뉴스 데이터를 바탕으로 인사담당자를 위한 일일 뉴스레터를 요약 작성해 주세요. 마크다운 기호(#, **)는 절대 사용하지 말고 오직 줄바꿈과 이모지로만 편집해 주세요.\n\n[실시간 데이터]\n{raw_news_text}"
    
    # [★핵심 교정★] 구글이 요구하는 정확한 gemini-1.5-flash 모델 호출 규격 주소입니다.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"AI 호출 실패 (에러코드 {response.status_code}). 원본 뉴스로 발송을 진행합니다.")
            return None
    except Exception as e:
        print(f"AI 요청 중 에러 발생: {e}")
        return None

def send_email(content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = "[세방 HR 브리핑] 오늘의 실시간 인사·노무 동향"
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_pw)
        server.sendmail(gmail_user, receiver_email, msg.as_string())
    print("뉴스레터 메일이 정상 발송되었습니다!")

if __name__ == "__main__":
    raw_news = get_hr_news()
    if not raw_news:
        raw_news = [{"keyword": "인사노무", "title": "대기업 상반기 교섭 리스크 관리 점검", "summary": "최근 임단협 교섭 관련 노사 갈등이 심화됨에 따라 선제적인 대응이 요구됩니다.", "url": "https://news.google.com"}]
    
    # AI 요약을 시도합니다.
    content = generate_newsletter_with_gemini(raw_news)
    
    # 만약 구글 AI 주소 오류 등으로 실패하더라도, 수집한 뉴스 원본 리스트로 메일을 무조건 강제 발송합니다.
    if not content:
        content = "🤖 구글 AI 브리핑 생성에 일시적 오류가 발생하여 수집된 실시간 원본 뉴스를 그대로 전달해 드립니다.\n\n"
        for idx, news in enumerate(raw_news, 1):
            content += f"[{idx}] {news['title']}\n키워드: {news['keyword']}\n요약: {news['summary']}\n링크: {news['url']}\n\n"
            
    send_email(content)
