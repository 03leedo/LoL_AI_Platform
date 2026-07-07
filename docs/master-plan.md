# LoL AI Platform — 통합 개발 마스터플랜

> 작성일: 2026-07-07 · 기준 문서: [PRD-expansion.md](./PRD-expansion.md)(확장 기획서)
>
> 이 문서는 PRD("무엇을 만들 것인가")와 **현재 코드베이스** 사이에서
> **어떤 순서로, 어떻게 연결하고, 어디까지 확장 가능하게** 만들 것인지를 확정한다.
> 기존 [development-plan.md](./development-plan.md)의 스프린트 계획을 대체한다.

---

## 0. 현재 위치 — 이미 구현된 것

| 영역 | 상태 | 비고 |
|---|---|---|
| Riot ID 검색 / 소환사 조회 | ✅ | Account-V1 + Summoner-V4, KR/asia 라우팅 |
| 최근 경기 목록 + 매치 카드 | ✅ | KDA/딜량/KP/골드/CS 표시 |
| 매치·타임라인 수집/저장 | ✅ | raw JSONB 보존 + 정규화(participants, events, 분단위 features) |
| 커스텀 지표 5종 | ✅ | Death Cost, Throw Index, Objective Setup, Lead Conversion, Stability |
| 증거(evidence) + 컨텍스트 리뷰 | ✅ | ±30초 윈도우, 미니맵 스냅샷 재생, 룰 기반 인사이트 |
| 주요 이벤트(key events) 추출 | ✅ | 우선순위 기반 최대 28개, 한글 라벨 |
| LLM 피드백(선택) | ✅ | OpenAI 호환, 미설정 시 룰 기반 폴백 |
| 인프라 | ✅ | Docker Compose (Postgres + FastAPI + Next.js) |

**지금 가진 핵심 자산 3가지** (이후 모든 확장이 이 위에 선다):

1. **raw JSON 보존** — `riot_matches.raw_json`, `match_events.raw_json`, `raw_frame`.
   지표 공식이 바뀌어도 Riot 재호출 없이 전체 재계산 가능.
2. **evidence + confidence 규약** — 모든 점수가 `{value, confidence, direction}` + 근거 목록을 가짐.
   PRD §19.2(신뢰도 표시) 원칙이 이미 코드 규약으로 존재.
3. **미니맵 렌더러** — 타임라인 좌표를 DDragon 맵 위에 그리는 프론트 컴포넌트.
   히트맵(신규)과 리플레이 좌표 뷰(확장)가 그대로 재활용.

**남은 갭**: Riot 클라이언트에 rate limit/재시도/캐시 없음 · DB 마이그레이션 없음(create_all) ·
프론트 단일 페이지(884줄) · 포지션 분석 / 능력치 평가표 / 승률 / 히트맵 / 벤치마크 / 신규 지표 미구현.

---

## 1. 전략 — 3계층 데이터 전략

기능을 하나씩 따로 만드는 게 아니라, **같은 지표·같은 화면의 "데이터 해상도"를 단계적으로 올리는** 구조로 간다.

| 계층 | 소스 | 얻는 것 | 해상도 | 단계 |
|---|---|---|---|---|
| **T1 정량** | Riot API (Match + Timeline + League) | 이벤트 로그, 분단위 좌표/골드/XP, challenges 파생 스탯 | 1분 / 이벤트 단위 | MVP (현재) |
| **T2 시공간 정밀** | 리플레이 컴패니언 (LCU 다운로드 + Replay API + 미니맵 CV) | **초단위 10인 좌표**, 팀 시야(fog) 기준 노출 여부, 클립 | ~1초 | 확장 E1 |
| **T3 정성** | 하이라이트 클립 프레임 + Vision LLM | 한타 포지셔닝, 카이팅 무빙, 웨이브 상태 | 장면 단위 | 확장 E2 |

**핵심 원칙**: 모든 지표는 `(value, confidence, direction, evidence[], source, metric_version)`을 가진다.
T2/T3가 붙으면 **같은 지표의 `source`와 `confidence`가 올라갈 뿐**, 스키마·UI·리포트 구조는 그대로다.
예) "회피 가능한 데스" — T1에서는 근사(confidence: low~medium), T2에서 fog 실측(confidence: high)으로 승격.

