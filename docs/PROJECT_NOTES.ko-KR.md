# PROJECT_NOTES — 개발 일지 요약

> 출처: 개인 Google Docs 개발 일지(2026.05.23 ~ 2026.06.30) + 이후 계층형 리팩토링 작업 기록(2026.06.30 ~ 07.01)을 정리한 문서.
> 코드 구조 자체는 [README.md](../README.md)를 참고하고, 이 문서는 **프로젝트의 의도·결정 근거·로드맵·미결 질문**처럼 코드만 봐서는 알 수 없는 맥락을 담는다.

---

## 1. 프로젝트 정체성과 철학

**한 줄 정의:** "AI 오케스트라를 만드는 것이 아니라, 내가 이미 수동으로 하던 다중 LLM 교차검증을 자동화한다."

- 같은 질문을 여러 LLM(GPT/Claude/Gemini)에 던지고, 답변·토큰·비용·메타데이터를 로그로 남겨 교차 검증하는 **개인용 리서치 자동화 CLI 도구**.
- 일본 Sakana AI의 'Fugu'(멀티 에이전트 오케스트레이션)에서 개념적 영감을 받았으나, **Fugu 같은 모델 학습은 목표가 아니다.** "Fugu식 개념을 응용한 개인용 교차검증 도구"가 목표.
- 용도는 **투자 리서치 보조 + 사업 아이템 검토** 2가지로 한정. 본업(주식 투자/창업 준비)과 병행하므로 주 3~5시간, MVP 우선.

**제1원칙 (반복 강조됨):**

- **AI 다수결 ≠ 진실.** 여러 모델이 같은 답을 해도 같이 틀릴 수 있다(공유된 학습 데이터·통념·오류).
- 도구의 목적은 정답을 AI에 위임하는 것이 아니라, **내 판단에서 빠진 근거·반론·리스크를 드러내는 것.** 최종 결정은 항상 사람.

---

## 2. 초기 타당성 평가 결론 (2026.05.23, GPT/Claude/Gemini)

세 LLM 모두 동일 결론: **풀스케일 오케스트라 AI를 지금 만드는 것은 비추천** (우선순위 붕괴 위험). 대신:

- 사업·투자 의사결정 보조용 **MVP**로 작게 시작.
- 언어는 **Python** (개인 도구 빠른 제작).
- 처음엔 LLM 호출 CLI → 답변 JSON 표준화 → 평가자/조율자 프롬프트 → SQLite 저장.
- 프로토타입을 실제 질문 수십 개로 테스트하고, 6개월 이상 써본 뒤 제품화 여부 재판단.

---

## 3. 마일스톤 (2026.05.24 설정)

| 단계 | 목표 | 상태 |
| :-- | :-- | :-- |
| 1단계 | GPT 단일 호출 → 답변 출력 → JSONL 로그 → SQLite 저장 + CLI | ✅ 완료 |
| 1.5단계 | 안정화(예외 처리, 하드코딩 제거, 안정화 정책) — "확장해도 덜 망가지는 상태" | ✅ 거의 완료 |
| 2단계 | Claude/Gemini 추가, 세 답변을 JSON 저장(멀티모델 호출) | ✅ 완료 (계층형 리팩토링 + OpenAI/Anthropic provider, `compare` 명령. Gemini는 스텁) |
| 3단계 | 평가자 프롬프트로 세 답변 비교 요약 출력 | ⬜ 예정 (`compare`가 답변 수집까지는 완료, 평가자 요약은 미구현) |
| 4단계 | SQLite 저장 + 비용 로깅 | ⬜ (1.5단계에서 상당 부분 선반영됨) |
| 5단계 | 실전 질문 30~50개 테스트 (투자/사업 2개 주제 한정) | ⬜ 예정 |

**3단계 최종 답변 구조(목표):** 1.결론 / 2.모델 간 공통 의견 / 3.충돌 지점 / 4.근거 부족 주장 / 5.확인 필요 사항 / 6.최종 판단

**초기 MVP에서 하지 말 것:** 웹 UI, 로그인, 모델 자동 선택, 재귀 호출, 이미지/동영상, 코드 실행 에이전트, 자동 투자 판단/매매, 벡터 DB/RAG, 복잡한 에이전트 프레임워크, 자체 모델 학습.

