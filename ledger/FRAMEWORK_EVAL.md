# 상위 프레임워크 도입 기술 평가서 (FRAMEWORK_EVAL.md) [CORRECTED v4]

- 지시서 번호: AG-D-260918-AC-04 (Task R 반영)
- 평가자: Antigravity (실행 에이전트)
- 검토 대상: Principal(허상훈) / System 2 감사(Claude)
- 갱신 일시: 2026-09-18T23:23:00+09:00

---

## 1. 프레임워크 실측 설치 및 에어갭 검증

### (1) Paperclip (`paperclipai`)
- **실행 명령**: `npx paperclipai --help`
- **실측 결과**: 설치 실패 (`npm error code E403`)
- **증거 포인터**:
  - 로그 파일: `/home/sims/.npm/_logs/2026-09-18T13_51_52_922Z-debug-0.log`
  - 에러 원문: `npm error 403 Forbidden - GET https://registry.npmjs.org/paperclipai`
- **실측 판정**: 샌드박스 보안 정책상 외부 npm 레지스트리 다운로드 불가 확인.

### (2) Aeon (`aeon-ai/aeon`)
- **실행 명령**: `git clone --depth 1 https://github.com/aeon-ai/aeon /home/sims/auto/atom-company/ledger/aeon_clone`
- **실측 결과**: 복제 실패 (`fatal: The requested URL returned error: 403`)
- **증거 포인터**:
  - 로그 파일: `ledger/T5_aeon_clone.log:1-3`
  - SHA256: `ledger/T5_aeon_clone.log: 1cc174bdbba97dd2672bca14d1fc39c7b67663d00be2b8552321880c245c31a0`
  - 에러 원문: `remote: Request to GET /aeon-ai/aeon/info/refs on github.com not allowed by policy`
- **실측 판정**: 외부 Git 호스트 아웃바운드 접근 차단 확인.

---

## 2. 파일 우편함 프로토콜(Atom Company) vs 상위 프레임워크 실측 비교

| 비교 항목 | Atom Company (현 파일 프로토콜) | Paperclip (Node.js/React) | Aeon (Git/Markdown) |
|---|---|---|---|
| **코드 규모** | **648행 (`wc -l agent.py` 실측)** | 대규모 패키지 [?] (> 10,000행 [?]) | 중규모 패키지 [?] |
| **외부 의존성** | **0 (Python 3 표준 라이브러리 전용)** | Node.js, React, 다수 npm 패키지 | Python, Git 런타임 |
| **메모리(RSS)** | **21.41 MB (`ps -o rss= -p $PID` 구동 중 실측)** | > 300 MB [?] (추정치) | 미실측 [?] |
| **에어갭 설치** | **성공 (외부 설치 불필요)** | **실패 (npm E403 차단 실측)** | **실패 (git 403 차단 실측)** |
| **감사 투명성** | **최상 (원자적 .md 메시지 보존)** | 중간 (별도 DB/인메모리 추적) | 높음 (Git 기반) |
| **대시보드 UI** | 부재 (CLI 및 원장 기반) | 웹 대시보드 및 조직도 UI 제공 | Markdown 기반 문서 |

---

## 3. Principal 권고안

1. **로컬 에어갭 환경**:
   - 현재 샌드박스 환경에서는 npm/git 아웃바운드가 차단되어 있어 Paperclip과 Aeon 모두 오프라인 번들 없이는 설치가 불가능합니다.
   - 따라서 종속성이 전혀 없는 Python 표준 라이브러리 기반의 본 파일 프로토콜이 가장 적합합니다.
2. **상위 프레임워크 확장 시 선결 과제**:
   - Paperclip 또는 Aeon을 도입하려면 인터넷이 연결된 환경에서 Docker 이미지 또는 npm/pip 캐시를 사전 빌드하여 로컬로 반입(Vendor bundling)해야 합니다.