---

## 2. 확장 이음새 — 지금 심어둘 것 5가지

나중에 하이라이트·비전·로컬 에이전트를 붙일 때 갈아엎지 않기 위한 최소 장치.

1. **Moment 영속화** — 지금 key_events/evidence는 요청 시마다 즉석 계산.
   이를 `moments` 테이블로 승격한다. Moment(경기 내 의미 있는 구간)는 이후
   **AI 리포트의 인용 단위 = 하이라이트 클립의 컷 단위 = Vision 분석의 첨부 단위**로 삼는 공용 화폐다.
2. **metric_scores long format** — 지표를 열(column)이 아니라 행(row)으로 저장.
   새 지표 추가 = INSERT일 뿐, 스키마 변경이 없다. (기존 `player_skill_scores`는 유지하되 신규는 long format으로)
3. **source(provenance) 필드** — 모든 점수/모먼트에 `api | approx | replay | vision` 출처 표기.
   T2/T3 데이터가 오면 같은 지표를 더 높은 신뢰도로 덮어쓰는 것이 자연스러워진다.
4. **metric_version + raw 재계산** — 공식 개선 시 버전 올리고 raw JSONB에서 배치 재계산.
5. **미디어 추상화** — 하이라이트는 `moment_id`를 참조하고 `clip_url`은 nullable.
   MVP에서는 "클립 없는 모먼트 카드"로 먼저 노출하고, E1/E2에서 영상이 뒤에 꽂힌다.

---

## 3. 데이터 현실 체크 — 설계를 좌우하는 팩트

### 3.1 이미 손에 있는 노다지 (raw_json에 저장돼 있고 파싱만 하면 됨)

- **`participants[].challenges` (~100개 필드)** — 라인전·교전·시야 지표 상당수가 이미 계산돼 온다:
  `soloKills`, `skillshotsDodged`, `dodgeSkillShotsSmallWindow`, `survivedSingleDigitHpCount`,
  `tookLargeDamageSurvived`, `laningPhaseGoldExpAdvantage`, `maxCsAdvantageOnLaneOpponent`,
  `visionScoreAdvantageLaneOpponent`, `damagePerMinute`, `goldPerMinute`, `teamDamagePercentage`,
  `killParticipation`, `turretPlates`, `epicMonsterSteals`, `effectiveHealAndShielding` 등.
  (패치별로 필드가 바뀔 수 있어 **defensive 파싱** 필수)
- **`CHAMPION_KILL.victimDamageReceived`** — 죽을 때 누가·어떤 스킬로·어떤 데미지 구성으로 잡았는지.
  데스 카드에 "포커싱 구성" 표시 가능. (단, 타임스탬프는 없어 "몇 초 만에 녹았나"는 불가 → T2)
- **킬/데스 좌표** — `match_events.position_x/y`에 이미 저장 중. **히트맵은 추가 수집 없이 지금 바로 가능.**
- **`shutdownBounty`** — 제압골 헌납이 이벤트에 직접 들어옴 (도박사 지표 재료).
- **frames의 `damageStats` / `championStats` / `timeEnemySpentControlled`** — 분단위 누적 딜/받은딜, 스탯 스냅샷, 내가 건 CC 누적.

### 3.2 Riot이 안 주는 것 → 설계 대응

| 없는 데이터 | 영향 받는 아이디어 | T1 대체 설계 | 승격 계층 |
|---|---|---|---|
| **받은 CC 시간** (건 CC만 제공) | 카이팅/생존 지표 원안 | challenges 회피 지표 + 한타 딜 지속성으로 재정의 (§4.3) | T2/T3 |
| **순간 체력** (분 스냅샷만) | "체력 20%에서 무리수" | `survivedSingleDigitHpCount` 등 간접 지표 | T2 |
| **와드 좌표** (WARD_PLACED에 position 없음) | 시야 히트맵 | 시야 점수·와드 수 통계까지만 | T2 (리플레이) |
| **60초 미만 위치** | 고립 데스 정밀 판정 | 최근접 프레임 근사(±30s 오차, confidence 명시) | T2 |
| **시야(fog) 노출 여부** | "상대가 보였는데 죽었나" (PRD §7.5, §10) | 직전 상대 이벤트 노출 기반 근사 | **T2 (fog 실측 — 핵심 차별화)** |
| **스킬/궁 사용 로그** | "궁 들고 폭사", 한타 침묵 시간 | **API로 측정 불가** — v0은 근사 + confidence: low | T2/T3, 내 게임은 E3 |