**테스트 기준:** 시간 절약 / 누락 발견 / 오류 감소 / 출처 요구 / 의사결정 기여 / 비용 대비 가치. (투자에서는 수익률보다 "충동적 판단을 줄였는가 / 반대 논리를 강제 검토했는가 / 세금·환율·수수료·리스크를 빠뜨리지 않았는가"가 1순위.)

---

## 4. 단계별 진행 기록

### 1단계 — API 통합 (2026.05.25 ~ 05.27)

- 개발 환경: VS Code(+ Pylance, Jupyter), venv 가상환경. OpenAI API는 **선결제 종량제**(크레딧 소진형, 약 $10 충전).
- Typer CLI(`cli.py`), `.env` 기반 API 키 관리(`env_check.py`), OpenAI 직접 호출(`llm_client.py`) 구현.
- Error 429 안내 → 결제 후 호출 성공. gpt-4o-mini 1회 호출 ≈ 0.00004575 USD(≈ 0.07원).
- 스트리밍/대화 이어가기는 **나중으로 보류**(SQLite 저장 우선).

### 1단계 — 로그 저장 (2026.05.28 ~ 05.31)

- **핵심 깨달음:** JSON 구조에는 *LLM 출력 Schema*(structured output)와 *로그 저장 Schema*(프로그램이 조립) 두 종류가 있다. → `schemas.py`에 Pydantic으로 정의, `llm_client.py`/`storage_json.py`가 공유.
- 로그는 **JSONL**(`logs/*.jsonl`)로 누적, 파일명 `*_log_생성날짜.jsonl`.
- **토큰 가격은 데이터로 관리:** 실시간 단가 API가 없으므로(LLM에 물어보는 것은 금지 — 비용/환각/무결성 문제) `config/prices/prices_*.json`을 사람이 직접 갱신, `count_cost.py`가 읽어 계산. `alias_of`로 dated 모델 ID 처리. 로그에는 "추정 비용"으로 저장(`estimated: true`).
- 비용 정밀도는 `Decimal` 사용.

### 1.5단계 — 안정화 (2026.06.11 ~ 06.20)

작업: 현재 상태 커밋/태그, README 갱신, DB 스키마 `schema.sql` 고정, 하드코딩 경로 제거, 가격표 30일 경과 알림, 전 파일 예외 처리.

**배운 내용 (예외 처리 원칙):**

- EAFP 대상(예외 처리): 사용자 입력·파일 경로·모델명·환경변수·네트워크/API·JSON 로딩 등 외부 의존성.
- LBYL/수정 대상: 개발자 버그(오타·타입 오류), 내부 불변 조건 — 숨기지 말고 터지게.
- **관심사 분리:** 하위 함수는 예외를 잡지 말고 최상위 진입점으로 전파. 광범위한 `except Exception`은 최상위에서만.
- 트레이스백은 아래에서 위로 읽기. "During handling of the above exception..." = 에러가 둔갑한 신호.

**LLM 리뷰로 발견한 핵심 버그(반드시 기억):**

- `ask_openai`의 "catch → print → return None" 패턴이 **진짜 에러(예: 404/RateLimit)를 가짜 에러(NoneType)로 둔갑**시켰다. → 하위 except를 걷어내고 예외를 cli.py 최상위로 전파.
- 실패 로그를 만드는 `except` 블록 자체에 `system_prompt` 누락 버그 → 실패조차 기록 못 하고 크래시(JSONL/SQLite 0건). 수정 완료.
- `resolve_model_entry`/`insert_log_record`의 unbound(NameError) 버그, `to_decimal`/`load_price_table`의 조용한 실패/타입 불일치 수정.

### 안정화 정책 (2026.06.19 ~ 06.20) — **현재 코드의 설계 불변식**

- **돈 쓴 응답은 절대 버리지 않는다.** 청구 후 단계(파싱·비용 계산·결과 검증) 실패는 모두 `PaidResponseError`로 감사 로그에 남긴다. 비용 계산만 실패하면 응답/토큰이 그대로 보존되고(`cost=None`), 파싱이나 결과 검증이 실패해 남길 응답이 없으면 `SalvageInfo`(실패 단계·provider·요청 모델 + 원시 응답에서 최선으로 읽어낸 id/model/usage)를 대신 남긴다. *(2026.08.01: 원래 비용 계산 실패에만 걸려 있던 경계를 청구 후 전 구간으로 확장.)*
- **유료 호출 전 preflight 검증**(가격표 존재·파싱·모델명) → 비용 낭비 0.
- **감사 로그는 항상 기록.** `log_data`를 try 밖에서 1회 생성, latency를 finally에서 측정(성공/실패 무관), `error_type` 항상 기록. 실패 run도 `runs` 행은 남김(`model_responses`는 건너뜀).
- **비용 미산정은 `cost=None`**으로 표현(가짜 0원 센티넬 금지 — 감사 로그 오염 방지).

