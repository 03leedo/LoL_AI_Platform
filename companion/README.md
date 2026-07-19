# Companion C1 — Live Client 수집기

내 게임 중 로컬 Live Client Data API(`https://127.0.0.1:2999`)를 폴링해서
**내 체력·골드·스탯·이벤트**를 로컬 SQLite에 버퍼링하고, **경기가 끝난 뒤**
백엔드로 업로드하는 수집 전용 프로그램입니다.

- **경기 중 어떤 분석·조언도 표시하지 않습니다** (수집 전용, opt-in).
- 수집 대상은 이 프로그램을 직접 실행한 본인 게임뿐입니다.
- Live Client API는 게임 클라이언트가 로컬에서 제공하는 공식 API입니다.

## 설치 (게임하는 PC에서)

1. Python 3.10 이상 설치 — https://python.org (설치 시 "Add to PATH" 체크)
2. 이 폴더의 `live_collector.py` 를 아무 폴더에나 복사
3. 백엔드가 켜져 있는지 확인 (`docker compose up` — 기본 http://localhost:8000)

## 실행

게임 시작 전에(또는 게임 중에라도) 터미널에서:

```powershell
python live_collector.py --riot-id "게임이름#KR1"
```

옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--backend` | `http://localhost:8000` | 백엔드 주소 (다른 PC면 `http://<그 PC IP>:8000`) |
| `--interval` | `1.0` | 폴링 주기(초) |
| `--db` | `live_buffer.sqlite` | 로컬 버퍼 파일 경로 |

동작:
- 게임이 감지되면 세션(UUID)을 만들고 1초마다 스냅샷을 로컬에 저장
- 게임이 끝나면 자동 업로드 → 서버가 저장된 전적과 대조(riot id + 시작 시각)
- 업로드 실패 시 로컬에 남아 있고, 다음 실행 때 자동 재시도
  (서버가 (session, seq) 중복을 무시하므로 재시도는 항상 안전)
- 종료: `Ctrl+C`

## 개인정보

- 전송 데이터: 본인 riot id, 게임 시간, 본인 챔피언 스탯/골드, 게임 이벤트 목록
- 다른 플레이어의 식별 정보는 이벤트에 포함된 이름 외에 수집하지 않습니다
- 로컬 버퍼(`live_buffer.sqlite`)는 언제든 삭제해도 됩니다 (업로드 전 데이터만 소실)