> ⚠️ PRD §11·§13의 "궁극기를 소지한 채 폭사" 류 지표는 Riot API만으로는 **원리적으로 불가**.
> 이 부류가 바로 리플레이/비전 확장(E1·E2)의 존재 이유이며, MVP에서는 약속하지 않는다.

### 3.3 API 실무 참고

- Spectator는 **V5**(by-puuid)가 현행, League-V4도 by-puuid 엔드포인트 사용 가능.
- 개발자 키 rate limit: **20 req/1s + 100 req/2min** (앱 전역).
  → 20판 수집 = 매치+타임라인 40콜 + α로 **2분 제한에 걸림**. 백그라운드 잡 큐가 필수(M0).
  → 벤치마크 코호트 수집(M4)까지 가면 **프로덕션 키 신청**이 사실상 필요. 미리 신청해 둘 것.
- 매치/타임라인은 불변 데이터 — **DB에 있으면 Riot 재호출 스킵** (DB-first 캐시, M0에서 적용).

---

## 4. 지표 로드맵 (지표 사전 v2)

기존 5종(Death Cost, Throw, Objective Setup, Lead Conversion, Stability)은 유지·보정. 신규는 아래 순서로.

| # | 지표 | 정의 (요약) | 주 입력 | T1 신뢰도 | 마일스톤 |
|---|---|---|---|---|---|
| 4.1 | **골드 리텐션** (스노우볼 낭비) | 1,500g+ 들고 필드에 머문 누적 시간, 킬 후 아이템 전환까지 평균 지연 | frames `currentGold`, `ITEM_PURCHASED` | 높음 (±60s) | M1 |
| 4.2 | **도박사 지수** | 제압골 헌납 + 고립 데스(근사) + 적진 침투 킬/데스 비율 + 솔로킬 성향 | `shutdownBounty`, 킬 좌표, challenges | 중간 | M1 |
| 4.3 | **한타 생존·딜 지속** (카이팅 프록시) | 킬 밀집 구간(fight window)에서 낸 딜 ÷ 데스, 스킬샷 회피 결합 | frames `damageStats` 델타, challenges 회피 필드 | 중간 | M1 |
| 4.4 | **킬/데스 히트맵 + 데스존** | 최근 N판 킬(블루)/데스(레드) 좌표 밀도 → 상위 밀집 구역 라벨링("데스 존") | `match_events.position` (이미 있음) | 높음 | M1 |
| 4.5 | **데스 가속도** | 첫 데스 후 5분 내 연쇄 데스 구간 감지 (멘탈 붕괴 패턴) | 킬 이벤트 | 높음 | M1 |
| 4.6 | **승률 곡선 v0** | 분단위 골드/XP/오브젝트 차이 기반 규칙형 승률 추정 그래프 | timeline features (이미 있음) | 중간 | M1 |
| 4.7 | **공통 6능력치 평가표** | 라인전/교전/오브젝트/맵리딩/리드전환/안정성 — 다중 경기 집계 (PRD §6) | 기존 지표 + challenges | 중간~높음 | M2 |
| 4.8 | **포지션 적합도** | 승률 + 라인 핵심 지표 + 공통 운영 + 최근 폼 + 표본 신뢰도 보정 (PRD §8) | 4.7 + 포지션 분류 | 중간 | M2 |
| 4.9 | **벤치마크 격차** ("나 vs 상위 티어") | 코호트(패치×티어×포지션) percentile 분포 대비 내 위치 | 챌린저/GM 수집 파이프라인 | 높음 | M4 |
| 4.10 | 한타 침묵 시간 | fight window 참여했으나 기여 0 근사 — **confidence: low 명시** | frames 델타 (분단위 한계) | 낮음 | M4→T2 승격 |

