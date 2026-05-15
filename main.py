import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 네이버 뉴스 검색 및 수집
# ==========================================
def get_hr_news():
    keywords = ["인사노무", "노사교섭", "임단협", "고용노동부 지침", "노동법 개정"]
    news_list = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    print("인사/노무 핵심 키워드로 네이버 최신 뉴스를 수집합니다...")

    for keyword in keywords:
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_smr&sort=1"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select("ul.list_news > li.bx")
            
            for article in articles[:4]:
                title_elem = article.select_one("a.news_tit")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                link = title_elem['href']
                
                dsc_elem = article.select_one("div.news_dsc")
                summary = dsc_elem.text.strip() if dsc_elem else ""
                
                if not any(item['url'] == link for item in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": title,
                        "url": link,
                        "summary": summary
                    })
        except Exception as e:
            print(f"[{keyword}] 검색 중 사소한 오류 발생 (패스): {e}")
            
    return news_list

# ==========================================
# 2. 라이브러리 버그를 우회하는 API 직접 호출 방식 (REST API)
# ==========================================
def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 키워드: {news['keyword']}\n제목: {news['title']}\n요약원문: {news['summary']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대한민국 최고의 기업 인사노무 전문가이자 CHO 전담 비서입니다.
    아래 수집된 최신 뉴스 데이터들을 바탕으로, 오늘 아침 기업 경영진과 인사팀이 반드시 읽고 선제 대응해야 할 '일일 HR 뉴스레터'를 작성해 주세요.

    [수집된 뉴스 데이터]
    {raw_news_text}

    [작성 가이드라인]
    1. 제목은 세련되고 전문적인 인사 브리핑 형태로 작성해 주세요 (예: "[세방 HR 브리핑] 오늘의 주요 인사·노무 동향")
    2. 뉴스들을 단순 나열하지 말고 중요도나 주제별로 2~3개의 그룹으로 묶어서 정리해 주세요.
    3. 각 뉴스 요약 끝에는 인사담당자가 주목해야 할 '실무적 시사점 또는 대응 팁'을 1~2줄씩 덧붙여 주세요.
    4. 메일 본문에서 글자가 깨지지 않도록 마크다운 기호(예: **, #)는 절대 사용하지 마세요. 일반 줄바꿈과 이모지만 사용하여 가독성을 높여주세요.
    """
    
    # 구글 라이브러리를 쓰지 않고, 가장 확실하고 주소가 고정된 구글 공식 REST API 포트를 직접 때립니다.
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    print("라이브러리 우회형 포트를 통해 Gemini 뉴스레터를 직접 안전하게 생성 중입니다...")
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        result_json = response.json()
        try:
            return result_json['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexErrors) as e:
            raise RuntimeError(f"구글 응답 파싱 실패: {result_json}")
    else:
        raise RuntimeError(f"구글 AI 서버 호출 실패 (에러코드 {response.status_code}): {response.text}")

# ==========================================
# 3. 구글 SMTP 서버를 통한 뉴스레터 메일 발송
# ==========================================
def send_email(content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not all([gmail_user, gmail_pw, receiver_email]):
        raise ValueError("메일 발송 관련 보안 키(Secrets) 설정을 다시 확인해 주세요.")
        
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = f"[세방 HR 뉴스레터] 오늘의 주요 인사·노무 동향"
    
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    print("구글 SMTP 서버에 접속하여 메일을 발송합니다...")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_pw)
        server.sendmail(gmail_user, receiver_email, msg.as_string())
    print("뉴스레터 메일 발송 완벽하게 성공!")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    if not raw_news:
        print("네이버 실시간 검색 차단 또는 검색 데이터 부재로 인해 기본 모드로 전환합니다.")
        raw_news = [{
            "keyword": "인사노무 기본동향",
            "title": "주요 대기업 노사 교섭 및 상반기 임단협 집중 모니터링 필요성",
            "summary": "최근 대기업들을 중심으로 임금 인상률 조율 및 노사 성과급 배분 갈등이 심화되고 있어, 인사팀의 실시간 동향 모니터링과 선제적 리스크 관리가 요구됩니다.",
            "url": "https://news.naver.com"
        }]
        
    newsletter_content = generate_newsletter_with_gemini(raw_news)
    send_email(newsletter_content)