### 2단계 — 다중 API 호출 / SOLID 리팩토링 (2026.06.25 ~ 진행 중)

- OpenAI 단일 공급자 전제 코드라 확장 시 더러워짐 → `git branch solid_refactoring` 생성.
- **2단계 체크리스트:**
  1. 공통 결과 모델 초안(`LLMRequest`, `LLMCallResult`) — *확정이 아니라 초안*. 2번째 provider가 검증함(Rule of Two).
  2. `ChatProvider`(Protocol) 작게 정의. sync/async 시그니처 결정.
  3. 기존 `ask_openai()`를 `OpenAIProvider`로 이동(로직 변경 없이).
  4. `cli.py:ask()`에서 오케스트레이션 분해(흐름 제어 / 표현 / 영속화).
  5. 저장 추상화(`LogRepository`/`LogWriter`)는 **뒤로 미룸**(YAGNI). 일단 단일 Facade(`RunRecorder`).
  6. provider registry/factory(단순 dict 매핑).
  7. **Claude 하나만** 붙이고 검증(Gemini 동시 X).
  8. ~~async 병렬 호출은 provider 2개 안정 후.~~ **→ 해결됨 (2026.07.27):** async가 아니라 `ThreadPoolExecutor`로 확정. 아래 "compare 병렬화" 항목 참조.

### 2단계 — 계층형 리팩토링 완료 (2026.06.30 ~ 07.01)

위 체크리스트를 실제로 수행하며 "두 아키텍처 공존" 상태를 끝내고 **단일 계층형 구조**로 정리. 6개 하위 단계로 진행(각 단계 완료 시 커밋):

1. **도메인 스키마 안정화** (`schemas.py`) — 다중 공급자에서도 안 깨지는 계약으로. 확정된 5개 결정(아래 5장 참조).
2. **`ChatProvider` Protocol 명시화** (`base_provider.py`) — 본문 없는 시그니처 `ask(request: LLMRequest) -> LLMCallResult`. 기존 `async def generateRequest`(동기 코드와 불일치) 제거. `@runtime_checkable`.
3. **공통 `ask` 흐름 추출** (신규 `providers/runner.py`) — preflight→유료 호출→파싱→비용→결과 조립→`PaidResponseError`를 한 곳에. 공급자별 차이는 콜백 2개(`call_api`, `parse_response`)로만 주입. `provider_openai.py`/`provider_anthropic.py`를 구체 클래스로 재작성.
4. **레지스트리 + 서비스 계층** (`providers/registry.py`, `services/service_ask.py`) — 이름→provider 해석, 단일 `ask`/다중 `compare`. 실패는 `ErrorInfo` 값으로 수집.
5. **횡단 중복 정리** — `list_models.py`/`env_check.py`의 3중 블록을 dict+루프로, `[file][def] Error Message:` print 패턴을 `diagnostics.print_error` 헬퍼로.
6. **마이그레이션** — import를 패키지 절대 방식으로 통일, **실행을 `python -m resources.cli`로 전환**(`cd resources` 폐기), `cli.py`를 얇게(서비스 위임), **`llm_client.py` 삭제**(중복 제거), CLAUDE.md 전면 갱신.

**리팩토링 중 해소한 복제 버그:** provider 스텁들에 있던 `response_id=str(uuid4)`(호출 누락), Anthropic이 OpenAI 필드명(`usage.prompt_tokens`)을 읽던 것, `content.message.content`(실제론 블록 리스트 `content[0].text`), `finish_reason`(Anthropic은 `stop_reason`), `selected_model` 강제 덮어쓰기 등.

**신규 `compare` 명령:** `python -m resources.cli compare "<sys>" "<q>" -t openai:gpt-4o-mini -t anthropic:claude-haiku-4-5`. 한 `run_id` 아래 여러 (provider, model)을 호출, 한 공급자 실패가 나머지를 막지 않음.

**provider 추가 비용:** 이제 `provider_*.py` 1개 + `registry.PROVIDERS` 1줄.

### 테스트 스위트 추가 (2026.07.01)

