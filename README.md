# real-estate

온라인 임장 리포트와 가이드를 모아 둔 저장소입니다.

## 배포된 페이지

로그인 없이 누구나 열 수 있어요. Google Apps Script 웹앱으로 배포했습니다.

| 페이지 | 링크 | 원본 |
|---|---|---|
| 안양 비산동 온라인 임장 (지도, 범계역 출발 동선 포함) | [열기](https://script.google.com/macros/s/AKfycbwnMTLsV7VGntcosR-_Ow9Zq_rl0F3cOxUVElZan8o_QRQ4d79HvUfkD1dXlK92QPIN/exec?p=anyang-bisan-2026-10-15) | `reports/안양-비산동-온라인-임장-2026-10-15.html` |
| 첫 임장 가이드 | [열기](https://script.google.com/macros/s/AKfycbwnMTLsV7VGntcosR-_Ow9Zq_rl0F3cOxUVElZan8o_QRQ4d79HvUfkD1dXlK92QPIN/exec?p=imjang-guide-2026-10-24) | `GUIDE.html` |

원본을 고친 뒤 같은 slug로 다시 올리면 링크는 그대로 유지됩니다.

```bash
python3 ~/.claude/skills/gas-html-publish/scripts/gas_publish.py add <원본 파일> --slug <slug>
```
