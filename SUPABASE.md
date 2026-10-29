# Supabase 클라우드 세이브

1. Supabase 프로젝트 생성 → Authentication > Providers 에서 **Anonymous sign-ins** 활성화.
2. SQL Editor에서 `supabase/schema.sql` 실행.
3. `supabase-config.js`에 Project URL과 anon key 입력 (anon key는 공개용이며 RLS로 보호됨. service_role 키는 절대 넣지 마세요).
4. 배포. 값이 비어 있으면 기존처럼 localStorage만 사용합니다.

동작: 게임 저장 시 5초 디바운스로 `game_saves`에 업로드, 접속 시 클라우드 저장본이 더 최신이면 로컬에 덮어쓰고 1회 새로고침합니다.

## 닉네임/비밀번호 로그인
- 기본은 익명 계정입니다. 게임의 👤 버튼에서 **닉네임 + 비밀번호(6자 이상)**로 회원가입하면 현재 익명 계정에 연결되어 진행 상황이 유지됩니다. 실제 이메일은 필요 없습니다(닉네임은 내부적으로 `<hex>@dolhareubang.app` 주소로 변환).
- **로그인**하면 그 계정의 클라우드 저장본을 불러옵니다. **로그아웃**은 최신 저장을 올린 뒤 이 기기의 로컬 저장본을 지웁니다.
- 필수 설정: Authentication > Sign In / Providers 의 **Confirm email을 꺼야** 합니다(가짜 주소라 확인 메일을 받을 수 없음). 비밀번호를 잊으면 복구 수단이 없습니다.