- `tests/`에 **무과금** pytest 스위트(가짜 SDK 응답/가짜 provider 주입). `pyproject.toml`에 `testpaths=["tests"]` — 기존 `test/`(실 API 호출 스크립트)는 수집 제외.
- 커버리지: 스키마 계약, 비용 계산(Decimal), `run_chat`(성공/client None/과금 후 실패 보존), provider 매핑, registry, service `ask`/`compare`, storage 토큰 매핑·멱등성. **30 passed.**
- `pytest`는 테스트 전용 의존성으로 `requirements_dev_win.txt`에 분리(`pytest==9.1.1`).

### compare 병렬화 (2026.07.27)

`service_ask.compare`의 순차 `for` 루프를 `ThreadPoolExecutor(max_workers=len(targets))`로 교체. 순수 I/O 대기라 벽시계 시간이 `sum(latency)` → `max(latency)`가 됨.

**async를 쓰지 않은 이유:** 동시 호출 수가 2~4개(`-t`로 명시)라 asyncio의 강점(수천 소켓, 태스크당 낮은 메모리)이 무의미한 반면, 변경 범위는 압도적으로 큼 — `ChatProvider` Protocol 시그니처, `runner.run_chat`, provider 3개(`AsyncOpenAI`/`AsyncAnthropic`), `service_ask.ask`, `cli.py`(단일 `ask`까지 `asyncio.run` 필요), `tests/fakes.py` 전체, 그리고 `pytest-asyncio` 신규 의존성. 게다가 `log_repository`의 sqlite3/파일 쓰기는 블로킹이라 결국 `asyncio.to_thread`로 감싸야 해서 이점이 상쇄됨. 스레드 쪽은 `run_request()`가 이미 완결된 작업 단위(예외를 절대 던지지 않고 항상 `LLMCallLog` 반환)라 `service_ask.py` 한 파일만 수정하면 됨.

**영속화는 병렬화하지 않음 (핵심 결정).** API 호출만 스레드로 돌리고, future는 **완료 순이 아니라 제출 순**으로 소비해 `persist_log`는 호출 스레드에서만 실행. SQLite 락 회피는 부수적 이유이고, 진짜 이유는 두 가지:

1. JSONL 파일명이 배치 공통 `created_at` 기준이라 **같은 provider를 여러 번 지정하면 한 파일에 동시 append**가 발생(Windows append는 원자적이지 않음).
2. `SqliteLogReader.recent`가 삽입 `id` 순으로 정렬해 한 그룹의 순서를 결정적으로 유지하는데, 병렬 쓰기는 이를 응답 지연 순서로 바꿔 `history -g <group_id>` 결과를 매번 다르게 만듦.

`persist_log`를 풀 블록 **안**에 두어, 아직 통신 중인 호출과 로컬 I/O가 겹치도록 함(중간 크래시 시 앞선 결과 보존).

**타임아웃(`future.result(timeout=...)`)은 의도적으로 배제.** 블로킹 소켓 읽기는 취소가 불가능하므로 타임아웃은 **이미 과금된 응답을 버리는 결과**가 되어 "Never discard a billed response" 불변식과 충돌함.

**테스트:** `BarrierProvider`(`threading.Barrier`로 동시 실행을 결정적으로 검증 — 순차 실행이면 타임아웃되어 전부 실패), `SlowProvider`(지연이 결과 순서에 영향을 주지 않음을 검증)를 `tests/fakes.py`에 추가. 기존 `compare` 테스트 2건은 무수정 통과(= API 호환). **44 passed.**

---

## 5. 핵심 설계 결정 (LLM 자문 정리)

### 계층형 리팩토링 확정 결정 (2026.07.01)

위 2단계 리팩토링을 진행하며 그동안 초안/미결이던 항목을 확정:

1. **`total_tokens`는 선택 필드** (`int | None`). Anthropic은 total을 안 주므로 없으면 storage가 input+output로 산출.
2. **`response_id`/`run_id`는 서비스 계층이 생성·주입.** provider는 ID를 만들지 않음(`LLMRequest.response_id`로 받음).
3. **캐시 토큰은 의미 차이를 필드로 분리 보존:** `cached_input_tokens`(OpenAI) / `cache_creation_input_tokens`·`cache_read_input_tokens`(Anthropic). (이전의 "필드만 0으로, 수식 보류" YAGNI 입장을 대체.)
4. **공통 흐름 공통화는 함수 주입 방식** (`run_chat`에 콜백 2개). 상속 기반 템플릿 메서드 대신 — Protocol 철학(상속 없는 계약)과 일치.
5. **import는 패키지 절대 방식으로 통일**, 실행은 프로젝트 루트에서 `python -m resources.cli`.

