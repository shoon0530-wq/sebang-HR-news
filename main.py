import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 네이버 뉴스 검색 및 수집 (인사/노무 타겟 최적화)
# ==========================================
def get_hr_news():
    # 인사담당자에게 꼭 필요한 '실전형 핵심 키워드'들을 조합하여 검색합니다.
    keywords = ["인사노무", "노사교섭", "임단협", "고용노동부 지침", "노동법 개정"]
    news_list = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    print("확장된 인사/노무 핵심 키워드로 네이버 최신 뉴스를 수집합니다...")

    for keyword in keywords:
        # 네이버 뉴스 '최신순(sort=1)'으로 정렬하여 검색 주소 생성
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_smr&sort=1"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            # 네이버 뉴스 검색 결과 문서 구조 분석 타겟팅
            articles = soup.select("ul.list_news > li.bx")
            
            for article in articles[:4]: # 키워드당 최신 뉴스 상위 4개씩 추출
                title_elem = article.select_one("a.news_tit")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                link = title_elem['href']
                
                # 요약문 추출
                dsc_elem = article.select_one("div.news_dsc")
                summary = dsc_elem.text.strip() if dsc_elem else ""
                
                # 중복 뉴스 제거 검사
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
# 2. Gemini AI를 활용한 뉴스브리핑 및 인사이트 생성
# ==========================================
def generate_newsletter_with_gemini(news_list):
    # 환경변수에서 AI 키 로드
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # AI에게 전달할 뉴스 데이터 뼈대 빌드
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 키워드: {news['keyword']}\n제목: {news['title']}\n요약원문: {news['summary']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대한민국 최고의 기업 인사노무 전문가이자 Chief HR Officer (CHO) 전담 비서입니다.
    아래 수집된 최신 뉴스 데이터들을 바탕으로, 오늘 아침 기업 경영진과 인사팀이 반드시 읽고 선제 대응해야 할 '일일 HR 뉴스레터'를 작성해 주세요.

    [수집된 뉴스 데이터]
    {raw_news_text}

    [작성 가이드라인]
    1. 제목은 세련되고 전문적인 인사 브리핑 형태로 작성해 주세요 (예: "[세방 HR 브리핑] 2026년 5월 15일 오늘의 주요 인사·노무 동향")
    2. 뉴스들을 단순 나열하지 말고, 중요도나 주제별(예: 노사관계/임단협 이슈, 노동부 정책/지침 변경 등)로 2~3개의 그룹으로 묶어서 가독성 좋게 정리해 주세요.
    3. 각 뉴스 요약 끝에는 인사담당자가 주목해야 할 '실무적 시사점(Implication) 또는 대응 팁'을 1~2줄씩 덧붙여 주세요.
    4. 반드시 깔끔한 마크다운(Markdown)과 이모지를 섞어 전문적이면서도 Scannable(한눈에 들어오는) 구조의 HTML 메일 본문 형태로 출력해 주세요.
    """
    
    print("Gemini AI가 맞춤형 HR 뉴스레터를 요약 및 생성 중입니다...")
    response = model.generate_content(prompt)
    return response.text

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
    msg['Subject'] = f"[세방 HR 뉴스레터] 오늘의 주요 인사·노무 동향 및 실무 시사점"
    
    # HTML 형식 지원을 위해 본문 탑재
    msg.attach(MIMEText(content, 'html' if "<div" in content or "<p" in content or "<html>" in content else 'plain', 'utf-8'))
    
    print("구글 SMTP 서버에 접속하여 메일을 발송합니다...")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_pw)
        server.sendmail(gmail_user, receiver_email, msg.as_string())
    print("뉴스레터 메일 발송 완벽하게 성공!")

# ==========================================
# 메인 제어 루프
# ==========================================
if __name__ == "__main__":
    raw_news = get_hr_news()
    
    # 만약 네이버 검색에서 정말 1건도 안 나오는 비상 상황을 대비한 백업 안전장치
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