각 지표 구현 시 공통 규칙: ① 산식과 상수는 서비스 코드에 상수로 명시 ② evidence(모먼트 참조) 필수
③ 근사가 들어가면 confidence 강등 + UI 표기 ④ 픽스처 기반 유닛 테스트 (기존 `tests/` 패턴 유지).

---

## 5. 아키텍처 진화

### 5.1 구조 (현재 구조 유지 + 추가분)

```text
frontend (Next.js)
  /                    검색                        [분리: M0]
  /summoner/[riotId]   프로필·매치목록·랭크분석 탭   [M2]
  /match/[matchId]     경기 상세 리뷰(현 리뷰 패널)   [M0 분리]

backend (FastAPI)
  api/routes      riot(현행) + analysis + ingest(잡 상태) + benchmarks
  services        riot_client(강화) · timeline_analyzer · custom_metrics
                  key_events → moments · evidence_contexts · llm_feedback(프로바이더 계층)
                  + heatmaps · role_analyzer · scorecard · benchmark · win_probability
  workers         ingest 잡 러너(다중 경기 수집) · 벤치마크 코호트 수집(스케줄)
  repositories    현행 + moments/metric_scores/benchmarks/ingest_jobs

companion (확장 E1, Tauri)   리플레이 다운로드·재생 제어·좌표 추출·업로드
```

### 5.2 DB 변경점 (M0에서 alembic 도입과 함께)

```text
moments            id, match_id, puuid?, t_start_ms, t_end_ms, moment_type,
                   importance, evidence(JSONB), source, created_at
metric_scores      puuid, scope(match|aggregate), match_id?, role?, window?,
                   metric_key, value, grade?, confidence, direction,
                   evidence(JSONB: moment_id 참조), source, metric_version, computed_at
ingest_jobs        id, puuid, requested_count, state(queued|running|done|failed),
                   progress, error?, created_at            ← 다중 경기 수집 추적
benchmarks (M4)    patch, cohort(tier), role, metric_key, p25/p50/p75/p90, sample_size
position_tracks (E1)  match_id, participant_id, source, resolution_ms, track(압축 JSONB)
```

### 5.3 riot_client 강화 (M0)

- 토큰 버킷 rate limiter (20/1s + 100/120s 전역, 여유율 80%) + `429 Retry-After` 존중 백오프
- DB-first: `riot_matches`/timeline에 있으면 재호출 스킵 (매치 데이터는 불변)
- account/summoner 단기 캐시 (우선 인메모리 TTL, Redis는 M5에서 교체)

### 5.4 LLM 프로바이더 계층 (M3)

현행 OpenAI 호환(`openai_base_url` 교체 가능) 유지 + 인터페이스 한 겹:
경기별 짧은 인사이트는 저비용 모델, **종합 리포트는 상위 모델**로 이원화.
Anthropic(claude-sonnet-5) 옵션 추가 — 구조화 입력(JSON) → 근거 인용 리포트에 강함.
리포트 캐시 키: `(puuid, 최신 match_id, metric_version)` — 새 경기 없으면 재생성 안 함.

---

## 6. 로드맵 — 마일스톤

> 규모: S(1~3일) M(1~2주) L(2주+) 감각치. 각 단계는 배포 가능한 상태로 끝낸다.

