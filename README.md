# DAY 4 · 돌하르방의 제주 텃밭

단계별 프롬프트로 만든 three.js 3D 텃밭 게임과, Blender로 만든 제주 지형 영상이 들어 있어요.

- 배포: https://day4-ten-theta.vercel.app (저장소 jeongeunlee0/day4, `main`에 푸시하면 Vercel이 자동 배포)

## 페이지

| 파일 | 내용 |
|---|---|
| `index.html` | 배포 첫 화면 — 게임 + Supabase 저장 · 로그인 · 장바구니 |
| `game.html` | 같은 게임의 다른 버전 |
| `universe.html` · `universe2.html` | three.js 우주 장면 |
| `jeju_game_steps/step1 ~ 9.html` | 「돌돌이의 귤 바람」 단계별 정답 예시 |
| `jeju_game_steps/프롬프트_순서.md` | 단계마다 AI에게 입력한 프롬프트 |

## 지형 영상 (Blender)

| 파일 | 내용 |
|---|---|
| `fetch_dem.py` | 제주 지형 높이 데이터 받기 → `dem/` |
| `build_scene.py` | `blender -b -P build_scene.py` → `jeju_birth.blend` |
| `render_final.py` · `test_render.py` | 프레임 렌더링 → `frames/f_0001.png …` |
| `encode_video.py` | 프레임을 영상으로 → `jeju_birth.mp4` |

## Supabase

`supabase-config.js` · `supabase-sync.js` · `supabase/schema.sql` — 설정 방법은 `SUPABASE.md`에 있어요.

## 이 PC에만 있는 파일 (git 제외)

`frames/`(렌더 프레임) · `test/` · `jeju_birth.blend` · `render_log.txt` · `.env.local`.
렌더링 스크립트가 이 위치를 그대로 쓰기 때문에 옮기지 않아요.
