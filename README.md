# 🏢 AtomCompany (260921)
> **Google Gemma 4 기반 완전자율 2-에이전트(PM ⇄ ENG) 소프트웨어 개발사**  
> *Fully Autonomous 2-Agent Software Enterprise Running 100% Locally on Google Gemma 4*

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Model](https://img.shields.io/badge/Model-Google%20Gemma%204%3AE4B-purple.svg)](https://ollama.com/library/gemma)
[![Tests](https://img.shields.io/badge/Protocol%20Tests-19%2F19%20Passed-emerald.svg)](tests/test_protocol.py)
[![UI](https://img.shields.io/badge/Dashboard-Glassmorphism%20Zero--CDN-orange.svg)](web/index.html)

---

## 🌟 프로젝트 개요 (Overview)

**AtomCompany**는 외부 클라우드 API 의존성이나 데이터 유출 없이, 로컬 워크스테이션의 **Google Gemma 4** 모델만을 활용하여 소프트웨어를 기획·구현·자가검증·납품하는 **완전자율 2-에이전트 기업(2-Agent Autonomous Enterprise)** 시스템입니다.

인간의 지속적인 개입 없이도 **PM(프로젝트 매니저)**과 **ENG(엔지니어)** 에이전트가 파일시스템 메일박스 기반의 엄격한 상호 감사 프로토콜을 준수하며 코드를 생산합니다.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ATOM COMPANY PROTOCOL ARCHITECTURE              │
├──────────────────────┐                          ┌──────────────────────┤
│  PM (Project Manager)│    MAILBOX BUS (SHA-256) │  ENG (Software Eng)  │
│  • 요구사항 명세 수립    │ ───────────────────────► │  • write_file 도구 호출 │
│  • 단위 테스트 실측 검증 │ ◄─────────────────────── │  • 자가 테스트 100% 통과 │
│  • 최종 합격/반려 판정  │                          │  • 무결성 증빙 보고서   │
└──────────────────────┘                          └──────────────────────┘
```

---

## 🚀 핵심 차별화 기능 (Key Features)

1. **100% 로컬 프라이빗 구동 (Zero External API)**
   - Ollama 기반 `gemma4:e4b` (9.6GB) 모델을 로컬 GPU(NVIDIA RTX 6000 Ada 48GB) 또는 CPU 환경에서 단독 구동.
   - 외부 네트워크가 완전히 차단된 사내망/에어갭(Air-gapped) 보안 환경에서도 완벽 작동.

2. **철저한 역할 분담 및 상호 검증 (Strict Role Separation)**
   - **PM 에이전트**: 코드 작성 권한 원천 박탈. 지시서 작성, 인터페이스 정의, 독립적 단위 테스트 실측 및 최종 판정(`DECISION: ACCEPT/REJECT`).
   - **ENG 에이전트**: 네이티브 도구(`write_file`) 호출로 소스 코드 생성, `python3 -m unittest` 자가 검증 통과 후 PM에게 납품.

3. **SHA-256 원장 및 루프 가드 (Verifiable Integrity & Loop Guards)**
   - 모든 에이전트 메시지는 SHA-256 체크섬을 검증하여 통신 위변조 방지.
   - 핑퐁 반복을 방지하는 루프 가드(Loop Guard)와 예산 제약 프로토콜 내장.
   - 19종의 전용 프로토콜 자동화 단위 테스트([`tests/test_protocol.py`](tests/test_protocol.py)) 100% 통과.

4. **럭셔리 다크 오로라 웹 대시보드 (Zero-CDN Mission Control)**
   - 외부 라이브러리/CDN 의존성 없이 순수 CSS3 글래스모피즘과 바닐라 JS로 구현.
   - 실시간 에이전트 텔레메트리, 2-에이전트 극장(통신 내역), 12대 과업 보드(Kanban), 산출물 코드 뷰어, **원클릭 실시간 단위 테스트 러너** 내장.
   - IPv4 + IPv6 듀얼 스택 네트워크 수신 지원.

---

## 📂 프로젝트 구조 (Repository Layout)

```
atom-company/
├── agent.py               # 핵심 에이전트 런타임 (PM & ENG 엔진, 도구 호출, 메일박스)
├── validate_msg.py        # 메시지 헤더·체크섬·형식 무결성 검증기
├── soak_runner.py         # 장기 자율 실행(Soak Test) 러너 및 메트릭스 수집
├── web_server.py          # 듀얼스택 경량 HTTP REST API 서버 (포트 8080/3000)
├── web/
│   └── index.html         # 최고급 디자인 자립형 웹 대시보드
├── ROLES/                 # 에이전트 시스템 프롬프트 (PM.md, ENG.md)
├── tasks/                 # 12대 과업 명세서 (TASK-0001 ~ TASK-0012)
├── tests/
│   └── test_protocol.py   # 19종 프로토콜 무결성 자동화 단위 테스트
├── workspace/             # 에이전트가 실제 작성한 소스 코드 및 테스트 산출물
│   └── workspace/
│       ├── todo_cli.py    # Gemma 4가 직접 작성한 Todo CLI 모듈
│       └── test_todo.py   # 6/6 단위 테스트 전원 통과 검증 코드
├── inbox/                 # 에이전트 간 비동기 메시지 교환 메일박스
├── done/                  # 처리가 완료된 메시지 아카이브
└── ledger/                # 불변 감사 원장 및 실행 리포트
```

---

## ⚡ 빠른 시작 (Quickstart)

### 1. 환경 준비
```bash
# Ollama 설치 및 Gemma 4 모델 준비
ollama serve &
ollama pull gemma4:e4b
```

### 2. 프로토콜 단위 테스트 검증 (19/19 통과)
```bash
python3 -m unittest tests/test_protocol.py
```

### 3. 웹 컨트롤 대시보드 구동
```bash
python3 web_server.py
```
브라우저에서 **`http://localhost:8080`** 접속:
- 실시간 미션 컨트롤 및 텔레메트리 확인
- `산출물 & 단위 테스트 실사` 탭에서 **`▶ 단위 테스트 즉시 실측`** 원클릭 실행

---

## 📜 라이선스 (License)
Apache-2.0 License.
Google DeepMind Gemma 4 오픈 가중치 이용 규정을 준수합니다.
