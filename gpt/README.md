# laighthouse-plugin-external — ChatGPT / Codex판

레포 루트의 Claude Code 플러그인(`skills/`, `hooks/`)을 **ChatGPT / Codex 플러그인**으로 옮긴 것입니다.
스킬 본문·스크립트의 단일 소스는 Claude판이며, `gpt/skills/`와 `gpt/hooks/save_mcp_response.py`는
`sync_from_claude.py`가 만드는 사본입니다 — **직접 고치지 말고** Claude판을 고친 뒤 다시 실행하세요.

```bash
python gpt/sync_from_claude.py
```

## 배포 형태

| 배포 형태 | 대상 | 훅 |
|---|---|---|
| **플러그인** (`gpt/.codex-plugin/plugin.json` + `.mcp.json` + `hooks/` + `skills/`) | ChatGPT 데스크톱 Work 모드, Codex — 레포 루트 `.agents/plugins/marketplace.json`(로컬 마켓플레이스)로 설치 | 응답 저장 훅 동작(`/hooks`에서 신뢰 필요) |
| **스킬 zip** (`build_skill_zips.ps1` 산출물) | chatgpt.com 웹 Chat — 스킬 하나씩 업로드, MCP는 설정에서 커넥터로 연결 | 없음 — 모델이 받은 응답을 직접 파일로 저장 |

## Claude판과 다른 점

| | Claude Code (레포 루트) | ChatGPT / Codex (`gpt/`) |
|---|---|---|
| 매니페스트 | `.claude-plugin/plugin.json` | `gpt/.codex-plugin/plugin.json` + 스킬별 `agents/openai.yaml`(원본은 `gpt/agents-meta/`) |
| MCP | `.mcp.json` (`"type": "http"`) | `gpt/.mcp.json` (`"type": "streamable-http"`) |
| 훅 | `hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}`) | `gpt/hooks/hooks.json` (`${PLUGIN_ROOT}`, 접미 매칭 matcher) — 스크립트는 같은 파일 |
| SKILL.md | 원본 | 첫 제목 아래 ChatGPT/Codex 환경 안내만 추가(훅이 없는 웹 Chat에서의 응답 저장 방법) |

## 설치 A — 플러그인 (ChatGPT 데스크톱 Work 모드 / Codex)

1. 이 레포를 클론합니다. 레포 루트의 `.agents/plugins/marketplace.json`이 `gpt/`를 플러그인으로 가리킵니다.
   레포 밖에서 쓰려면 `codex plugin marketplace add <레포 루트 경로>`.
2. Plugins Directory에서 소스 "Laighthouse External"을 선택해 **Laighthouse Report**를 설치합니다(MCP 인증은 설치 시).
3. 대화에서 `/hooks`를 열어 `save_mcp_response.py`를 신뢰합니다. 신뢰하지 않아도 스킬은 동작하지만, 모델이 응답을
   직접 파일로 저장해야 해서 느리고 큰 응답 섹션은 빠질 수 있습니다. 실행 환경에 `python3`가 필요합니다.

## 설치 B — 스킬 zip (chatgpt.com 웹 Chat)

```powershell
.\gpt\build_skill_zips.ps1
```

`~/Downloads/laighthouse-external-gpt-skills/<스킬>.zip`이 생성됩니다(sync를 먼저 자동 실행하고, 만든 zip을 다시 열어
OpenAI Skills 규격과 SKILL.md가 참조하는 `references/`·`assets/` 파일이 번들에 있는지 검사합니다). Sidebar → Plugins →
Skills → Create → Upload from your computer에서 하나씩 올리고, `laighthouse` MCP 서버를 커넥터로 연결합니다.
