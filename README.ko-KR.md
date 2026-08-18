# Personal Multi-LLM Review Automation Tool 🚀

![Language](https://img.shields.io/badge/Language-Python_100%25-blue)
![Status](https://img.shields.io/badge/Status-MVP-brightgreen)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> 🇬🇧 English documentation is available in [README.md](README.md).

## 📖 개요 / 설명

**Personal Multi-LLM Review Automation Tool**은 여러 대형 언어 모델(LLM)의 응답을 교차 검증하는 과정을 자동화하기 위한 CLI 기반 보조 도구입니다.

여러 LLM의 답변을 교차 검토할 때, 플랫폼을 수동으로 오가는 이른바 "탭 전환 지옥"은 심각한 맥락 전환 비용과 피로를 유발합니다. 이 도구는 하나의 프롬프트를 여러 AI 모델로 평가하도록 오케스트레이션하고, 답변·메타데이터·로컬에서 계산한 비용을 구조화된 형식(JSONL 및 SQLite)으로 기록합니다.

## 🎯 목적 & 철학

이 프로젝트는 사업 및 투자 의사결정을 돕기 위한 개인 리서치 자동화 도구로 출발했습니다. 멀티 에이전트 오케스트레이션 시스템의 철학에서 영감을 받아, 개인용으로 엄격하게 최소 기능 제품(MVP) 형태로 최적화되었습니다.

**⚠️ 핵심 철학:**

* **AI의 다수결 ≠ 절대적 진실:** 여러 AI의 합의가 진실을 보장하지는 않습니다. _최종 결정은 언제나 사람인 사용자에게 있습니다._
* **사각지대 줄이기:** 이 도구의 진정한 목적은 정답 찾기를 AI에 위임하는 것이 _아닙니다_. 오히려 누락된 근거, 반론, 리스크 요인을 자동으로 드러내어, 중요한 결정을 내리기 전에 사용자의 인지적 사각지대를 최소화하도록 설계되었습니다.

## 💻 기술 스택 & 버전

* **언어:** Python 3.14 (100%)
* **CLI 프레임워크:** [Typer](https://typer.tiangolo.com/) (타입 힌트 기반의 빠른 CLI 생성)
* **데이터 검증:** Pydantic (`extra="forbid"` 적용, 프로바이더 중립적인 엄격한 스키마)
* **프로바이더:** OpenAI ✅, Anthropic ✅, Google/Gemini ✅
* **데이터베이스:** SQLite3 (로컬 로깅 및 분석 쿼리용)
* **환경 및 의존성 관리:** [uv](https://docs.astral.sh/uv/) (`uv.lock`으로 버전 고정), 안전한 API 키 처리는 `python-dotenv`

## 🚀 사용법

### 1. 사전 준비

의존성과 Python 툴체인 모두 [uv](https://docs.astral.sh/uv/)가 관리합니다. uv는 한 번만 설치하면 됩니다:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

이후 프로젝트 루트에서:

```bash
uv sync
```

이 명령 하나가 `.python-version`(3.14)을 읽어 해당 인터프리터가 없으면 내려받고, `.venv/`를 만들고, `uv.lock`에 고정된 정확한 버전으로 모든 의존성을 설치합니다. 별도의 `venv` 생성이나 `pip install` 단계는 없습니다. 테스트/린트 도구(`pytest`, `ruff`)는 `dev` 의존성 그룹에 있으며 기본으로 함께 설치됩니다. 런타임 의존성만 필요하면 `uv sync --no-dev`를 쓰세요.

아래 명령들은 `uv run` 접두사를 붙여 표기했습니다. 이 접두사는 venv를 활성화하지 않고도 해당 환경에서 명령을 실행합니다. venv를 직접 활성화하는 편이 좋다면(Windows는 `.venv\Scripts\activate`, 그 외는 `source .venv/bin/activate`) 접두사를 빼면 됩니다.

저장소에 `requirements.txt`는 없습니다. `pyproject.toml`과 `uv.lock`이 유일한 기준입니다. pip 기반 워크플로용으로 필요하다면 lock 파일에서 생성하세요:

```bash
uv export --no-dev --no-hashes --format requirements.txt -o requirements.txt
```

### 2. 환경 변수 설정

이 도구는 `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` 세 개의 키를 읽습니다. 모든 키는 선택 사항이며, 키가 없으면 도구 전체가 멈추는 대신 해당 프로바이더 하나만 비활성화됩니다.

Anthropic은 `ANTHROPIC_API_KEY` 대신 `ANTHROPIC_AUTH_TOKEN`도 받습니다. SDK가 설정된 쪽을 사용하므로 둘 중 하나만 있어도 프로바이더가 활성화됩니다.

키를 넣는 방법은 두 가지이며, **OS 환경 변수를 먼저 읽고 항상 우선합니다.** `.env`는 OS 환경 변수가 채우지 않은 값만 보완합니다.

**권장 — OS 환경 변수.** 프로젝트 디렉터리 바깥에 있으므로 저장소와 함께 커밋·압축·공유될 수 없습니다:

```powershell
# Windows (PowerShell): setx는 사용자 프로필에 기록합니다. 실행한 셸에는 반영되지 않으므로
# 반드시 새 셸을 여세요.
setx OPENAI_API_KEY "your-openai-api-key-here"
```

```bash
# macOS/Linux: ~/.zshrc 또는 ~/.bashrc에 추가
export OPENAI_API_KEY="your-openai-api-key-here"
```

**대체 수단 — `.env` 파일.** 프로젝트 루트에서 `.env.example`을 `.env`로 복사한 뒤 보유한 키를 채워 넣으세요:

```dotenv
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

`.env`는 gitignore로 차단되어 있지만 저장소 안의 평문 파일이라는 점은 그대로입니다. 실제 유출은 커밋보다 폴더를 압축해 공유하는 경로에서 발생합니다. 두 방식 모두 키를 암호화해 저장하지 않으며, 내 계정 권한으로 도는 프로세스라면 어느 쪽이든 읽을 수 있습니다.

`.env`는 시작 시 한 번(`resources/env.py`, `resources/__init__.py`에서 호출) **모든 프로바이더 클라이언트가 생성되기 전에** 로드되므로, 두 방식은 모든 명령에서 동일하게 동작합니다.

설정 상태는 언제든 아래 명령으로 검증할 수 있습니다:

```bash
uv run python -m resources.cli check-env
```

### 3. 로컬 설정 (비용)

비용은 추가 API 호출 없이 데이터 파일에서 **로컬로** 계산됩니다. 요율은 프로바이더별로 `config/prices/prices_{openai,anthropic,gemini}.json`에 **USD / 100만 토큰** 기준으로 저장됩니다. 각 파일에는 `updated_at`/`source` 메타데이터가 함께 담겨 있으며, 날짜가 붙은 모델 ID는 `alias_of`를 통해 기준 항목을 재사용할 수 있습니다:

```json
{
  "provider": "OpenAI",
  "currency": "USD",
  "unit": "per_1m_tokens",
  "updated_at": "2026-05-31",
  "source": "https://developers.openai.com/api/docs/pricing",
  "models": {
    "gpt-4o-mini": {
      "input": 0.15,
      "cached_input": 0.075,
      "output": 0.60
    },
    "gpt-4o-mini-2024-07-18": {
      "alias_of": "gpt-4o-mini"
    }
  }
}
```

### 4. 데이터베이스 설정

SQLite 파일 `_db/llm_responses.db`는 `_db/_create_table.sql`로 최초 1회 생성/초기화합니다(`sqlite3` CLI나 임의의 클라이언트로 실행). 도구는 **이미 존재하는** DB에 연결하며, 누락된 감사(audit) 컬럼만 `ALTER`로 추가할 뿐 테이블 자체를 생성하지는 않습니다.

`_db/_create_table.sql`이 스키마의 **유일한 원본(single source of truth)**입니다(`_db/llm_responses.db` 파일 자체는 git에서 제외됨). DB를 삭제하고 처음부터 다시 만들고 싶을 때는 반드시 이 파일로 재시드하세요. DB 클라이언트에서 임의로 내보낸 덤프로 복원하면 추적 중인 스키마와 조용히 어긋날 수 있으므로 사용하지 마세요:

```bash
# 비어 있고 올바르게 시드된 DB를 재생성
rm _db/llm_responses.db          # 선택: 기존 파일 먼저 삭제
sqlite3 _db/llm_responses.db < _db/_create_table.sql
```

모든 구문이 `CREATE TABLE/INDEX IF NOT EXISTS`라서 기존 DB에 실행해도 안전합니다(누락된 것만 채움). GUI 클라이언트(예: DB Browser for SQLite)에서는 같은 파일 내용을 **Execute SQL** 탭에 붙여넣고 실행하면 됩니다.

### 5. CLI 실행

**프로젝트 루트**에서 모듈로 실행하세요(`cd resources` 금지). `ask`와 `compare`는 실제(유료) API를 호출하며, 로그(JSONL)와 메타데이터(SQLite)를 자동으로 저장합니다.

**단일 프로바이더/모델에 질문:**

```bash
uv run python -m resources.cli ask "<system_prompt>" "<user_question>"
# 기본값: --provider openai --model gpt-5.6-luna

uv run python -m resources.cli ask "<system_prompt>" "<user_question>" \
  --provider anthropic --model claude-haiku-4-5
```

**여러 모델을 비교** (핵심 "리뷰" 기능) — `--target/-t provider:model`을 최소 1개 지정해야 하고 동일한 `provider:model`은 중복 지정할 수 없습니다. 답변은 지정한 타겟 순서대로 출력됩니다. 각 호출은 자체 `run_id`를 갖고 하나의 공유 `group_id`로 묶입니다:

```bash
uv run python -m resources.cli compare "<system_prompt>" "<user_question>" \
  -t openai:gpt-5.6-terra -t anthropic:claude-haiku-4-5
```

**기타 명령어:**

```bash
uv run python -m resources.cli check-env      # .env 키 검증 (대화형)
uv run python -m resources.cli list-models    # 설정된 프로바이더별 모델 목록
uv run python -m resources.cli history        # 최근 호출 조회 (최신순)
uv run python -m resources.cli history -n 20              # 최근 20건 조회
uv run python -m resources.cli history --group <group_id> # 한 비교(compare)의 호출들만 조회
```

* **`system_prompt`**은 LLM이 어떻게 응답할지 미리 규정하는 지시문입니다.
* **`user_question`**은 LLM에 전달하는 메시지입니다(구체적이고 명확할수록 좋습니다).

## 📂 아키텍처

코드는 `resources/` 아래의 단일 레이어드 아키텍처이며, 패키지 절대 경로 임포트(`from resources.schemas import ...`)를 사용해 패키지로 다루고 프로젝트 루트에서 실행합니다:

```bash
cli.py                                      # 얇은 Typer 계층: 인자 파싱 → 위임 → 렌더링
  └─ services/service_ask.py                # id(run_id/response_id) 소유, 로그 구성, 오류 수집, 저장
       └─ providers/registry.py             # 이름 → ChatProvider 인스턴스
            └─ providers/provider_*.py      # 프로바이더별 API 특성 (openai, anthropic, google)
                 └─ providers/runner.py     # run_chat(): 공통 호출 파이프라인, 프로바이더 차이는 콜백으로 주입
                      └─ count_cost.py / schemas.py / storage_json.py / storage_sqlite.py
```

* **`cli.py`** — 얇은 Typer 계층. 인자를 파싱해 서비스 계층에 위임하고 결과를 렌더링합니다.
* **`services/service_ask.py`** — 오케스트레이션. `run_id`/`response_id`를 발급하고, 프로바이더를 해석하며, 감사 로그를 구성하고, `compare` 실패를 데이터로 수집한 뒤 저장합니다.
* **`providers/registry.py`** — 프로바이더 이름을 구체 `ChatProvider`에 매핑하는 유일한 지점입니다.
* **`providers/provider_*.py`** — 프로바이더별 API 특성(OpenAI, Anthropic, Google).
* **`providers/runner.py`** — 공통 채팅 파이프라인(preflight → 유료 호출 → 파싱 → 최선의 비용 계산 → 결과 조립). 각 프로바이더는 `_call_api`와 `_parse_response` 콜백만 제공합니다.
* **`schemas.py`** — 엄격하고 프로바이더 중립적인 Pydantic 모델(`LLMRequest`, `LLMCallResult`, `LLMCallLog` 등).
* **`storage_json.py` & `storage_sqlite.py`** — JSONL 및 SQLite로의 데이터 영속화.
* **`count_cost.py`** — 추가 API 호출 없이 토큰 사용 비용을 로컬에서(`Decimal`로) 계산합니다.

**프로바이더 추가** = `provider_*.py` 하나를 추가하고 `registry.PROVIDERS`에 한 줄을 추가하면 됩니다.

## 🧪 테스트

pytest 스위트는 `tests/`에 있으며 **유료 호출을 전혀 하지 않습니다** — 프로바이더 파싱은 가짜(fake) SDK 응답으로, 서비스 계층은 레지스트리에 가짜를 주입해 테스트합니다. 프로젝트 루트에서 실행하세요:

```bash
uv run pytest
```

## 🤝 기여 가이드

현재는 개인 MVP이므로 핵심 로직에 대한 직접적인 풀 리퀘스트는 제한될 수 있습니다. 다만 아래 영역의 기여와 포크는 언제든 환영합니다:

1. **새 프로바이더 추가:** `LocalLLMProvider`(예: Ollama) 구현, 또는 다른 클라우드 프로바이더 추가.
2. **평가용 프롬프트:** 여러 모델 답변 간의 충돌을 감지하고 누락된 인용을 부각하는 프롬프트 개선.
3. **비용 분석:** 시간에 따른 모델별 비용 효율을 분석하는 SQL 뷰나 Pandas 스크립트 작성.

***
자유롭게 저장소를 포크하고, 로컬 LLM 연동을 실험해 보세요. 견고한 프롬프트 전략을 발견하면 이슈를 열어 공유해 주세요!