### Protocol vs ABC

- **`typing.Protocol` 채택.** provider들은 공유 구현 코드가 없는 "남남"이며, 상속(is-a)이 아니라 "동일 계약 준수"면 충분. 더 가볍고 파이썬스럽다.
- **주의:** Protocol은 정적 타입 체커(Pylance)용 — 메서드 이름이 **글자 단위로 동일**해야 구조적 타이핑 성립. 런타임 강제는 없음. 공통 부모는 강제하지 말되, 스키마(`LLMRequest`/`LLMCallResult`/`UsageInfo`/`CostInfo`)는 **더 엄격하게** 관리. (반복 구현이 실제로 쌓이면 그때 ABC/mixin 검토.)

### OpenAI SDK 호환 레이어

- Claude/Gemini를 OpenAI SDK(base_url/key만 변경)로 호출 가능 — **스파이크(빠른 확인)용으로는 OK.**
- **그러나 프로덕션 generate()는 네이티브 SDK 권장.** 특히 Anthropic 호환 레이어는 prompt caching 미지원, 일부 필드(`usage.*_tokens_details`)를 **조용히 무시** → 비용 추적 도구에 치명적("번역의 번역" 2중 손실).
- 줄여야 하는 건 "HTTP 호출 코드"뿐, **응답 정규화·비용 계산은 provider별로 유지.**

### 공급자 고유 필드 / 캐시 토큰

- 같은 개념·이름만 다른 것(OpenAI `prompt_tokens` ↔ Anthropic `input_tokens`)은 **각 어댑터 내부에서 공통 이름으로 번역**. 중앙 코드에 `if provider == ...` 분기 금지(OCP 위반 = "Replace Conditional with Polymorphism").
- 진짜 고유 데이터는 **`raw_response`에 원본 통째 보관 + 공통 필드만 추출.** 공통 스키마에 provider별 Optional 남발 금지.
- **`UsageInfo`는 provider-neutral하게**(`input_tokens`/`output_tokens` + 캐시 카테고리들 nullable + `raw_usage`).
- **Claude 캐시 비용:** native SDK usage(`cache_creation_input_tokens`=쓰기, `cache_read_input_tokens`=읽기)에서만 나옴. 단가는 base input 대비 배수(읽기 0.1x / 5분 쓰기 1.25x / 1시간 쓰기 2.0x, 전 모델 동일). **계산은 Anthropic provider의 cost 로직 안에 가둘 것.** 단, 현재 구조는 캐시 토큰이 보통 0 → **지금은 YAGNI(필드만 기본값 0으로 기록, 수식 보류).**
  - **→ 해결됨 (2026.07.01):** `TokenUsageInfo`에 캐시 3필드를 분리 보존(위 5장 결정 3). 비용 계산은 아직 단일 캐시 레이트만 적용 — Anthropic은 `cache_read`(할인분)를 `run_chat`의 `cached_input_tokens_for_cost`로 넘김. 쓰기/읽기 배수 구분 수식은 여전히 보류(YAGNI). DB는 단일 `cached_tokens` 컬럼에 합산 저장, 분해는 `raw_json`에 보존.

### 부분 실패 정책 (부분 해결)

- compare(동시 3개 호출)에서 한 provider만 실패 시 **all-or-nothing은 권장 안 함**(이미 돈 낸 응답을 버림 = `PaidResponseError` 철학과 모순).
- 상태를 분리: `complete`(전원) / `partial`(일부 실패, 누가·왜 기록) / `failed`(정족수 미달, 비교 불가 — 성공 1개는 대조 대상 없으니 실패).
- **누락 공급자를 평가자 AI에게 명시적으로 플래그**해야 함 — 평가자는 살아남은 응답을 "전체"로 착각하므로. 이것이 합의 착시를 깨는 메커니즘.
- **→ 해결됨 (2026.07.01):** `service_ask.compare`가 한 provider 실패해도 나머지를 진행하고, 실패를 `ErrorInfo`로 수집(`partial_result`에 `PaidResponseError`로 보존된 응답 포함). 결과는 `CompareResult(successes, failures, logs)`로 성공/실패 분리. **아직 미구현:** `complete/partial/failed` 상태 라벨링과 정족수 판정, 평가자에게 누락 공급자를 플래그하는 메커니즘(= 3단계 평가자 프롬프트에서 처리 예정).