| 단계 | 이름 | 내용 | 완료 기준 | 규모 |
|---|---|---|---|---|
| **M0** | 기반 보강 | rate limiter/재시도/DB-first 캐시 · alembic · moments/metric_scores/ingest_jobs 테이블 · 프론트 라우트 분리 | 20판 연속 수집이 429 없이 완료 · 마이그레이션으로 스키마 관리 | S~M |
| **M1** | 신규 지표 + 히트맵 | §4.1~4.6 (골드 리텐션·도박사·한타 생존·**히트맵/데스존**·데스 가속도·승률 곡선 v0) + challenges 파서 | 경기 상세에 신규 지표 카드 + 소환사 페이지에 최근 20판 히트맵 | M |
| **M2** | 포지션 분석 + 평가표 | 다중 경기 백그라운드 수집 · League-V4 랭크 · 공통 6능력치 집계 · 포지션 적합도/추천 · 랭크 분석 탭 UI | PRD §8.2 화면 재현, 표본 부족 시 신뢰도 경고 | M |
| **M3** | AI 종합 리포트 | 다중 경기 종합(강점/약점/반복 패턴/추천 포지션) · 프로바이더 계층 · moment 인용 링크 · 캐싱/비용 가드 | 리포트의 모든 주장에 근거(모먼트/지표) 링크 | S~M |
| **M4** | 벤치마크 + 예측 고도화 | 챌린저/GM 코호트 수집 잡 · percentile 저장 · "나 vs 상위 티어" 비교 UI · (데이터 쌓이면) XGBoost+SHAP 승률 교체 | 지표별 상위 티어 대비 백분위 표시 | M |
| **M5** | 프로덕션 | Redis · 인덱스 · CI(GitHub Actions) · k6 · nginx · 배포 | PRD Sprint 6 기준 | S~M |
| **E1** | 리플레이 컴패니언 α | §7.1 — 좌표 트랙 추출·업로드, 지표 source=replay 승격 | 한 경기의 1초 단위 10인 트랙이 서버 지표에 반영 | L |
| **E2** | 하이라이트 + Vision | §7.2 — Moment→클립→프레임→Vision LLM | 주요 장면 TOP3 + 비전 분석 카드(신뢰도 표기) | L |
| **E3** | 라이브 이벤트 에이전트 | §7.3 — 내 경기 자동 이벤트 기록→경기 후 자동 클립 | 경기 종료 후 자동 복기 목록 생성 | M |

PRD 스프린트와의 매핑: M0~M1 ≈ Sprint 3 잔여+α, M2 ≈ Sprint 4, M3 ≈ Sprint 5, M5 ≈ Sprint 6,
E1~E3 ≈ Expansion Sprint 7~9 (단, **순서를 "업로드 영상"이 아니라 "리플레이 컴패니언" 우선으로 뒤집음** — §7.1 참조).

---

## 7. 확장 상세 설계

### 7.1 E1 — Replay Companion (핵심 차별화)

사용자가 영상을 올리는 게 아니라, **로컬 컴패니언 앱이 리플레이에서 구조화 데이터를 뽑아 서버로 보낸다.**

```text
[Tauri 데스크톱 앱]
 1. LCU API로 최근 분석 대상 경기의 리플레이(.rofl) 자동 다운로드
    (서버가 "이 매치 리플레이 원함" 큐를 내려줌)
 2. 리플레이 재생 실행 → 게임 클라이언트가 Replay API 노출
    (game.cfg에 EnableReplayApi=1, https://127.0.0.1:2999)
 3. /replay/playback 으로 배속 재생·시점 점프 제어
    /replay/render 로 카메라·UI·fog(팀 시야) 제어
 4. 주기적 미니맵 캡처 → 템플릿 매칭(CDragon 챔피언 아이콘)
    → 10인 초단위 좌표 트랙 생성
 5. 서버 업로드: 영상이 아니라 좌표 JSON 수십 KB
 6. (클립 필요 시) Moment 구간만 /replay/recording 으로 클라 자체 녹화
```

**왜 이 순서인가 (PRD Sprint 7 "영상 업로드"보다 먼저):**
- 30분 VOD를 직접 올릴 사용자는 거의 없다 — 컴패니언은 **풋티지 확보 문제 자체를 없앤다**.
- 영상(GB)이 아니라 좌표(KB)를 옮기므로 스토리지/처리 비용과 프라이버시 부담이 급감한다.
- **fog를 내 팀 시야로 놓고 보면 "죽기 전에 상대가 우리 미니맵에 보였는가"를 실측**할 수 있다.
  → PRD §7.5(Visible Threat Response), §10(회피 가능한 데스 vs 전략적 압박 판정)이 근사가 아닌 측정이 된다.
  이것이 어떤 전적 사이트도 없는 이 서비스의 결정적 차별화 포인트.
- 업로드 방식은 fallback으로 유지 (컴패니언 미설치 사용자용, E2에서).