---

## 6. API 테스트 메모 (2026.06.26)

- **Anthropic:** `client.messages.create()`에 **`max_tokens` 필수**(빼면 400). OpenAI는 선택값.
- **Gemini:** `generateContent`(stateless) vs `Interactions`(stateful, 실험적 경고) 중 **`generateContent` 채택** — 멀티 LLM 독립 수집에 오버헤드 적고 OpenAI/Anthropic SDK와 1:1 매칭 쉬움. 구글 API는 구조 차이가 있어 추상화 시 주의.

---

## 7. 2A단계 — 로컬 LLM (실험적, 2026.06.09)

- PC 사양: AMD Ryzen 7 1700X / GTX 1080 Ti (11GB VRAM) / 16GB RAM. 로컬 LLM 운용 가능하나 "안정적 평가자 AI"로는 애매 → **개인정보 보호용 독립 모델 + LLM 내부 구조 학습용**으로 활용.
- llama.cpp 빌드가 너무 복잡해 포기 → **Ollama 설치**(딸깍 설치, `/v1` OpenAI 호환 엔드포인트). `llama3.1:8b-instruct-q8_0` 채팅 성공.
- 후보 모델: Qwen 2.5 7B(한국어 최상위·보안 우려), Llama 3.1 8B(표준), Gemma 3 4B, EXAONE 3.5 7.8B(LG, 한국어 특화) 등.

---

## 8. 보류 중인 작업

- **Progress bar:** 스트리밍 청크 구현이 필요해 보류. 당장은 `rich.status`/spinner로 "호출 중..." 표시만 가능.
- 스트리밍 응답, 대화 이어가기, 토큰 파라미터(`--max-tokens`/`--temperature`) CLI 옵션.

---

## 9. 미결 설계 질문 (LLM 심화 질문에서)

- ~~`ErrorInfo`를 **누가 만드는가** — provider(예외 raise)냐 service 계층(compare 루프가 예외→데이터 변환)이냐?~~ **→ 해결됨 (2026.07.01):** provider 계약은 단순하게(성공→`LLMCallResult`, 실패→raise; 청구 후 부분 실패는 `PaidResponseError`). 실패를 데이터(`ErrorInfo`)로 바꾸는 책임은 **service 계층의 `compare`에만** 둠. 단일 `ask`는 그대로 raise→`LLMCallLog`(success=False)로 기록. `schemas.py`의 `ErrorInfo`는 이제 실제 필드를 가진 값 타입(provider/model/error_type/message/elapsed_sec/partial_result/created_at).
- 정족수(비교 성립 최소 N)는 질문 유형(단순 사실 vs 가치 판단)에 따라 달라져야 하는가?
- **상관된 동의(correlated agreement):** 셋 다 성공·합의해도 프런티어 모델은 학습 계보를 공유 → 독립 검증이 아닐 수 있음. `complete` 상태라 경보가 안 울려 부분 실패보다 위험. 평가자/사용자가 이를 독립 입증으로 착각하지 않게 어떻게 설계할 것인가?
- 의미적 불일치(예: Anthropic `stop_reason` ↔ OpenAI `finish_reason`)는 타입 체커가 못 잡음 → 어떻게 검증할 것인가?

---

## 10. 참고 자료

- SOLID: [GeeksforGeeks](https://www.geeksforgeeks.org/system-design/solid-principle-in-programming-understand-with-real-life-examples/), [RealPython](https://realpython.com/solid-principles-python/)
- 디자인 패턴: [Refactoring.Guru](https://refactoring.guru/design-patterns)
- Python: [함께해요 파이썬 생태계](https://wikidocs.net/book/14021), [파이썬 전문가](https://wikidocs.net/book/15787)
- Sakana Fugu: <https://sakana.ai/fugu-beta/> (ICLR 2026 논문 <https://arxiv.org/abs/2512.04695>)
- Claude OpenAI SDK 호환: <https://platform.claude.com/docs/ko/cli-sdks-libraries/libraries/openai-sdk>
- Gemini OpenAI 호환: <https://ai.google.dev/gemini-api/docs/openai?hl=ko>
- Anthropic prompt caching: <https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching>
- GitHub: <https://github.com/SupremeHo/Personal-Multi-LLM-Review-Automation-Tool>

> 원본 일지에는 Claude prompting guide 전문과 OpenAI/Claude/Gemini 모델 목록 스냅샷도 포함되어 있다(여기서는 생략).