**제약과 대응:**
- 리플레이는 **현재 패치 경기만 재생 가능** → "경기 후 조기 수집" 정책, 서버가 수집 대기 큐 관리.
- LCU 리플레이 다운로드 엔드포인트는 비공식 → 버전 변화 감내 설계(실패 시 스킵, 기능 저하만).
- 화면 캡처 + 공식 로컬 API만 사용, 메모리 접근·주입 없음 (Vanguard 안전).

### 7.2 E2 — 하이라이트 + Vision 분석

```text
moments (T1에서 이미 축적) → Highlight Score 상위 구간 선정
→ 클립 확보 (E1 클라 녹화 / 사용자 업로드 영상 FFmpeg 컷)
→ 프레임 샘플링 (시작·교전 직전·스킬 교환·킬/데스 직전·결과)
→ Vision LLM 분석 (포지셔닝·웨이브·카이팅) → moment에 결과 첨부
```
- Vision 결과는 항상 **가능성 + 근거 + 신뢰도**로 표현 (PRD §12.4 문구 규정 준수).
- Vision은 점수의 "보정자"이지 단독 판정자가 아님 — API 근거 없는 Vision 단독 점수 금지.

### 7.3 E3 — 라이브 이벤트 에이전트

- 내 게임 중 Live Client Data API(`https://127.0.0.1:2999/liveclientdata/allgamedata`) 폴링으로
  킬/오브젝트 이벤트 타임스탬프만 기록 → 경기 종료 후 리플레이/녹화와 결합해 자동 클립.
- **경기 중 사용자에게 어떤 분석·조언도 노출하지 않는다** (수집 전용). PRD §19.3 유지.

### 7.4 정책 가드레일 (전 단계 공통)

1. 실시간 조언 금지 — 수집은 실시간, 분석·노출은 경기 후.
2. 의도 단정 금지 — "~했을 가능성", "확인 필요" 화법 (이미 LLM 시스템 프롬프트에 반영됨).
3. 모든 점수에 근거 + 신뢰도 (이미 규약 존재 — 신규 지표도 동일 규약 강제).
4. **Riot 프로덕션 API 키 신청** — M2(다중 수집) 전에 신청 권장, M4(코호트)에는 사실상 필수.

---

## 8. 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| 개발 키 rate limit (100/2min) | 다중 경기·코호트 수집 지연 | 잡 큐 + DB-first 캐시(M0), 프로덕션 키 신청 |
| challenges 필드 패치 변동 | 지표 계산 실패 | defensive 파싱 + 필드 부재 시 confidence 강등 |
| 분단위 프레임 한계 | 고립/한타 지표 오차 | 근사임을 UI에 명시, T2에서 승격 |
| LCU/Replay API 비공식성 | 컴패니언 기능 중단 가능 | 실패 시 T1로 자동 강등(서비스 코어는 무영향) |
| 리플레이 패치 윈도우 | 과거 경기 좌표 추출 불가 | 조기 수집 정책, 놓친 경기는 T1 데이터로 유지 |
| 미니맵 CV 패치 취약성 | 트랙 품질 저하 | CDragon 에셋 자동 갱신 + 버전별 캘리브레이션 테스트 |
| LLM 비용 | 리포트 남발 시 비용 증가 | 캐시 키 전략 + 모델 이원화 + 일일 상한 |
| 단일 page.tsx 비대화 | 개발 속도 저하 | M0에서 라우트/컴포넌트 분리 |

---

## 9. 바로 다음 작업 — M0 체크리스트

- [ ] riot_client: 토큰 버킷 rate limiter + 429 백오프 + 재시도
- [ ] 매치/타임라인 DB-first 조회 (있으면 Riot 호출 스킵)
- [ ] alembic 도입 (기존 테이블 baseline 마이그레이션)
- [ ] `moments` / `metric_scores` / `ingest_jobs` 테이블 + 리포지토리
- [ ] key_events → moments 영속화 연결 (기존 응답 형식은 유지)
- [ ] 프론트 라우트 분리: `/` 검색 · `/summoner/[riotId]` · `/match/[matchId]`
- [ ] (준비) Riot 프로덕션 키 신청서 제출

M0가 끝나면 M1(신규 지표 + 히트맵)부터는 화면에 보이는 것이 매주 늘어나는 구간에 들어간다.
